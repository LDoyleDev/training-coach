# Developing on the Windows desktop

The toolchain (`make`, `uv`, Node) is Linux-first. On the Windows desktop two things get in the
way, both caused by AVG Antivirus:

1. **AVG's HTTPS scanning** re-signs TLS with its own root ("AVG Web/Mail Shield Root"). Tools
   with their own certificate bundles (git's OpenSSL, uv, pip in containers) reject it.
2. **AVG blocks `uv.exe`** from starting (`Access is denied`).

## Fix it properly (recommended)

In AVG: allow `uv.exe` (under `%APPDATA%\Python\Python312\Scripts\` if installed with pip, or
wherever the uv installer put it), and exclude the dev tools from HTTPS scanning, or turn off
HTTPS scanning. Then install GNU make (for example `winget install ezwinports.make`; the
recipes need Git Bash's `sh` on `PATH`) and `make setup` works.

For git over HTTPS, use the Windows certificate store, which trusts AVG's root:
`git config http.sslBackend schannel` (per repo, or `--global`).

## Workaround: run the toolchain in a container

Docker Desktop works. Export AVG's public root certificate and bake it into a dev image:

```powershell
# PowerShell: write AVG's root to avg-root.crt (a public certificate, not a secret)
$c = Get-ChildItem Cert:\LocalMachine\Root, Cert:\CurrentUser\Root |
  Where-Object Subject -like '*AVG Web/Mail Shield Root*' | Select-Object -First 1
"-----BEGIN CERTIFICATE-----`n" + [Convert]::ToBase64String($c.RawData, 'InsertLineBreaks') +
  "`n-----END CERTIFICATE-----" | Set-Content -Encoding ascii avg-root.crt
```

`Dockerfile` next to it (outside the repo):

```dockerfile
FROM node:22-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
COPY avg-root.crt /usr/local/share/ca-certificates/avg-root.crt
RUN update-ca-certificates
ENV UV_SYSTEM_CERTS=1 NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/avg-root.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt UV_PROJECT_ENVIRONMENT=/venv \
    UV_LINK_MODE=copy UV_PYTHON=3.12 UV_CACHE_DIR=/uvcache
RUN uv python install 3.12 && git config --global --add safe.directory '*'
```

Build once, then run any target from the repo root. Named volumes keep the Linux venv and
`node_modules` out of the Windows checkout:

```bash
docker build -t tc-dev .
docker run --rm -v "$PWD:/src" -v tc-venv:/venv -v tc-uvcache:/uvcache \
  -v tc-node-modules:/src/frontend/node_modules -w /src tc-dev make check
```

In Git Bash, prefix the `docker run` with `MSYS_NO_PATHCONV=1`. The first run needs
`make setup` (or `cd backend && uv sync` and `cd frontend && npm ci`) inside the container.
Git hooks installed this way won't run from Windows git, so CI is the backstop.
