# Runbook: backup and restore

The app backs up its SQLite database every night at 03:30 (Europe/Berlin) into
`data/backups/`, and once on start if today has no backup yet (ADR-0010, step 1-H). Each
backup is a complete, standalone `.db` file: it is copied with SQLite's online backup API,
checked with `PRAGMA integrity_check`, and only then renamed into place.

| What | Where | Kept |
| --- | --- | --- |
| Nightly | `data/backups/training_coach-YYYY-MM-DD.db` | newest 7, plus the newest of each of the 4 weeks before them |
| Manual (and before every deploy) | `data/backups/training_coach-manual-<UTC time>.db` | 35 days (ADR-0044) |
| Desktop copy (not set up yet) | `~/backups/training-coach/` via `scripts/pull-backup.sh` | 35 days |
| Off-site | Cloudflare R2 bucket, encrypted with age, via `scripts/offsite-backup.sh` | 35 days |

A failed backup logs `backup.failed` and, when the bot is on, sends you a Telegram message.
Data loss is at most one day.

Everything personal is in that one file: workouts, test days, measurements and progress
photos (photos are rows in `progress_photos`, ADR-0039). So a backup, the desktop copy and a
restore cover photos and measurements with nothing extra to copy. Treat backups and the
desktop copy as private for the same reason.

## Manual backup (before a deploy with a migration, or any risky change)

```bash
docker compose exec app training-coach backup    # logs backup.created with the file name
```

It's deleted after 35 days, like every copy, so erased data doesn't linger (ADR-0044). If a
backup has to outlive that (evidence of a problem, say), copy it out of `data/backups/` under
another name and delete it yourself when done.

## Pulling backups to the desktop

One-time setup on the Pi, so your SSH user can read the backups (the app writes them as
uid/gid 10001, mode 0640):

```bash
getent group 10001          # must print nothing, or coach-data from an earlier run
sudo groupadd --gid 10001 coach-data       # the container's app group, by number
sudo usermod -aG coach-data vybe           # log out and back in afterwards
sudo chmod 750 data && sudo chmod 640 data/training_coach.db*   # not readable by other users
```

If gid 10001 already belongs to another group, stop: every member of that group could read
your data. Pick the fix with that group's owner first.

The app runs with umask 027, so database files it creates from now on are group-readable at
most; the `chmod` fixes ones created before.

Then on the desktop (Linux or WSL), run it once by hand and add the cron line from the
script's header:

```bash
scripts/pull-backup.sh            # ok: newest nightly backup is training_coach-2026-10-07.db
```

It exits non-zero with a warning when nothing newer than two days has arrived: the pull worked
but the Pi stopped backing up.

## Restore

```bash
docker compose down
cp data/training_coach.db data/training_coach.db.broken    # keep the bad one for later
cp data/backups/<file>.db data/training_coach.db           # or copy one back from the desktop
rm -f data/training_coach.db-wal data/training_coach.db-shm
sudo chown 10001:10001 data/training_coach.db
docker compose up -d --build                               # migrations run on start
curl -s localhost:8095/healthz && docker compose logs app | grep -E "bot.started|backup"
```

Restoring an older backup into a newer release is fine: migrations bring it up to date on
start. Restoring into an older release than the backup's needs that release's schema; check
out the matching tag first.

## Off-site copies (ADR-0042)

Every night at 04:30 the Pi encrypts the newest backup with a **dedicated backup age key** and
copies it to a Cloudflare R2 bucket, then deletes copies older than 35 days. Only that key's
private half can read them: its master copy is in Liam's password manager ("Training Coach
backup key"), with a working copy at `%USERPROFILE%\.age\training-coach-backups.txt` on Windows.
The desktop dual-boots Windows and Linux, so the key mustn't live on only one side. R2's free tier
(10 GB, no download fees) covers this many times over.

### Set up (once)

1. **On the Pi**: `sudo apt install -y age rclone`.
2. **In Cloudflare** (dashboard → R2): create a bucket, e.g. `training-coach-backups` (location:
   Europe). Then **Manage API tokens → Create API token**: permission *Object Read & Write*,
   *applied to this bucket only*. Note the Access Key ID, Secret Access Key and the S3 endpoint
   (`https://<account id>.r2.cloudflarestorage.com`). Never paste them into chat, issues or git.
