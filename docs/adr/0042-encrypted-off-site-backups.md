# ADR-0042: Encrypted off-site backups on Cloudflare R2, kept 35 days

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam (security review)

## Context

Backups are complete copies of the database, which now holds measurements and progress photos
(ADR-0039). They were plaintext on the Pi and the desktop, the desktop copy was never pruned,
and both machines are in the same home: a fire or theft takes every copy. A deletion in the app
never left the backups. The project spends nothing (cost discipline).

## Decision

- **Encrypt with age to a dedicated backup key** on the Pi, so the Pi can't read its own
  off-site copies and a leaked bucket token exposes nothing readable. The private key's master
  copy is in Liam's password manager, with a working copy on Windows. Not the Linux desktop's
  sops key: the desktop dual-boots, so a key on one side is out of reach from the other.
- **Off-site on Cloudflare R2** (free tier: 10 GB, no egress fees; already the DNS provider), in a
  bucket with a token limited to it, uploaded by `rclone` from a nightly systemd timer
  (`scripts/offsite-backup.sh`) after the app's 03:30 backup. The token lives in a mode-600 file
  outside the app's `.env`: the app container never needs it.
- **35 days** off-site and on the desktop (`pull-backup.sh` now prunes nightly copies); the Pi
  keeps its own 7 daily + 4 weekly. A deletion leaves every copy within about five weeks.
- Failures are loud: a stale backup, a missing tool, a loose settings file or a missing upload
  stop the run, which `systemctl --failed` and the journal show.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| age + R2 (chosen) | Free; client-side encryption; no egress fees | One more token to keep |
| age + Backblaze B2 | Free 10 GB; separate from Cloudflare | Another account; egress limits |
| Encrypt in the app (pyrage) | One process | A new dependency; the app would hold the bucket token |
| Desktop copy only | Nothing new | Same building as the Pi; plaintext; unbounded |

## Consequences

- Restoring from off-site needs the backup key's private half: losing it loses those copies.
- A failed run alerts on Telegram through an `OnFailure=` unit (#168; deploy runbook).
