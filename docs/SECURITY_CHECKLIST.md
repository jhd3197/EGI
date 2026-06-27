# EGI Security Review Checklist

Run through this list **before any public deployment** and again after major
changes. It maps each control from the security plan (plan-07) to where it lives
and how to verify it. EGI holds sensitive crisis data (names, contacts,
locations), so treat an unchecked box as a blocker, not a nice-to-have.

See also: [`DEPLOYMENT.md`](DEPLOYMENT.md) for how to configure each setting.

---

## Pre-launch checklist

- [ ] **CORS limited to known origins.** `ENV=production` and `ALLOWED_ORIGINS`
      set to your real domain(s) — never `*`. With the PWA served same-origin you
      often need no origins at all.
- [ ] **Security headers present.** `X-Content-Type-Options`, `X-Frame-Options`,
      `Referrer-Policy`, `Permissions-Policy` on every response; optional
      `CONTENT_SECURITY_POLICY` set for the PWA.
- [ ] **Rate limiting enabled.** `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW` tuned;
      a burst of writes returns `429` with `Retry-After`.
- [ ] **Operator endpoints require a bearer token.** `OPERATOR_TOKENS` set to
      one or more secure random strings; moderation/duplicate/review/audit
      endpoints return `401` without a valid `Authorization: Bearer` header.
- [ ] **HTTPS enforced.** Reverse proxy (nginx/Caddy) terminates TLS; port 3000
      is not reachable from the public internet (firewall).
- [ ] **Photos disabled or access-controlled.** `ENABLE_PHOTOS=false` by default;
      when enabled, photos are served only through the operator-gated
      `GET /uploads/{filename}`. EXIF is stripped on upload regardless.
- [ ] **Backups working and tested.** `egi backup` produces a tarball and
      `egi restore` round-trips it. Backups stored encrypted and OFF the server.
- [ ] **Audit logging enabled.** Operator actions, auth failures and record
      creation land in `audit_log` / `record_history`; review via
      `GET /moderation/audit`.
- [ ] **No hardcoded secrets in repo.** No tokens, `.env` files, or DB dumps
      committed. `.gitignore` excludes `.env`, `*.db`, `server/backups/`, `*.tar.gz`.
- [ ] **`.env.example` complete and up to date.** Every required variable is
      documented there.
- [ ] **Dependency scan run.** `pip-audit` (server) and `npm audit` (frontend)
      reviewed; see notes below.
- [ ] **Server headers reviewed.** Confirm the headers above on a live response
      (`curl -I https://your-host/health`).
- [ ] **Data retention policy documented and runnable.** `egi retention-review`
      lists records past retention; `egi anonymize` strips PII while keeping
      status counts.

---

## How each control is implemented

| Control | Where | Configure |
|---|---|---|
| CORS | `server/security.py` (`cors_kwargs`) | `ENV`, `ALLOWED_ORIGINS` |
| Security headers | `server/security.py` (`SecurityHeadersMiddleware`) | `CONTENT_SECURITY_POLICY` |
| Rate limiting | `server/ratelimit.py` (dependency on write routes) | `RATE_LIMIT_MAX/WINDOW/TRUSTED_IPS` |
| Operator auth | `server/auth.py` (`require_operator`) | `OPERATOR_TOKENS` |
| Photo privacy | `server/routes/uploads.py`, `server/security.py`, `server/ocr.py` (`strip_exif`) | `ENABLE_PHOTOS` |
| Audit logging | `server/modules/audit.py`, `audit_log` + `record_history` tables | — |
| Backups | `server/backup.py`, `egi backup` / `egi restore` | `--output` |
| Retention | `server/modules/retention.py`, `egi retention-review` / `egi anonymize` | `retained_until` |
| Input validation | `server/validators.py`, model validators, upload guards | — |

---

## Verifying on a running server

```bash
# Headers + CORS (production should NOT echo an unknown Origin)
curl -sI https://your-host/health
curl -sI -H "Origin: https://evil.example" https://your-host/health | grep -i access-control-allow-origin   # expect: none

# Operator auth (with OPERATOR_TOKENS set)
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://your-host/moderation/SOME_ID/approve            # expect 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Authorization: Bearer $TOKEN" https://your-host/moderation/SOME_ID/approve

# Photo privacy (ENABLE_PHOTOS=false)
curl -s -o /dev/null -w "%{http_code}\n" https://your-host/uploads/whatever.jpg                          # expect 403

# Rate limiting (rapid writes eventually 429)
for i in $(seq 1 100); do curl -s -o /dev/null -w "%{http_code} " -X POST https://your-host/sync -H 'Content-Type: application/json' -d '{"records":[]}'; done
```

---

## Dependency scanning

Run before each release and periodically:

```bash
# Server (install once: pip install pip-audit)
pip-audit -r server/requirements.txt

# Frontend
cd frontend && npm audit
```

**Current state (review at release time):** `npm audit` reports findings in the
**build/dev toolchain** (vite / esbuild / vite-node), which ship only in
`devDependencies` and are not part of the deployed PWA bundle. They do not affect
the production artifact in `frontend/dist/`. Re-evaluate before each release and
upgrade when a non-breaking fix is available. `pip-audit` was not installed in
the build environment at the time of writing — install it and run the command
above as part of the release process.

---

## Ongoing practices

- Rotate `OPERATOR_TOKENS` regularly (change the env var and restart).
- Keep backups encrypted and off-server; test a restore periodically.
- Never commit real operator tokens, `.env` files, or database dumps.
- Treat photos and exact locations as high-risk data.
- Rejected records stay in the DB for audit but hidden from public view.
- Delete or anonymize crisis data once it is no longer needed (`egi anonymize`).