3. **On the Pi**, create the settings file (it holds the token, so mode 600):

   ```
   mkdir -p ~/.config/training-coach
   install -m 600 /dev/null ~/.config/training-coach/offsite.env
   nano ~/.config/training-coach/offsite.env
   ```

   with:

   ```
   TC_BACKUP_AGE_RECIPIENT=age1src86urme5la8q453dxf300jgq625u6dvsm0zn4gwudlps49dvgsuhczzr
   TC_OFFSITE_BUCKET=training-coach-backups
   RCLONE_CONFIG_R2_TYPE=s3
   RCLONE_CONFIG_R2_PROVIDER=Cloudflare
   RCLONE_CONFIG_R2_ACCESS_KEY_ID=<access key id>
   RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=<secret access key>
   RCLONE_CONFIG_R2_ENDPOINT=https://<account id>.r2.cloudflarestorage.com
   TC_OFFSITE_PING_URL=https://hc-ping.com/<uuid>
   ```

   The ping URL is a second Healthchecks.io check (period 1 day, grace a few hours), next to
   the app's heartbeat (`deploy.md`, "Uptime monitoring"). The job pings it after each good run
   and on a failure, so a job that stops running, or never started, sends an email. Without it
   the job still runs and logs a warning.

   For a second key (recommended: any one of them can decrypt, so losing one loses nothing),
   list both public halves in quotes:
   `TC_BACKUP_AGE_RECIPIENT="age1first... age1second..."`.

   (The recipient is the backup key's **public** half. Made once on Windows with
   `winget install FiloSottile.age`, `mkdir $HOME\.age` and
   `age-keygen -o $HOME\.age\training-coach-backups.txt`;
   `age-keygen -y` on that file prints it again.)
4. **Try it once**, then install the timer. Your SSH user needs the `coach-data` group first
   (see "Pulling backups to the desktop"), or the script can't read the backups:

   ```
   ~/training-coach/scripts/offsite-backup.sh       # "uploaded training_coach-....db.age"
   sudo cp ~/training-coach/scripts/systemd/training-coach-alert@.service /etc/systemd/system/
   sudo cp ~/training-coach/scripts/systemd/training-coach-offsite.{service,timer} /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now training-coach-offsite.timer
   systemctl list-timers training-coach-offsite.timer
   ```

5. **Keep the backup key's private half in the password manager** (the `AGE-SECRET-KEY-1…`
   line). Without it the off-site copies can't be read.

Check: `journalctl -u training-coach-offsite -n 20` shows `ok: kept the last 35 days off-site`.

### Restore from off-site

On any machine with age: download the file from the R2 dashboard (or
`rclone copy r2:<bucket>/<name> .`), then decrypt with the backup key, e.g. on Windows
`age -d -i $HOME\.age\training-coach-backups.txt -o training_coach.db <name>.db.age` (or a key
file restored from the password manager), and restore that file as in "Restore" above.

## Rehearsal

Rehearse a restore once per phase and note it in the release PR. It runs beside the live app,
which is never stopped or touched:

1. Take a manual backup (above), and note `PRAGMA integrity_check` and the row counts of
   workouts, set_logs, measurements, progress_photos and test_days, plus the photos' total size.
   The backups are readable only inside the container or by `coach-data`; with sqlite3 missing
   on the Pi, `docker compose exec -T app python -` with a short script does it.
2. Copy it into a scratch folder (`mkdir -m 700 ~/tc-drill`; `docker compose cp
   app:/data/backups/<file>.db ~/tc-drill/data/training_coach.db`) and start a second container
   of the same image on it, with no `.env` (so no bot and no messages) and no network:
   `docker run -d --name tc-drill --user "$(id -u):$(id -g)" -v "$HOME/tc-drill/data:/data"
   --read-only --tmpfs /tmp --cap-drop ALL --network none training-coach:local`.
3. When it's healthy, compare the integrity check, the migration (`alembic_version`) and the
   counts with step 1.
4. With no photos or measurements in the live data yet, add a test photo and measurement to the
   drill copy, back the drill copy up (`docker exec tc-drill training-coach backup`), restore
   that into a second drill container and check the photo comes back byte for byte.
5. Off-site: download last night's copy (`rclone copyto r2:<bucket>/<name> ...`, with
   `offsite.env` sourced), decrypt it on the desktop with the backup key (above), compare its
   counts, and delete the decrypted file.
6. `docker rm -f tc-drill ...`, `rm -rf ~/tc-drill`.

Last rehearsed: **2026-10-25 on the Pi** (v0.38.1), as above. The restore, the migration check,
every count and the test photo's bytes matched, and the off-site copy decrypted with the backup
key and matched its nightly backup. The drill also found the off-site job had never run (the
timer, the alert unit and the `coach-data` group were never installed, and the bucket was
empty); they were installed the same day and the first copy uploaded. Before that: 2026-10-07 on
the desktop (#14), with a seeded database.
