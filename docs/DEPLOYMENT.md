# Production Deployment Guide

This guide walks a non-expert through deploying **EGI** (Emergencia · Gente · Info)
to a public, internet-reachable server in **under two hours**. EGI is an
offline-first family-reunification system: a single Python + FastAPI server backed
by SQLite (WAL mode) that also serves the web app (PWA). There is one server
directory (`server/`), one database file, and an `egi` operator CLI.

> EGI may hold sensitive personal data (names, contacts, locations of people in a
> crisis). Treat deployment as a privacy-critical task. Use HTTPS, lock down
> access, collect the minimum, and read the
> [Security Checklist](SECURITY_CHECKLIST.md) before going public.

Everything below is command-first and copy-pasteable. Commands assume a fresh
**Ubuntu 22.04 / Debian 12** host unless noted.

---

## 1. Target platforms

EGI runs anywhere Python 3.10+ runs. The most common targets:

| Platform | Best for | Notes |
|----------|----------|-------|
| **Self-hosted VPS** (Ubuntu/Debian + systemd) | Most community deployments | Canonical path in this guide |
| **Docker / Docker Compose** | Reproducible, portable deploys | See [Section 9](#9-docker--docker-compose) |
| **Raspberry Pi / low-power** | Local/community hosting, on-site at a shelter | Works on a Pi 3/4/5; see [Section 13](#13-raspberry-pi--low-power-notes) |
| **Cloud** (Hetzner, DigitalOcean, AWS Lightsail) | Pay-as-you-go VPS | Any of these is just an Ubuntu VPS; same steps |

**Cloud quick picks** (all map to the VPS steps below):

- **Hetzner Cloud** — `CX22` (2 vCPU / 4 GB) is generous; the smallest shared
  instance is plenty for a small deployment.
- **DigitalOcean** — Basic Droplet, **1 GB / 1 vCPU**, Ubuntu 22.04.
- **AWS Lightsail** — `$5`/mo plan (1 GB / 2 vCPU), Ubuntu 22.04 blueprint.

Pick the region closest to the affected community to reduce latency on poor
connections.

---

## 2. Minimal server requirements

For a small deployment (one community, thousands of records):

- **1 vCPU**
- **1 GB RAM**
- **10 GB disk**
- A domain name pointed at the server's IP (an `A` record) for HTTPS.

That is enough for FastAPI + SQLite + the static frontend. Scale RAM/CPU up only
if you enable on-device OCR/LLM (Tesseract is light; a local Ollama model is
**not** — see [Section 3](#3-install-system-dependencies)) or expect heavy load.

Disk grows mainly from uploaded photos (if enabled) and backups. Budget more disk
if `ENABLE_PHOTOS=true`.

---

## 3. Install system dependencies

SSH into the server as a sudo-capable user, then:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

EGI requires **Python 3.10+** (the repo targets **3.11**). Check:

```bash
python3 --version   # must be 3.10 or newer
```

### Tesseract OCR (required for paper import)

```bash
sudo apt install -y tesseract-ocr
# Optional language packs, e.g. Spanish:
sudo apt install -y tesseract-ocr-spa
tesseract --version
```

If `tesseract` is on `PATH` (it is, after the above), leave `TESSERACT_CMD=tesseract`
in `.env`. If you installed it elsewhere, point `TESSERACT_CMD` at the binary.

### Node.js (to build the frontend)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # v20.x
```

### Ollama (optional — local LLM for OCR/AI extraction)

EGI works fully **without** any LLM. If `LLM_MODEL` is unset, OCR records are
created with raw text only and completed by a moderator. Only install Ollama if
you want local AI extraction and have the RAM/CPU for it (a small model wants
several extra GB of RAM):

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b
```

Then set `AI_PROVIDER=ollama` and `AI_MODEL=llama3.1:8b` in `.env`, or use a
hosted provider (e.g. `LLM_MODEL=openai/gpt-4o-mini` plus `OPENAI_API_KEY`).
For a 1 GB RAM box, **skip Ollama** and use a hosted provider or no LLM at all.

---

## 4. Get the code and build the frontend

Clone the repo (adjust the URL to your fork/mirror) into a stable location:

```bash
sudo mkdir -p /opt/egi
sudo chown "$USER" /opt/egi
git clone https://github.com/your-org/EGI.git /opt/egi
cd /opt/egi
```

### Python environment

```bash
cd /opt/egi/server
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note on Prompture.** `requirements.txt` installs Prompture as an editable
> local install from a Windows path (`-e C:/Users/Juan/...`). On a Linux server
> that line will fail. Edit `requirements.txt` (or use a deployment-specific
> requirements file) to point at your clone of Prompture, e.g.
> `-e /opt/prompture`, or install it from your package index. Clone Prompture
> alongside EGI first if you rely on OCR LLM extraction.

### Build the frontend

The FastAPI server serves the built PWA from `FRONTEND_DIR`. Build it once:

```bash
cd /opt/egi/frontend
npm install
npm run build        # outputs frontend/dist/
```

This produces `/opt/egi/frontend/dist/`. Point the server at it via `.env`:

```ini
FRONTEND_DIR=../frontend/dist
```

`FRONTEND_DIR` is resolved relative to `server/` by default, so the value above
works when the server runs from `/opt/egi/server`. You can also set an absolute
path (`FRONTEND_DIR=/opt/egi/frontend/dist`).

### Initialize the database

```bash
cd /opt/egi/server
source .venv/bin/activate
python -m db          # creates ./data/egi.db (idempotent)
```

`python -m db` is safe to run repeatedly — it also runs automatically on startup.

---

## 5. Configure `.env` for production

Create `server/.env` from the example and edit it:

```bash
cd /opt/egi/server
cp .env.example .env
nano .env
```

### Core settings

```ini
PORT=3000
DB_PATH=./data/egi.db
UPLOAD_DIR=./uploads
FRONTEND_DIR=../frontend/dist
TESSERACT_CMD=tesseract

# Optional LLM extraction (leave commented/unset for raw-text-only OCR).
# LLM_MODEL=openai/gpt-4o-mini
# AI_PROVIDER=ollama
# AI_MODEL=llama3.1:8b
```

### Production security settings

These variables harden a public deployment. **Set all of them before exposing the
server to the internet.**

```ini
# Mark the environment as production (enables strict defaults).
ENV=production

# Comma-separated list of allowed browser origins (CORS).
# Use your real domain(s). NEVER use "*" in production.
ALLOWED_ORIGINS=https://egi.example.com

# Bearer tokens for moderators/operators (comma-separated).
# Generate one per operator with the command shown below. Keep them secret.
OPERATOR_TOKENS=PASTE_A_GENERATED_TOKEN_HERE,PASTE_ANOTHER_FOR_A_SECOND_OPERATOR

# Photo uploads are privacy-sensitive. Off by default; enable only if you
# have a clear policy for handling and removing photos.
ENABLE_PHOTOS=false

# Rate limiting: max requests per window (seconds) per client IP.
RATE_LIMIT_MAX=120
RATE_LIMIT_WINDOW=60
# IPs exempt from rate limiting (e.g. a trusted relay or the reverse proxy).
RATE_LIMIT_TRUSTED_IPS=127.0.0.1
```

#### Generate secure operator tokens

Run this once **per moderator** and paste the output into `OPERATOR_TOKENS`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Each token is a long random string. Moderators present it as a bearer token
(`Authorization: Bearer <token>`) when calling moderation/admin endpoints. Rotate
tokens by editing `.env` and restarting the service. Never share them in chat,
screenshots, or commits.

> ### Never commit `.env`
>
> `.env` contains operator tokens and API keys. It must **never** be committed to
> git or copied into a Docker image layer. Confirm it is ignored:
>
> ```bash
> grep -q "^\.env$\|/\.env$\|\*\*/\.env" /opt/egi/.gitignore && echo "ignored" || echo "ADD .env TO .gitignore"
> ```
>
> Keep `.env` readable only by the service user:
>
> ```bash
> chmod 600 /opt/egi/server/.env
> ```

---

## 6. Run the server with uvicorn behind systemd

In production, run uvicorn bound to **localhost only** (`127.0.0.1`) and put a
reverse proxy in front of it (Section 7). Never expose port 3000 publicly.

### Create a dedicated non-root user

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin egi
sudo chown -R egi:egi /opt/egi
```

The `egi` user owns the code, the venv, `data/`, and `uploads/`. Running as a
dedicated non-root user limits the blast radius if the process is compromised.

> If you cloned/built as your own user, re-run the `chown` above so the `egi`
> user can read the code and write `data/`, `uploads/`, and the WAL files.

### systemd unit file

Create `/etc/systemd/system/egi.service`:

```ini
[Unit]
Description=EGI sync server (FastAPI + SQLite)
After=network.target

[Service]
Type=simple
User=egi
Group=egi
WorkingDirectory=/opt/egi/server
EnvironmentFile=/opt/egi/server/.env
ExecStart=/opt/egi/server/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 3000
Restart=on-failure
RestartSec=3

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/opt/egi/server/data /opt/egi/server/uploads

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now egi
sudo systemctl status egi          # should show "active (running)"
journalctl -u egi -f               # live logs (Ctrl-C to exit)
```

Confirm it responds locally:

```bash
curl http://127.0.0.1:3000/health
```

> **Workers:** the default single uvicorn process is fine for a 1 vCPU box. SQLite
> + WAL handles concurrent reads well. If you later add workers
> (`--workers N`), all workers share the same SQLite file — keep the file on
> local disk (not a network mount) to avoid locking problems.

---

## 7. Reverse proxy with HTTPS (Let's Encrypt)

Pick **one** of the two options below. Both terminate TLS on 443 and proxy to
`127.0.0.1:3000`. Point your domain's `A` record at the server first.

### Option A — Caddy (automatic HTTPS, simplest)

Caddy obtains and renews Let's Encrypt certificates automatically.

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

Edit `/etc/caddy/Caddyfile`:

```caddyfile
egi.example.com {
    encode gzip
    reverse_proxy 127.0.0.1:3000
}
```

Reload Caddy. It will fetch a certificate on first request:

```bash
sudo systemctl reload caddy
```

That's it — `https://egi.example.com` is live with auto-renewing TLS.

### Option B — nginx + Certbot

```bash
sudo apt install -y nginx
```

Create `/etc/nginx/sites-available/egi`:

```nginx
server {
    listen 80;
    server_name egi.example.com;

    # Allow large-ish OCR image uploads (tune to your needs).
    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and add HTTPS with Certbot (it rewrites the block to listen on 443
and sets up auto-renewal):

```bash
sudo ln -s /etc/nginx/sites-available/egi /etc/nginx/sites-enabled/egi
sudo nginx -t && sudo systemctl reload nginx

sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d egi.example.com --redirect --agree-tos -m you@example.com
```

Certbot auto-renews via a systemd timer. Test renewal:

```bash
sudo certbot renew --dry-run
```

> Keep `ALLOWED_ORIGINS` in `.env` matching the public HTTPS origin
> (`https://egi.example.com`). A mismatch causes the browser app to fail CORS.

---

## 8. Firewall (ufw)

Allow SSH and web traffic; block the app port from the public internet.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP (Let's Encrypt challenge + redirect)
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable
sudo ufw status verbose
```

**Do not** open port 3000. It is reachable only on `127.0.0.1` via the reverse
proxy. If your cloud provider has its own firewall/security group (AWS Lightsail,
DigitalOcean Cloud Firewall, Hetzner Firewall), apply the same rules there too:
allow 22/80/443, deny 3000.

---

## 9. Docker / Docker Compose

Prefer containers? The snippets below are illustrative — copy them into a
`Dockerfile` and `docker-compose.yml` at the repo root. They build the frontend
inside the image and run uvicorn. `data/` and `uploads/` are mounted as host
volumes so your database and photos survive container rebuilds.

> Remember the Prompture caveat from [Section 4](#4-get-the-code-and-build-the-frontend):
> the editable Windows path in `requirements.txt` won't resolve in a Linux
> container. Vendor Prompture into the build context or adjust the path before
> building.

### `Dockerfile`

```dockerfile
# ---- Stage 1: build the frontend ----
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build        # -> /app/frontend/dist

# ---- Stage 2: runtime ----
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/server
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist

ENV FRONTEND_DIR=/app/frontend/dist \
    DB_PATH=/app/server/data/egi.db \
    UPLOAD_DIR=/app/server/uploads

EXPOSE 3000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
```

Inside the container uvicorn binds `0.0.0.0` so Docker can route to it; the
reverse proxy (or Compose port mapping) still controls public exposure.

### `docker-compose.yml`

```yaml
services:
  egi:
    build: .
    restart: unless-stopped
    # Bind to localhost only; put nginx/Caddy in front for HTTPS.
    ports:
      - "127.0.0.1:3000:3000"
    env_file:
      - ./server/.env
    volumes:
      - ./server/data:/app/server/data
      - ./server/uploads:/app/server/uploads
```

```bash
docker compose up -d --build
docker compose logs -f
curl http://127.0.0.1:3000/health
```

The DB is initialized automatically on startup; to run it explicitly:

```bash
docker compose exec egi python -m db
```

Put Caddy or nginx (Section 7) in front of `127.0.0.1:3000` exactly as for the
bare-metal setup. Keep `.env` out of the image — it is mounted at runtime via
`env_file`, never `COPY`-ed in.

---

## 10. Backups

EGI's state is just two things: the SQLite database (`server/data/`) and uploaded
files (`server/uploads/`). Back up both, regularly, off the server.

Use the operator CLI (introduced in Phase 7), which writes a timestamped tarball
of `data/` + `uploads/`:

```bash
cd /opt/egi
egi backup                     # -> e.g. backups/egi-backup-2026-06-26T0300Z.tar.gz
```

> The `egi` CLI is installed with `pip install -e .` from the repo root and always
> targets the same DB as the running server (it loads `server/.env`). See
> `egi_cli/` and the [README](../README.md) for the full command list.

### Nightly cron

Edit the service user's crontab (or root's) to back up every night at 03:00 and
keep the last 14 archives:

```bash
sudo crontab -u egi -e
```

```cron
# Nightly EGI backup at 03:00, prune archives older than 14 days.
0 3 * * * cd /opt/egi && /opt/egi/server/.venv/bin/egi backup >> /var/log/egi-backup.log 2>&1 && find /opt/egi/backups -name 'egi-backup-*.tar.gz' -mtime +14 -delete
```

> **Get backups off the box.** A backup on the same disk does not survive disk
> loss. Copy archives to object storage or another host, e.g.
> `rclone copy /opt/egi/backups remote:egi-backups` after the backup runs. Because
> backups contain sensitive personal data, store them **encrypted** and access-controlled.

### Restore

Stop the service, extract the tarball over `server/`, then restart:

```bash
sudo systemctl stop egi
tar -xzf /opt/egi/backups/egi-backup-XXXX.tar.gz -C /opt/egi/server
sudo chown -R egi:egi /opt/egi/server/data /opt/egi/server/uploads
sudo systemctl start egi
```

> SQLite WAL note: prefer backing up while the service is stopped, or rely on
> `egi backup` (which copies the DB safely). Avoid copying `egi.db` alone while the
> server is writing — grab `egi.db`, `egi.db-wal`, and `egi.db-shm` together if you
> ever copy by hand.

---

## 11. Upgrade procedure

Upgrades are pull → reinstall → rebuild → migrate → restart. Always back up first.

```bash
cd /opt/egi
egi backup                                   # 0. snapshot before upgrading
sudo systemctl stop egi                      # optional but safest

git pull                                      # 1. get new code

source server/.venv/bin/activate              # 2. reinstall Python deps
pip install -r server/requirements.txt

cd frontend && npm install && npm run build   # 3. rebuild the PWA
cd ../server

python -m db                                  # 4. apply migrations (idempotent)

sudo systemctl start egi                      # 5. restart
sudo systemctl status egi
curl http://127.0.0.1:3000/health
```

`python -m db` is idempotent — it creates missing tables and is safe to run on
every upgrade. If you build/pull as a different user, re-run
`sudo chown -R egi:egi /opt/egi` before restarting so the service user can read
the new files.

For Docker: `git pull && docker compose up -d --build`.

---

## 12. Security must-dos before going public

Do not skip these. Full details and the complete list are in the
[Security Checklist](SECURITY_CHECKLIST.md).

- [ ] `ENV=production` is set.
- [ ] `ALLOWED_ORIGINS` lists your real HTTPS origin(s) — **never `*`**.
- [ ] `OPERATOR_TOKENS` are generated with `secrets.token_urlsafe(32)`, unique
      per operator, and kept secret.
- [ ] `.env` is `chmod 600`, owned by the `egi` user, and **never committed**.
- [ ] HTTPS is enforced (Caddy auto / Certbot `--redirect`); plain HTTP redirects to HTTPS.
- [ ] uvicorn binds `127.0.0.1` only; **port 3000 is not publicly reachable**.
- [ ] Firewall allows 22/80/443 and blocks 3000 (ufw **and** any cloud firewall).
- [ ] Rate limiting is on (`RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW`); `RATE_LIMIT_TRUSTED_IPS` is minimal.
- [ ] `ENABLE_PHOTOS=false` unless you have a clear photo-handling/removal policy.
- [ ] Nightly backups run and are copied off the server, encrypted.
- [ ] The server runs as the non-root `egi` user.
- [ ] No analytics/tracking added; unverified reports stay visibly unverified
      (see the privacy principles in the [README](../README.md)).

---

## 13. Raspberry Pi / low-power notes

EGI runs well on a Raspberry Pi 3/4/5 or similar low-power board — useful for
hosting on-site at a shelter or community center.

- Use **Raspberry Pi OS (64-bit)** or Ubuntu Server for arm64. The Python +
  FastAPI + SQLite steps are identical to Sections 3–6.
- Tesseract installs the same way: `sudo apt install -y tesseract-ocr`.
- **Skip Ollama** on a Pi — local LLMs are too heavy. Leave `LLM_MODEL` unset
  (OCR keeps raw text for manual completion) or use a hosted provider when online.
- Prefer a good-quality **SSD over an SD card** for the SQLite database; SD cards
  wear out under write load and can corrupt the DB. If you must use an SD card,
  back up frequently.
- For purely local/offline use you can skip Let's Encrypt and run behind a LAN
  hostname, but then browsers will warn about the missing certificate. For any
  internet-facing Pi, use Caddy (Section 7) — it handles HTTPS with one line.

---

## Troubleshooting quick reference

| Symptom | Check |
|---------|-------|
| `systemctl status egi` shows failed | `journalctl -u egi -e` — usually a bad path, missing venv, or import error |
| Web app loads but API calls fail (CORS) | `ALLOWED_ORIGINS` must match the browser origin exactly, scheme included |
| 502 from nginx/Caddy | uvicorn not running or not on `127.0.0.1:3000`; `curl http://127.0.0.1:3000/health` |
| Blank page / 404 for the app | `FRONTEND_DIR` wrong or `npm run build` not run; rebuild and check `frontend/dist` exists |
| OCR import does nothing | Tesseract not installed or `TESSERACT_CMD` wrong; run `tesseract --version` |
| `pip install` fails on Prompture | Fix the editable path in `requirements.txt` for this host (see Section 4) |

---

EGI is a community coordination tool, not a replacement for emergency services.
Deploy responsibly, protect the data, and keep the [Security Checklist](SECURITY_CHECKLIST.md)
handy.
