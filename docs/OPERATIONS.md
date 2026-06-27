# EGI Operations Manual

This is the **runbook** for keeping a live EGI server healthy. It is written for a
community volunteer who is *not* a systems expert. If something is broken, start at
the [On-call checklist](#1-on-call-checklist-first-5-minutes) and work down.

EGI is a single Python + FastAPI server backed by SQLite (WAL mode) that also
serves the web app. Deployment (how to install it in the first place) lives in
[DEPLOYMENT.md](DEPLOYMENT.md); this document is about **running it day to day and
recovering when it breaks**.

> EGI holds sensitive personal data (names, contacts, locations of people in a
> crisis). Every action below — especially logs, backups, and credential rotation —
> must protect that data. Never paste record content into chat or tickets.

Useful one-liners assume the server answers on `http://127.0.0.1:3000` (behind your
Caddy/nginx reverse proxy). From another machine, use your public HTTPS URL
instead, e.g. `https://egi.example.com`.

---

## 1. On-call checklist (first 5 minutes)

When you get an alert or a "the site is down" report, do these in order. Stop as
soon as you find the cause.

1. **Is the app up at all?**
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/health
   ```
   - `200` → app is healthy; the problem may be the proxy/DNS/TLS, not EGI.
   - `503` → app is running but a health check is failing (see step 3).
   - connection refused / timeout → the process is down (step 2).

2. **Is the service running?**
   ```bash
   sudo systemctl status egi          # systemd deployments
   # or, for Docker:
   docker compose ps
   ```
   If it is dead, look at the last lines of the log (step 4) before restarting:
   ```bash
   sudo systemctl restart egi
   ```

3. **What does `/health` actually say?**
   ```bash
   curl -s http://127.0.0.1:3000/health | python3 -m json.tool
   ```
   Look at `checks.database`, `checks.uploads_dir`, `checks.sync_queue`. A `fail`
   tells you which subsystem to chase (database file gone, disk full, etc. — see
   the [common incidents table](#10-common-incidents)).

4. **Read the most recent logs** (they are structured JSON):
   ```bash
   sudo journalctl -u egi -n 100 --no-pager        # systemd
   docker compose logs --tail=100 egi              # Docker
   ```
   Grab the `request_id` of any `ERROR` line — you can trace the whole request
   with it (see [§4](#4-reading-structured-logs--tracing-by-request_id)).

5. **Check the metrics for a smoking gun:**
   ```bash
   curl -s http://127.0.0.1:3000/metrics | grep -E '^egi_'
   ```
   High `egi_http_requests_total{status="5.."}`, a stale
   `egi_backup_last_success_timestamp`, a growing `egi_pending_moderation_total`,
   or a near-limit `egi_db_size_bytes` each point at a different playbook below.

If after 5 minutes you have not found it: restart the service (it is safe — the DB
is durable), confirm `/health` returns `200`, and then keep investigating with the
logs. **Restarting EGI never loses committed data.**

---

## 2. Health and readiness endpoints

EGI exposes three operational endpoints (`/health`, `/ready`, `/metrics`). None of
them contain personal data, so they are safe to scrape and to share with an ops
team. Metrics get their own section ([§3](#3-metrics-endpoint-metrics)).

### `GET /health` — is the app working *right now*?

Returns structured JSON and a **`503`** status if any critical check fails (so a
load balancer or uptime monitor can act on it).

```bash
curl -s http://127.0.0.1:3000/health | python3 -m json.tool
```

Healthy response (HTTP `200`):

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "checks": {
    "database":    {"status": "pass", "response_ms": 3},
    "uploads_dir": {"status": "pass", "free_bytes": 10737418240},
    "sync_queue":  {"status": "pass", "pending": 0}
  }
}
```

Unhealthy response (HTTP `503`) — note `status: "unhealthy"` and which check failed:

```json
{
  "status": "unhealthy",
  "version": "0.1.0",
  "checks": {
    "database":    {"status": "fail", "error": "unable to open database file"},
    "uploads_dir": {"status": "pass", "free_bytes": 52428800},
    "sync_queue":  {"status": "pass", "pending": 0}
  }
}
```

- **`database` fail** → the SQLite file is missing, locked, or the disk is read-only.
- **`uploads_dir` fail / low `free_bytes`** → disk is (nearly) full; `free_bytes`
  is checked against `MIN_FREE_BYTES` (default 100 MB).
- **`sync_queue` pending climbing** → records are queued but not draining.

### `GET /ready` — has startup finished?

Returns `200` only after the database is initialized and the app is ready to serve.
Use it for container/systemd/Caddy **readiness** probes so traffic isn't sent
before startup completes.

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/ready   # 200 when ready
```

---

## 3. Metrics endpoint (`/metrics`)

`GET /metrics` returns plain-text Prometheus exposition format. Point a Prometheus
scrape at it (see
[deploy/prometheus-alerts.yml](../deploy/prometheus-alerts.yml) for the scrape
config and alert rules).

```bash
curl -s http://127.0.0.1:3000/metrics | grep -E '^egi_'
```

Key metrics and what they mean:

| Metric | Meaning |
|--------|---------|
| `egi_build_info` | Version/build labels (always `1`). |
| `egi_http_requests_total{method,route,status}` | Request counter — error rate comes from the `status="5.."` series. |
| `egi_http_request_duration_seconds` | Request latency histogram (use for p95). |
| `egi_sync_records_total{direction}` | Sync volume in/out. |
| `egi_sync_log_records_total{direction}` | Sync-log rows in/out. |
| `egi_db_size_bytes` | SQLite file size — **plan a Postgres move past ~5 GB**. |
| `egi_pending_moderation_total` | Records awaiting moderation (backlog signal). |
| `egi_messages_pending_total{channel}` | Undelivered messages per channel. |
| `egi_pending_duplicates_total` | Unresolved duplicate clusters. |
| `egi_backup_last_success_timestamp` | Unix time of the last successful backup — **stale = backups are failing**. |

---

## 4. Reading structured logs & tracing by request_id

In production EGI logs **one JSON object per line** (`LOG_FORMAT=json`, the
default in production; set `LOG_FORMAT=text` for human-readable local dev). Each
request line includes `timestamp`, `method`, `path`, `status`, `duration_ms`,
`client_ip`, `user_id` (if authenticated), and a `request_id`.

View them where your platform sends stdout:

```bash
sudo journalctl -u egi -f                 # systemd, live
docker compose logs -f egi                # Docker, live
```

Because they are JSON, you can filter with `jq` without fragile regexes:

```bash
# Only errors:
sudo journalctl -u egi -o cat | jq 'select(.level=="ERROR")'

# Slowest requests over 1s:
sudo journalctl -u egi -o cat | jq 'select(.duration_ms > 1000)'
```

### Trace one request end to end

Every request carries a `request_id`. It is also returned to the client in the
**`X-Request-ID`** response header, so a user reporting an error can give you the
exact ID:

```bash
# See the ID the server assigns to a call:
curl -s -D - http://127.0.0.1:3000/health -o /dev/null | grep -i x-request-id
```

Then pull every log line for that request:

```bash
sudo journalctl -u egi -o cat | jq 'select(.request_id=="<paste-id-here>")'
```

This stitches together the inbound request line, any warnings, and the final
status/duration — the fastest way to understand a single failed moderation,
login, or sync.

> Logs never contain full bearer tokens or passwords. If you ever see a secret in
> a log line, treat it as a breach and go to [§9](#9-rotate-credentials-after-a-suspected-breach).

### Consolidated audit log

For *who did what* (not raw request traffic), use the operator-gated audit
endpoint, which merges the action log and record history:

```bash
curl -s -H "Authorization: Bearer $OPERATOR_TOKEN" \
  "http://127.0.0.1:3000/audit/log?source=all&limit=50" | python3 -m json.tool
```

Filters: `source=all|actions|history`, `actor`, `action`, `target_type`,
`person_id`, `since`, `limit`, `offset`. Add `?format=export` to download the
matching entries as a JSON file for long-term retention.

---

## 5. Backups

EGI's entire state is the SQLite database plus the `uploads/` directory. `egi
backup` writes a single timestamped, integrity-checked `.tar.gz` of both. See
[DEPLOYMENT.md §10](DEPLOYMENT.md#10-backups) for the install-time setup; this
section covers operating them.

### How automated backups work

Install a nightly timer/cron with the helper (it just **prints** a ready-to-paste
snippet — nothing is installed automatically):

```bash
egi schedule-backup --mode systemd --time 03:30   # prints a systemd timer + service
egi schedule-backup --mode cron   --time 03:30    # prints a crontab line instead
```

Paste the systemd output into `/etc/systemd/system/egi-backup.{service,timer}`,
then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now egi-backup.timer
systemctl list-timers egi-backup.timer            # confirm next run
```

The scheduled job runs `egi backup --retention-days 7`, which:
- checkpoints the WAL and runs `PRAGMA integrity_check` before archiving,
- prunes local archives older than the retention window,
- encrypts the tarball if `BACKUP_ENCRYPT_KEY` is set (or `--encrypt` is passed),
- uploads offsite if `BACKUP_S3_ENDPOINT` / `BACKUP_S3_BUCKET` are set.

### Verify the last backup actually succeeded

Do not trust "the cron is installed" — trust the metric. Every successful backup
stamps `egi_backup_last_success_timestamp` (Unix seconds):

```bash
curl -s http://127.0.0.1:3000/metrics | grep egi_backup_last_success_timestamp
# Compare to now; if it is older than ~24h, backups are failing.
date +%s
```

The Prometheus alert `EGIBackupFailing` fires automatically when this value is
more than 24h old. If it is stale: check the backup log
(`server/backups/backup.log` or `journalctl -u egi-backup`), confirm disk space,
and run `egi backup` by hand to see the error.

### Encryption key storage — read this

> **Store `BACKUP_ENCRYPT_KEY` somewhere SEPARATE from the backups themselves.**
> An encrypted tarball sitting next to its key is not encrypted in any meaningful
> way. Keep the key in a password manager / secrets vault, *not* on the backup
> disk, *not* in the same object-storage bucket, and *not* in git. If you lose the
> key, encrypted backups are unrecoverable — so make sure at least one trusted
> operator also has it.

---

## 6. Restore from backup

Restoring **overwrites** the live database and uploads. Stop the server first.

```bash
sudo systemctl stop egi                 # (or: docker compose stop egi)
egi restore /opt/egi/server/backups/egi-backup-XXXX.tar.gz --confirm
sudo systemctl start egi
curl -s http://127.0.0.1:3000/health | python3 -m json.tool
```

`egi restore`:
- decrypts the archive first if it ends in `.enc` (using `BACKUP_ENCRYPT_KEY`),
- verifies integrity, restores the DB and uploads, and runs `PRAGMA
  integrity_check` on the restored DB (it warns loudly if that fails).

Without `--confirm` it prints what it *would* overwrite and exits without changing
anything — use that as a dry run. **Target: a full restore in under 10 minutes.**

### Quarterly restore drill (do not skip)

A backup you have never restored is not a backup. Once a quarter, prove it works
**without touching production**:

1. Pick a scratch directory and restore the latest backup into it:
   ```bash
   mkdir -p /tmp/egi-drill/data /tmp/egi-drill/uploads
   DB_PATH=/tmp/egi-drill/data/egi.db \
   UPLOAD_DIR=/tmp/egi-drill/uploads \
   egi restore /opt/egi/server/backups/egi-backup-LATEST.tar.gz --confirm
   ```
   (Overriding `DB_PATH`/`UPLOAD_DIR` keeps the live DB untouched.)
2. Boot a throwaway server against the scratch dir on a spare port:
   ```bash
   cd /opt/egi/server
   DB_PATH=/tmp/egi-drill/data/egi.db UPLOAD_DIR=/tmp/egi-drill/uploads \
     .venv/bin/uvicorn main:app --host 127.0.0.1 --port 3999
   ```
3. Verify it is healthy and the data is there:
   ```bash
   curl -s http://127.0.0.1:3999/health | python3 -m json.tool   # expect "healthy"
   curl -s http://127.0.0.1:3999/persons | python3 -m json.tool   # expect real records
   ```
4. Stop the throwaway server, delete `/tmp/egi-drill`, and **record the drill
   date and result** (in your ops log / wiki). If it failed, fix backups *now* —
   not during a real outage.

---

## 7. Scaling up (CPU/RAM) and moving to PostgreSQL

EGI on SQLite is comfortable for a single community (thousands to tens of
thousands of records). Scale in this order:

### Scale the box first (vertical)

Symptoms: high latency under load, p95 climbing, CPU pinned.

1. Note current size and load: `egi_db_size_bytes`, p95 from
   `egi_http_request_duration_seconds`, and `top`/`htop` during a busy period.
2. Resize the VPS (most providers let you bump CPU/RAM with a reboot). 2 vCPU / 4
   GB handles a lot. Do **not** enable a local Ollama LLM on a small box — it is
   the heaviest thing you can add (see DEPLOYMENT.md §3).
3. Only add uvicorn `--workers N` if one core is the bottleneck **and** the DB is
   on local disk (never a network mount) — all workers share the one SQLite file.
4. Make sure backups/uploads disk has headroom (`/health` `free_bytes`,
   `MIN_FREE_BYTES`).

### Move to PostgreSQL (horizontal headroom)

**When:** `egi_db_size_bytes` is approaching **~5 GB**, or you see write-lock
contention under sustained concurrent load that vertical scaling didn't fix. The
alert `EGIDatabaseLarge` is your early warning.

EGI supports PostgreSQL via `DATABASE_URL` (e.g.
`DATABASE_URL=postgresql://egi:secret@localhost:5432/egi`). At a high level:

1. Stand up a PostgreSQL instance and create the `egi` database/user.
2. Back up the SQLite DB first (`egi backup`).
3. Cut over with the migration tooling (`egi sqlite-to-postgres` / `egi migrate`),
   set `DATABASE_URL` in `.env`, and restart.
4. Verify `/health` `database` check passes and `/persons` returns the expected
   records.

Existing SQLite deployments keep working unchanged — Postgres is opt-in. See the
plan's Postgres-migration phase for the detailed cutover steps before you start.

---

## 8. Block an abusive IP

EGI has built-in per-IP rate limiting (`RATE_LIMIT_MAX` writes per
`RATE_LIMIT_WINDOW` seconds; `RATE_LIMIT_TRUSTED_IPS` exempts your proxy/relays).
Tighten those first for broad abuse. To hard-block a single offender, do it at the
edge — cheaper than letting traffic reach the app.

**Caddy** (`/etc/caddy/Caddyfile`):

```caddyfile
egi.example.com {
    @blocked remote_ip 203.0.113.7 198.51.100.0/24
    respond @blocked "Forbidden" 403
    encode gzip
    reverse_proxy 127.0.0.1:3000
}
```
```bash
sudo systemctl reload caddy
```

**nginx** (inside the `server { … }` block):

```nginx
deny 203.0.113.7;
deny 198.51.100.0/24;
```
```bash
sudo nginx -t && sudo systemctl reload nginx
```

**Firewall (ufw)** — blunt instrument, blocks the IP from the whole host:

```bash
sudo ufw insert 1 deny from 203.0.113.7 to any
sudo ufw status numbered
```

> Behind a reverse proxy, the real client IP arrives in `X-Forwarded-For`. If you
> rate-limit on it, set `RATE_LIMIT_TRUST_FORWARDED=true` and keep
> `RATE_LIMIT_TRUSTED_IPS` to your proxy only, or attackers can spoof the header.

---

## 9. Rotate credentials after a suspected breach

If a token leaked, a laptop with `.env` was lost, or you see unexplained
privileged actions in the [audit log](#consolidated-audit-log), rotate everything.
Move fast; assume the attacker has whatever was exposed.

1. **Invalidate all sessions/tokens** with the helper:
   ```bash
   egi rotate-secrets
   ```
   This **forces token invalidation** — every issued user token stops working, so
   everyone must log in again to get a fresh token. (Communicate this first; it
   logs everyone out.)
2. **Rotate static operator tokens.** If you still use the deprecated
   `OPERATOR_TOKENS`, generate new ones and replace them in `.env`:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Update `OPERATOR_TOKENS=…` in `server/.env`, then restart the service.
3. **Rotate `BACKUP_ENCRYPT_KEY`.** Generate a new key, store it in your secrets
   vault (separate from backups — see [§5](#encryption-key-storage--read-this)),
   set it in `.env`, and take a fresh encrypted backup so a current archive exists
   under the new key. Keep the old key only as long as you need old archives.
4. **Rotate any provider API keys** that were in `.env` (e.g. `OPENAI_API_KEY`)
   via that provider's console.
5. Restart the server, confirm `/health` is `200`, and **review the audit log**
   (`/audit/log?source=all`) for what the attacker touched. Prefer
   corrections/history over silent deletion of any tampered records.
6. Write up what happened and what you rotated, and rotate `.env` file
   permissions back to `chmod 600`.

---

## 10. Common incidents

| Symptom | Check (metric / log) | Action |
|---------|----------------------|--------|
| Site down, `curl /health` refused | `systemctl status egi` / `docker compose ps` | Read last logs, then `systemctl restart egi`. |
| `/health` returns `503`, `database` fail | `/health` `checks.database`, logs | DB file missing/locked or disk read-only; restore from backup ([§6](#6-restore-from-backup)) if corrupt. |
| `/health` `503`, `uploads_dir` fail / low `free_bytes` | `df -h`, `MIN_FREE_BYTES` | Free disk space; prune old backups; grow the volume. |
| Lots of 500s | `rate(egi_http_requests_total{status=~"5.."}[5m])`, `ERROR` logs by `request_id` | Trace a failing `request_id` ([§4](#4-reading-structured-logs--tracing-by-request_id)); fix root cause; restart if needed. |
| Slow / timeouts | p95 from `egi_http_request_duration_seconds`, CPU | Scale the box ([§7](#7-scaling-up-curam-and-moving-to-postgresql)); check for one slow endpoint. |
| Backups stale | `egi_backup_last_success_timestamp`, `backup.log` | Run `egi backup` by hand, read the error; fix disk/key/S3. |
| Moderation backlog | `egi_pending_moderation_total` (alert > 500) | Get more moderators reviewing; check `/moderation/pending`. |
| Messages not delivering | `egi_messages_pending_total{channel}` | Check channel config/credentials and webhook/messaging logs. |
| DB getting large | `egi_db_size_bytes` (alert ~5 GB) | Plan the PostgreSQL move ([§7](#7-scaling-up-curam-and-moving-to-postgresql)). |
| Abuse / flood from one IP | `client_ip` in logs, `egi_http_requests_total` | Block at the edge ([§8](#8-block-an-abusive-ip)); tighten `RATE_LIMIT_*`. |
| Suspected breach / leaked token | Audit log (`/audit/log`) | Rotate credentials ([§9](#9-rotate-credentials-after-a-suspected-breach)). |

---

## See also

- [DEPLOYMENT.md](DEPLOYMENT.md) — install, reverse proxy, systemd, Docker, backups setup.
- [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) — pre-public hardening checklist.
- [deploy/prometheus-alerts.yml](../deploy/prometheus-alerts.yml) — scrape config + alert rules.
- [deploy/docker-compose.staging.yml](../deploy/docker-compose.staging.yml) — staging stack (`egi deploy-staging`).

EGI is a community coordination tool, not a replacement for emergency services.
Operate it responsibly and protect the data.
