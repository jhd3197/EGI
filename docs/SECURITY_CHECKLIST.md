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

---

## Trust, safety & verification (plan-25)

EGI accepts anonymous reports but makes verified sources visibly trustworthy, and
gives operators tools to contain abuse. The model is deliberately lightweight: not
everyone needs to be verified, but verification should be meaningful when present.

### Trust tiers on records

Every person record can carry provenance that travels with it over the mesh:

| Field | Meaning |
|-------|---------|
| `origin_device` | The device fingerprint that created it (already existed). |
| `author_role` | `reporter` \| `watcher` \| `org_member` \| `operator` … |
| `org_id` | Optional organization affiliation. |
| `location_id` | Optional location the update is bound to. |
| `signature` | Proof the record was issued by a verified key. |
| `trust_tier` | **Computed server-side** — `high` (verified) / `medium` (partial) / `low` (unverified). |

`trust_tier` is **never trusted from the client**. The server recomputes it on
every `/sync` upsert from the carried signals, the moderation `reviewed` flag, and
the origin device's reputation (`modules/trust.py`). A banned device's records sink
to `low` and are hidden.

- **High:** an active, signed watcher at a location, or a member of a *verified*
  organization.
- **Medium:** an authorized/verified role, an official source, an operator-approved
  record, or a present (not-yet-pinned) signature.
- **Low:** anonymous — accepted, but visibly unverified.

### How to become a watcher

A watcher is a trusted person responsible for a specific location (a nurse at a
hospital, a volunteer at a shelter).

1. An operator (or org admin) creates the location: `POST /locations`.
2. They mint a one-time invite: `POST /locations/{id}/invites` → returns a `token`
   and `claim_url` (shown **once** — share it as a link or QR code). This is also
   surfaced in the operator **Org/Location admin** screen in the PWA.
3. The watcher logs in and redeems it: `POST /trust/invites/redeem` with the token.
   They are now an authorized watcher; their signed updates for that location show
   as "verified by location" and verify offline against the pinned key.

Authorizations can carry an `expires_at` and be revoked
(`POST /locations/{id}/watchers/{user_id}/revoke`).

### How to become a remote moderator

A moderator is usually a diaspora volunteer reviewing flagged content from abroad.

1. Log in with an account, then `POST /moderators/signup` (PWA: **Moderator
   onboarding** screen) choosing the languages and regions you cover.
2. Review the training example and mark yourself trained (`POST /moderators/me/trained`).
3. Pull your scoped queue: `GET /moderators/me/queue` (open flags + pending records).

Onboarding can be invite-gated per deployment; a community server may run it open.

### Reporting abuse / incorrect information

Any record carries a **"Reportar información incorrecta"** button (PWA `FlagModal`),
mapped to `POST /flags`:

- Reasons: wrong, outdated, duplicate, inappropriate, **deceased** (critical), other.
- Flags are **offline-aware**: they queue on the device and sync when connectivity
  returns. Critical (`deceased`) flags sort to the top of the moderator queue.
- A moderator resolves a flag (`POST /flags/{id}/resolve`); resolving a person flag
  to `rejected`/`approved` applies the moderation decision and is audited.

### Operator abuse controls

- **Rate limits** — IP-based (`ratelimit.py`) plus identity-based per device/user
  (`modules/rate_limit.py`): reports/hour, shelter-updates/hour, mesh-connections/min.
  Over-budget sync records are skipped (the legitimate batch is not rejected).
- **Device bans** — `egi device ban <device_id> --reason "…"` (or
  `POST /trust/devices/{id}/ban`, commander+). A banned device's records are hidden,
  its future syncs rejected, and its id joins the **blocklist bundle**
  (`GET /trust/blocklist`) that gateways relay through the mesh so offline peers drop
  it too.
- **Audit** — every flag, resolution, role grant, invite, and ban is in
  `audit_log` (operator-gated `GET /audit/log`). `egi moderation stats` summarizes
  the queue, flags, and moderator roster.

### Privacy implications

- Remote moderators see report content but **not** private rosters or operator-only
  provenance (`import_batch_id` is stripped from public reads). Watcher identities
  are operator-only; public location reads expose only a `watcher_count`.
- The same minimization rules apply: collect the minimum, mark unverified data,
  prefer corrections/history over silent deletion, and add no analytics/tracking.
- Open questions still being worked: whether moderators should ever see approximate
  locations or photos of minors, periodic re-authorization of watchers, and key
  rotation/recovery if a signing key is compromised.
