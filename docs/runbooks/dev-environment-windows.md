# Runbook: development environment on Windows (WSL 2)

The desktop moves from Ubuntu to Windows. Development runs inside **WSL 2 (Ubuntu 24.04)**,
so the Makefile, uv, Docker and git behave exactly as before (ADR-0018). Nothing in the repo
changes; only where it runs.

| Piece | Where it runs on Windows |
| --- | --- |
| Repo clone, `make`, uv, Node, git | WSL 2 Ubuntu, in `~/code` (never under `/mnt/c`: slow, breaks file watching) |
| Claude Code | Inside WSL (`claude`), or the Claude desktop app's Code tab with a WSL session |
| Docker (image test builds only) | Docker Desktop with the WSL 2 backend |
| Tailscale | Windows app; WSL reaches the Pi through it |
| Ollama (Vybe) | Native Windows app; the RX 6900 XT runs through Vulkan there (ROCm on Windows doesn't support this card) |

## 1. Windows (once, PowerShell as admin)

```powershell
wsl --install -d Ubuntu-24.04          # reboot when asked, then create the Linux user
powercfg /change standby-timeout-ac 0  # never sleep on mains power
powercfg /hibernate off
```

Settings > Windows Update > Advanced options: set **Active hours** to cover your working day so
updates don't reboot the PC mid-session. Install Tailscale for Windows and Docker Desktop
(Settings > Resources > WSL integration: enable Ubuntu-24.04).

Optional `C:\Users\<you>\.wslconfig` (mirrored networking makes Tailscale and `localhost`
behave the same in WSL and Windows):

```ini
[wsl2]
networkingMode=mirrored
memory=24GB
```

Then `wsl --shutdown` and reopen Ubuntu.

## 2. Inside WSL (once)

```bash
sudo apt update && sudo apt install -y git make build-essential tmux jq curl
curl -LsSf https://astral.sh/uv/install.sh | sh                  # uv (installs to ~/.local, no sudo)
# Node 22 from the NodeSource apt repo, with its signing key (no piped script as root):
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
  | sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt update && sudo apt install -y nodejs
curl -fsSL https://claude.ai/install.sh | bash                    # Claude Code (user install, no sudo)
# GitHub CLI: https://github.com/cli/cli/blob/trunk/docs/install_linux.md
git config --global user.name "Liam Doyle"
git config --global user.email "<github email>"
gh auth login            # GitHub.com > SSH > generate a new key > browser
claude                   # then /login
```

The uv and Claude Code installers are unpinned scripts piped to a shell. That is acceptable on a
personal dev box because both run as your user, not root, and come from the vendors' own
domains. Never pipe a script to `sudo`.

## 3. This repo

```bash
mkdir -p ~/code && cd ~/code
git clone git@github.com:LDoyleDev/training-coach.git && cd training-coach
make setup && make check
```

`.env` is never in git. Copy it from the Ubuntu install or the Pi over Tailscale
(`scp vybe@vybe-pi:~/training-coach/.env .`), never by email or chat. To read files from the
Ubuntu drive without booting it: `wsl --mount <disk> --partition <n>` from an admin PowerShell
(see `wsl --help`).

Keep secrets inside WSL:

- After copying, `chmod 600 .env`.
- Never put `.env` under `/mnt/c`. Every Windows process can read it there, and OneDrive syncs
  Desktop, Documents and Pictures to the cloud.
- `wsl --mount` exposes the whole Ubuntu home folder. Copy only `.env`, then
  `wsl --unmount` straight away.

## 4. Driving Claude Code from the phone

Remote Control keeps Claude running on this PC while you steer it from the Claude app:

```bash
tmux new -s claude
cd ~/code/training-coach
claude remote-control --spawn worktree --name "Desktop"   # space shows a QR code for the phone
# detach: Ctrl-b then d; reattach: tmux attach -t claude
```

- `--spawn worktree` gives each phone-started session its own git worktree, so parallel tasks
  don't edit the same files.
- In Claude Code, `/config`: turn on **Push when actions required** (and optionally **Push when
  Claude decides**).
- In claude.ai settings, turn on **Require trusted devices**.
- The session dies if the PC sleeps for long, reboots, or WSL shuts down. Restart with
  `claude remote-control` in the same folder (within ~4 hours it brings the sessions back).
- Repo-only work does not need the PC at all: start a cloud session at claude.ai/code.

## 5. Gotchas

- Run `make` and Claude Code in WSL, not in PowerShell or Git Bash.
- Line endings: `.gitattributes` forces LF; don't clone into a Windows folder.
- A clean OS install gets a **new Tailscale IP**. Update anything pointing at the old desktop IP
  (for example Vybe's `OLLAMA_HOST`).
- AVG Antivirus's HTTPS scanning re-signs TLS with its own root. Tools that ship their own CA
  bundle reject it when run natively on Windows: use `git config http.sslBackend schannel` and
  `uv sync --system-certs` (or `UV_SYSTEM_CERTS=1`). Inside WSL, fix it the same way if it bites.
