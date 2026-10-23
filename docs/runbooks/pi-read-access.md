# Runbook: read-only access to the Pi

A second SSH key that can only read: the app's status, logs, deploy runs, band import and the
database (read-only). It lets an assistant on the desktop check the live coach without a prompt
each time, while anything that changes the Pi still goes through the normal `vybe-pi` key and is
asked for. About 10 minutes, once.

How it is safe: the Pi ties the key to one command, `~/bin/tc-read` (a copy of
`scripts/pi-read.sh`), in `authorized_keys`. Whatever the client sends arrives in that script as
text and only its fixed subcommands run; `restrict` turns off forwarding and terminals. The
database is opened read-only with `query_only` on and an authorizer that allows only reads, and
secret and binary columns (hashes, tokens, keys, photos) come back empty; only a fixed list of SQL functions runs, and no value may pass 1 MB. Logs are not masked like that: the app keeps secrets out of them (`backend/CLAUDE.md`, Logging) and the helper redacts query strings, Telegram bot tokens, bearer headers and ingest secrets on top. A secret stored under a harmless column name, or inside a JSON column, would not be masked; `backend/tests/test_pi_read.py` checks the models by name. Deploys don't update the installed copy:
widening what the key can do is a deliberate copy, never a side effect of a release.

## 1. The key (desktop, PowerShell)

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519_tc_read -C "tc-read"
ssh-add $env:USERPROFILE\.ssh\id_ed25519_tc_read
```

Give it a passphrase; the Windows ssh-agent remembers it. Add to `C:\Users\<you>\.ssh\config`:

```
Host tc-read
    HostName vybe-pi.local
    User vybe
    IdentityFile ~/.ssh/id_ed25519_tc_read
    IdentitiesOnly yes
    ServerAliveInterval 30
    ServerAliveCountMax 4
```

The alias deliberately doesn't start with `vybe-pi`, so a permission rule written for `vybe-pi`
can't match it by prefix.

## 2. The script and the key on the Pi (desktop, PowerShell)

From a checkout of this repo:

```powershell
ssh vybe-pi "mkdir -p ~/bin"
scp scripts\pi-read.sh vybe-pi:bin/tc-read
scp $env:USERPROFILE\.ssh\id_ed25519_tc_read.pub vybe-pi:tc-read.pub
ssh vybe-pi
```

Then, on the Pi:

```bash
chmod 755 ~/bin/tc-read
printf 'restrict,command="%s/bin/tc-read" %s\n' "$HOME" "$(cat ~/tc-read.pub)" >> ~/.ssh/authorized_keys
rm ~/tc-read.pub
tail -1 ~/.ssh/authorized_keys   # restrict,command="/home/vybe/bin/tc-read" ssh-ed25519 AAAA... tc-read
exit
```

## 3. Check it (desktop)

```powershell
ssh tc-read status
ssh tc-read band
ssh tc-read logs 2h ingest
ssh tc-read sql "SELECT local_date, status FROM workouts ORDER BY id DESC LIMIT 3"
ssh tc-read sql "DELETE FROM workouts"     # refused: only SELECT, WITH or a schema PRAGMA
ssh tc-read "cat /etc/passwd"              # prints the help: nothing else runs
```

## 4. Let the assistant use it

In `~/.claude/settings.json`, under `permissions.allow` (keep the `ask` rule for `vybe-pi`):

```json
"Bash(/c/Windows/System32/OpenSSH/ssh.exe tc-read:*)"
```

Changes to live data still need an OK in chat and go through `vybe-pi`
(`docs/runbooks/backup-restore.md` first).

## Updating or removing

- New subcommand: change `scripts/pi-read.sh` in a PR, then copy it again (step 2's `scp` line).
- Remove: delete the `tc-read` line from `~/.ssh/authorized_keys` on the Pi, and the key on the
  desktop (`ssh-add -d`, then the two `id_ed25519_tc_read` files).
