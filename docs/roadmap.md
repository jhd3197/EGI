# EGI Roadmap

This is the single source of truth for where EGI is going. Each plan is a self-contained document in [`docs/plans/`](plans/). Status is maintained by hand; update it when a phase ships.

**Last updated:** 2026-06-28 (plan-26 shipped: SAR Operations Workflow. Server: six additive `sar_*` tables + migration `0009`, `modules/sar.py` + `routes/sar.py` — operation CRUD with auto-grid/manual sectors + persons M2M, sector claim/release/status with one-active-volunteer-per-sector 409 conflict, volunteer join/check-in/check-out, per-sector task checklist, field reports (`sighting`→`needs_recheck`, `cleared`, `needs_help`, `found`) with the `found`→registry status update gated on operator confirmation, `/sar/sync` mesh/cloud last-write-wins; namespaced under `/sar` so it never collides with the plan-09 `/operations` (events) surface; public reads + anonymous volunteer actions, verified-account operation creation, operator-gated `found` confirmation, every mutation audit-logged. Frontend: `OperationsScreen`/`OperationDetailScreen`/`SectorCard`/`FieldReportSheet` (offline-queued) + store/view wiring (`'operations'` category-gated tab, 409 handling, `myVolunteer` tracking) + DashboardScreen SAR widgets, trilingual es/en/pt (629 keys, parity green; build + check:i18n green). Android: `RecordEnvelope.TYPE_FIELD_REPORT` mesh transport + relay passthrough + JVM round-trip test (assembleDebug + testDebugUnitTest green); on-device Room persistence of relayed field reports rides the pending Room-migration/BLE-cert path like plan-25's trust carry. 13 server pytest + 5 frontend vitest; full server + frontend suites green; live HTTP E2E (create→join→claim→check-in→found→confirm→registry flip) verified. Roadmap execution order is 27 → 28 → 29.)

**Previously updated:** 2026-06-28 (plan-25 shipped: Trust, Safety & Verification. Server: record trust signals (`author_role`/`org_id`/`location_id`/`signature`) + server-computed `trust_tier` (`modules/trust.py`, never client-trusted), `device_reputation` (0-100 score/tier + ban/blocklist), `organizations`/`locations`/`org_members`/`location_watchers` with TOFU-pinned signing keys + operator verification, one-time `trust_invites` (link/QR, SHA-256, user-bound redeem), `moderation_flags` (public+offline+critical-first) + resolve, `moderators` onboarding + region-scoped queue, per-device/user rate limiting wired into `/sync` — migration 0008, routes `trust`/`organizations`/`locations`/`moderators` + `/flags`, CLI `egi device` + `egi moderation`. Frontend: trust badges, `FlagModal`, ModerationScreen Flags tab, `ModeratorOnboardingScreen`, `OrgAdminScreen` (548 i18n keys, parity green; build green). Android: `MeshCrypto` ECDSA sign/verify + envelope codec preserves trust fields on relay (store-and-forward Room carry partial). Docs: README trust section + SECURITY_CHECKLIST trust model. Server pytest green (pre-existing voice-backend env tests aside). Roadmap execution order is 26 → 27 → 28 → 29.)

**Previously updated:** 2026-06-28 (plan-24 shipped: User Preferences, Subscriptions & Alerts — the unified cross-cutting layer. Server: `user_preferences`/`user_settings`/`operation_subscriptions` tables (migration 0006), `modules/preferences.py` (timestamp-guarded LWW + decision helpers), `modules/notifications.py` (preference-aware gate: category notify toggle, operation mute, near-me radius, quiet hours; critical categories + own-record matches bypass), `modules/subscriptions.py`, routes `/preferences[/categories|/notify-test]` + `/subscriptions` + `/operations/{id}/subscribe|unsubscribe|mute`; rate-limited + audited. Frontend: `lib/preferences.js`, local-first store sync, `SettingsScreen`+`NotificationSettings`, category-display gating in `view.js` (feed/search/map/shelters tab + near-me radius), `CategoryFilterNote`, DisasterPicker subscribe/mute. Android: per-category relay opt-outs gate the mesh bloom filter (`MeshRepository`/`BluetoothMeshManager`/`EgiBridge`) + PWA "data types I share" mesh section. Trilingual es/en/pt (498 keys, parity green); FE 101 tests green; assembleDebug runs on Samsung SM-S134DL. Roadmap execution order is 24 → 25 → 26 → 27 → 28 → 29.)

**Previously updated:** 2026-06-28 (created Plan 24 — User Preferences, Subscriptions & Alerts as a unified cross-cutting layer; the animal opt-out in Plan 28 is now one application of this system. Roadmap execution order is 23 → 24 → 25 → 26 → 27 → 28 → 29.)

---

## Legend

- ✅ Done
- 🚧 In progress
- ⏳ Pending
- 🛑 Blocked / deferred

---

## At a glance

| Plan | Area | Status |
| --- | --- | --- |
| 01 | Foundations & alignment | ✅ done (offline map tiles shipped in plan-10) |
| 02 | Mesh & bridge sync | ✅ done (mesh polish completed in plan-16; real-device BLE certification pending) |
| 03 | Testing & quality | ✅ done (Android CI wired in plan-16; real-device BLE certification pending) |
| 04 | CLI, seeding & AI ops | ✅ done (OCR review TUI pending) |
| 05 | Mesh hardening & data quality | ✅ done (mesh polish completed in plan-16) |
| 06 | Product & UX hardening | ✅ done (mesh status UI shipped in plan-16) |
| 07 | Security, privacy & operations | ✅ done |
| 08 | User accounts, hashing & RBAC | ✅ done |
| 09 | Search operations & action plans | ✅ done |
| 10 | Photos, maps & geospatial | ✅ done (face-blur + bbox-draw tool deferred) |
| 11 | Communications hub | ✅ done (native Android FCM client shipped in plan-16; real-provider creds pending) |
| 12 | Interoperability & federation | ✅ done (PFIF XML, CSV/Excel, PDF flyers, webhooks, federation) |
| 13 | Operational intelligence | ✅ done (dashboards, quality scoring, SITREP reports) |
| 14 | Inclusive crisis access | ✅ done (WhatsApp/Telegram bots, voice transcription, Wayuu i18n + panic mode, shelter posters; native Android ML Kit translation/voice + real bot creds pending) |
| 15 | Production operations, observability & scaling | ✅ done (health/metrics, JSON logs, automated backups, load tests/SLOs, CI security scans, ops manual; PostgreSQL runtime is scaffolded but experimental) |
| 16 | Field-ready Android mesh & native communications | 🚧 code complete (reports over mesh, live mesh UI, Wi-Fi Direct, duty-cycling/foreground service, SMS check-in, native FCM, warning-free Kotlin + Room migrations, emulator CI wired); pending real-device BLE certification + live push creds |
| 17 | Final polish & platform finishes | ⏳ pending (event/city selector, OCR TUI, draw-a-box map search, face-blur, faster-whisper, ML Kit packs, full PostgreSQL runtime) |
| 18 | Android automation & validation agent | ✅ done (lint/schema fixes shipped; install/permission/test scripts ready; two-device mesh smoke test scaffolded; PWA now renders on both connected phones) |
| 19 | PWA-in-WebView end-to-end testing | 🚧 mostly shipped (offline fonts, native `/sync` bridge, CDP smoke tests A/B/C green on both devices, visual regression, CI; two-device mesh propagation blocked by BLE scan throttle → plan-18) |
| 20 | Shelter & refugee information hub | ✅ done (server-backed shelters, detail card, directions, official feed, capacity filters, check-in, verified-operator tokens; guc i18n falls back to es) |
| 21 | Offline routing: from X to Y | ✅ done (directions UI, road-network packs + Web Worker A\*, native position bridge, hazard avoidance, route sharing, multi-modal + evacuation corridors; BLE-direct route-share propagation rides on pending BLE cert; transit awaits GTFS data) |
| 22 | i18n language purity audit & fix | ✅ done (bilingual `*En` keys and ` · ` halves removed from es/en/pt; components render one language per element; `check:i18n` CI guard + vitest purity suite; on-device screenshot baselines deferred) |
| 23 | Android mesh human chain & gateway bridging | ✅ code complete (hop limit, gateway flag + preference routing, live FG notification, Wi-Fi Direct bulk socket transfer, PWA gateway/chain UI, trilingual README, new JVM + instrumented tests); pending real-device 3-hop certification + on-device Wi-Fi Direct group negotiation |
| 24 | User preferences, subscriptions & alerts | ✅ done (per-category display/notify/relay preferences, local-first + server sync, settings UI, preference-aware notifications, operation subscriptions, mesh-relay opt-outs, life-safety bypass + audit; APK runs on Samsung, Moto pending re-verify) |
| 25 | Trust, safety & verification | ✅ done (server + PWA shipped; Android signing shipped, mesh store-and-forward field carry partial) |
| 26 | SAR operations workflow | ✅ done (server + PWA shipped; Android mesh field-report transport shipped, Room persistence partial) |
| 27 | Data quality & deduplication engine | ⏳ pending |
| 28 | Missing animals (pets) | ⏳ pending |
| 29 | UX audit & pre-flight checks | ⏳ pending (final polish before major releases) |

---

## Plan 01 — Foundations & Alignment
**File:** [`plans/plan-01-foundations.md`](plans/plan-01-foundations.md)  
**Goal:** Define what EGI is, align the stack with the bridge-node vision, and outline the PFIF-aligned data model.

- ✅ Offline-first web PWA
- ✅ FastAPI server + SQLite
- ✅ Android folder + WebView direction
- ✅ PFIF-style schema (`events`, `cities`, `reports`, `incidents`)
- ✅ Basic person + report records
- 🚧 Event + city selectors in PWA (`DisasterPicker.jsx` — event-level done, city-within-event partial)
- ✅ Self check-in flow (`HomeScreen` → `checkInSelf`)
- ✅ Search by cédula and name (UI) (`SearchScreen.jsx`)
- ✅ Offline map tiles (shipped in plan-10: `frontend/src/lib/tileCache.js`)

---

## Plan 02 — Mesh & Bridge Sync
**Files:** [`plans/plan-02-mesh-and-bridge.md`](plans/plan-02-mesh-and-bridge.md), [`plans/plan-02-followups.md`](plans/plan-02-followups.md)  
**Goal:** Let two nearby Android phones exchange records without internet, and let any phone bridge the merged data to the cloud.

- ✅ BLE advertisement + scan
- ✅ GATT index exchange + record transfer
- ✅ Room DB with last-write-wins merge
- ✅ Cloud sync to `/sync`
- ✅ `window.EgiNative` JS bridge
- ✅ Bloom filter peer skipping
- ✅ GATT encryption + privacy warning (mandatory GATT encryption + privacy consent)
- ✅ Reports (PFIF notes) over the mesh (plan-16)
- ✅ Mesh UI in the PWA (`MeshScreen.jsx`, plan-16)
- ✅ Wi-Fi Direct bulk transfer (plan-16; device-level group negotiation still TODO)
- ✅ Relay duty-cycling + foreground service (plan-16)
- ✅ SMS text-only check-in full flow (plan-16)

---

## Plan 03 — Testing & Quality
**File:** [`plans/plan-03-testing-and-quality.md`](plans/plan-03-testing-and-quality.md)  
**Goal:** Fast, practical tests that catch real breakage.

- ✅ Server pytest suite (`test_sync.py`, `test_db.py`, `test_ocr.py`)
- ✅ Frontend vitest suite (`form.test.js`, `indexeddb.test.js`)
- ✅ CI workflow for server + frontend tests
- ✅ Kotlin JVM unit tests (envelope, bloom filter, mappers)
- ✅ Manual test checklist
- ✅ Android emulator/instrumented tests in CI (`.github/workflows/android.yml`, plan-16; not yet executed on hardware-accel runner)
- 🚧 BLE hardware manual test certification (checklist + `mobile/android/scripts/` automation shipped in plan-16; real-device sign-off pending)

---

## Plan 04 — CLI, Seeding & AI-Assisted Data Operations
**File:** [`plans/plan-04-cli-seeding-and-ai-ops.md`](plans/plan-04-cli-seeding-and-ai-ops.md)  
**Goal:** Make development, demos, and operator tasks easy via a single `egi` CLI.

- ✅ `egi` CLI (`backend`, `frontend`, `build`)
- ✅ `egi seed` / `egi unseed`
- ✅ `egi generate-synthetic`
- ✅ Modular server refactor (`modules/` + `routes/`)
- ✅ `server/ai.py` multi-provider base (Ollama + OpenAI)
- ✅ `POST /normalize` free-text → AI draft
- ✅ PFIF-aligned schema fields
- ✅ `egi export-pfif` / `egi import-pfif` CLI commands
- ✅ XML PFIF export (`export-pfif --format xml|json`)
- 🚧 OCR review TUI helper (`egi_cli/commands/ocr_review.py` — stub)

---

## Plan 05 — Mesh Hardening & Data Quality
**File:** [`plans/plan-05-mesh-hardening-and-data-quality.md`](plans/plan-05-mesh-hardening-and-data-quality.md)  
**Goal:** Complete the mesh, add data-quality features, and make the Android build field-ready.

- ✅ Fuzzy duplicate detection (`/duplicates/pending`, merge, reject)
- ✅ Confidence-based status derivation (`self > official > witness > ocr`)
- ✅ Moderation queue (`/moderation/pending`, approve, reject, stats)
- ✅ `dedup_rejections` table to avoid re-suggesting rejected clusters
- ✅ Soft-merge preserves history
- ✅ GATT encryption
- ✅ Reports over mesh (plan-16)
- ✅ Mesh UI in PWA (plan-16)
- ✅ Wi-Fi Direct bulk socket transfer (plan-16)
- ✅ Duty-cycling + foreground service (plan-16)
- ✅ SMS fallback (plan-16)
- ✅ Warning-free Kotlin build + real Room migrations (plan-16)

---

## Plan 06 — Product & UX Hardening
**File:** [`plans/plan-06-product-and-ux-hardening.md`](plans/plan-06-product-and-ux-hardening.md)  
**Goal:** Make the PWA usable, trustworthy, and resilient in a real crisis.

- ✅ Migrate offline cache from `localStorage` to IndexedDB (`frontend/src/lib/db.js`)
- ✅ Replace fake Google auth with honest guest/alias flow (`AuthScreen.jsx`)
- ✅ i18n scaffold (es / en / pt) (`frontend/src/i18n/`)
- ✅ Accessibility pass (focus, ARIA, live regions, contrast)
- ✅ Redesign home with three clear actions (`HomeScreen.jsx`)
- ✅ Fast sighting and safe-registration flows (`ReportSheet.jsx`)
- ✅ Prominent cédula search + scan (`SearchScreen.jsx`)
- ✅ Pagination in `/persons` (cursor-based)
- ✅ Moderator UI in the PWA (`ModerationScreen.jsx`)
- ✅ Mesh status UI (`MeshScreen.jsx` fully live: peers, last sync, queued, recently-seen devices, manual sync; plan-16)

---

## Plan 07 — Security, Privacy & Operations
**File:** [`plans/plan-07-security-privacy-and-operations.md`](plans/plan-07-security-privacy-and-operations.md)  
**Goal:** Protect crisis data and make public deployment repeatable.

- ✅ CORS restricted to known origins (`security.py`, `ALLOWED_ORIGINS`)
- ✅ Security headers middleware (`SecurityHeadersMiddleware`)
- ✅ Rate limiting on write endpoints (`ratelimit.py`)
- ✅ Operator bearer-token auth for moderation
- ✅ Photo upload access control (disabled by default, `ENABLE_PHOTOS`)
- ✅ Audit logging for moderator actions (`modules/audit.py`)
- ✅ VPS / Docker deployment guide (`docs/DEPLOYMENT.md`)
- ✅ `egi backup` + restore command (`egi_cli/commands/backup.py`)
- ✅ Data retention + anonymization policy (`modules/retention.py`)
- ✅ Security review checklist (`docs/SECURITY_CHECKLIST.md`)

---

## Plan 08 — User Accounts, Password Hashing & RBAC
**File:** [`plans/plan-08-user-accounts-rbac.md`](plans/plan-08-user-accounts-rbac.md)  
**Goal:** Replace static operator tokens with real user accounts, secure password hashing, and role-based access control.

- ✅ `users` and `user_tokens` tables
- ✅ bcrypt password hashing
- ✅ `POST /auth/login`, `/auth/logout`, `/auth/me`
- ✅ Roles: viewer, operator, commander, admin (`require_role`)
- ✅ User CRUD (admin only) (`routes/users.py`, `egi user …`)
- ✅ Deprecation window for old `OPERATOR_TOKENS` (logged backward-compat fallback)

---

## Plan 09 — Search Operations & Action Plans
**File:** [`plans/plan-09-search-operations-action-plans.md`](plans/plan-09-search-operations-action-plans.md)  
**Goal:** Turn `events` into active operational cases and add versioned action plans with tasks.

- ✅ Operational fields on `events` (commander, status, closure, UTM)
- ✅ `/operations` API (`routes/operations.py`)
- ✅ `action_plans` and `action_plan_tasks` tables
- ✅ Default task templates
- ✅ Task state machine and assignment

---

## Plan 10 — Photos, Maps & Offline Geospatial Intelligence
**File:** [`plans/plan-10-photos-maps-geospatial.md`](plans/plan-10-photos-maps-geospatial.md)  
**Goal:** Add safe photo handling, map-based views, and geospatial search.

- ✅ `photos` table with resize/thumbnails (`modules/photos.py`, `routes/photos.py`: POST/GET `/persons/{id}/photos`, DELETE `/photos/{id}`; ≤1200px + 300×300, content-hash filenames)
- ✅ EXIF stripping and optional GPS extraction (`ocr.extract_gps` / `extract_taken_at` lift GPS+date into `lat`/`lon`/`taken_at` before stripping)
- ✅ Photo access control (operator-gated `/uploads`, shipped in Plan 07; still behind `ENABLE_PHOTOS`)
- ✅ Map UI with OpenStreetMap (Leaflet + markercluster: `frontend/src/components/MapScreen.jsx`)
- ✅ Radius search (`GET /persons/nearby`, "Buscar en esta área" in the map UI) + bounding-box/heatmap endpoints (`GET /operations/{id}/bounds` and `/heatmap`). 🚧 A literal draw-a-box tool in the UI is deferred.
- ✅ Offline map tile caching (`frontend/src/lib/tileCache.js`: IndexedDB `egi-tiles` store + region prefetch; `OfflineTileLayer`)
- 🚧 Face-blur toggle for public-safe thumbnails — deferred (optional AI; not shipped)

---

## Plan 11 — Communications Hub: SMS, Push, Email & Alerts
**File:** [`plans/plan-11-communications-hub.md`](plans/plan-11-communications-hub.md)  
**Goal:** Build a unified messaging layer for notifications, broadcasts, and two-way replies.

- ✅ Pluggable SMS provider with two-way parsing (`modules/sms.py` + `modules/providers.py`: check-in + reply→report, `/sms/notify`, `/sms/broadcast`; log/Twilio drivers)
- ✅ Email provider abstraction (`modules/email.py` + `providers.py`: log/SMTP; welcome + password-reset (`/auth/forgot-password`, `/auth/reset-password`) + alert emails, es/en/pt HTML+text templates)
- ✅ Web Push + FCM push notifications (`modules/push.py`, `routes/push.py`, `frontend/public/sw.js` + `PushToggle`; subscribe/unsubscribe + operation topics) + native Android FCM client (`MeshFirebaseMessagingService`, plan-16). 🚧 Real delivery needs VAPID/FCM creds (`pywebpush`/`firebase-admin` optional, see `docs/PUSH_SETUP.md`).
- ✅ Operation-wide alert broadcasts (`modules/alerts.py`: `POST /operations/{id}/alerts` → push+SMS+email, templated with variables)
- ✅ Delivery status tracking (`messages` table + `alert_id`; `GET /messages`, `/operations/{id}/alerts`, `/alerts/{id}/messages`, status callback)

**Shipped in this plan:** `message_providers` / `messages` / `push_subscriptions` / `password_resets` tables; `modules/{messaging,providers,templates,email,push,alerts}.py`; routes `{messaging,push,alerts}` + SMS/auth extensions; pluggable provider abstraction (config = runtime change). **Remaining:** wire real provider credentials in a deployment and install `pywebpush`/`firebase-admin` for live Web Push/FCM (the native Android FCM client shipped in plan-16).

---

## Plan 12 — Interoperability, Federation & Data Exchange
**File:** [`plans/plan-12-interoperability-federation.md`](plans/plan-12-interoperability-federation.md)  
**Goal:** Import/export standard formats, federate trusted servers, and notify external systems.

- ✅ PFIF 1.4 XML round-trip (`server/pfif.py` export/import wired)
- ✅ CSV/Excel import and export (`modules/exchange.py` + `routes/exchange.py`: operator-gated CSV/xlsx export with filters, bulk import with es/en column-alias mapping + per-row validation; imports land as `source='csv_import'` awaiting moderation)
- ✅ PDF missing-person flyers (`modules/flyer.py` + `GET /persons/{id}/flyer.pdf`: localized es/en/pt, contact QR, optional photo behind `ENABLE_PHOTOS`; degrades to 503 if reportlab/qrcode absent)
- ✅ Webhooks with retry logic (`modules/webhooks.py` + `routes/webhooks.py`: subscription CRUD, HMAC-SHA256 signed delivery, per-attempt log, exponential-backoff `retry_pending`; emits `person.created/updated/merged` + `operation.closed`, best-effort post-commit)
- ✅ Server-to-server federation (`modules/federation.py` + `routes/federation.py` + `egi peer` CLI: `trusted_peers` with TOFU public-key pinning, pull/push/sync reusing the `/sync` last-write-wins logic so two nodes federate without duplicates)

---

## Plan 13 — Operational Intelligence, Dashboards & Reporting
**File:** [`plans/plan-13-operational-intelligence.md`](plans/plan-13-operational-intelligence.md)  
**Goal:** Give commanders situational awareness through dashboards, quality scoring, and reports.

- ✅ Operation and global stats endpoints (`modules/stats.py` + `routes/stats.py`: `GET /stats/operations/{id}`, `/stats/operations/{id}/timeseries`, `/stats/global`)
- ✅ Data-quality scoring (`modules/quality.py` + `routes/quality.py`: per-record completeness/confidence/freshness score with issue codes, cached in `data_quality_scores`; `/quality/summary|low|stale|persons/{id}|recalculate`; `egi quality-scan` nightly job)
- ✅ Automated duplicate suggestions (`modules/duplicates.py`; surfaced in `egi quality-scan` + `possible_duplicate` quality flag)
- ✅ Heatmap and hot-zone endpoints (`GET /operations/{id}/heatmap` + `/bounds`, shipped in plan-10; suggested search sectors added in plan-13: `GET /operations/{id}/sectors`)
- ✅ Scheduled SITREP reports (`modules/sitrep.py` json/html/pdf + `modules/scheduled_reports.py` + `routes/reports.py`: `GET /operations/{id}/sitrep`, `scheduled_reports` CRUD, `POST /reports/run-due`; `egi sitrep` + `egi run-reports` CLIs; PDF degrades to 503 without reportlab)
- ✅ PWA dashboard screen (`frontend/src/components/DashboardScreen.jsx`, operator-gated, consumes `/stats`)

---

## Plan 14 — Inclusive Crisis Access: Voice, Chatbots, Translation & Low-Literacy UX
**File:** [`plans/plan-14-inclusive-crisis-access.md`](plans/plan-14-inclusive-crisis-access.md)  
**Goal:** Lower the barriers to reporting and searching so almost anyone can use EGI during a crisis, regardless of literacy, language, device, or connectivity.

- ✅ WhatsApp bot for reporting and search (`modules/chatbot.py` + `modules/whatsapp_bot.py`, `POST /webhooks/whatsapp`; Twilio + Meta Cloud API drivers, `log` default; report/safe/search FSM, drafts `source='whatsapp'` reviewed=0 → moderation; replies logged in `messages`)
- ✅ Telegram bot for diaspora volunteers (`modules/telegram_bot.py`, `POST /webhooks/telegram`; `/buscar /reportar /estoybien /ayuda`, reuses the same engine; slash commands reset in-progress intent)
- ✅ Voice-note transcription (`modules/voice.py` + `voice_transcripts` table, `POST /voice/transcribe`): local-first Whisper backends, best-effort WhatsApp/Telegram audio download, low-confidence flagged for confirmation; on-device (Web Speech API / EgiNative) preferred. 🚧 Server backend needs optional `faster-whisper`.
- ✅ On-device translation + Wayuu (`frontend/src/i18n/guc.js` partial dict + offline `LanguagePicker`, `lib/translate.js` EgiNative bridge). 🚧 Native Android ML Kit offline packs are a direction doc (`mobile/android/translation-plan14.md`), not yet shipped in Kotlin.
- ✅ Panic/low-literacy UI mode (`SimpleHomeScreen.jsx`: three giant high-contrast actions, tap-to-hear TTS via `lib/speech.js`, `simpleMode` persisted)
- ✅ Printable shelter posters with QR codes (`modules/poster.py`, `GET /operations/{id}/poster.pdf`: big QR opens the PWA with `?op=<id>`, pictographic steps, es/en/pt; 503 without reportlab/qrcode)

---

## Plan 15 — Production Operations, Observability & Scaling
**File:** [`plans/plan-15-production-operations-observability-scaling.md`](plans/plan-15-production-operations-observability-scaling.md)  
**Goal:** Make EGI reliable, observable, and scalable enough for real-world community deployment.

- ✅ Structured `/health`, `/ready`, and Prometheus `/metrics` (`modules/health.py`, `metrics.py`; hand-rolled exposition, no new deps; request middleware records count+latency, DB-derived gauges)
- ✅ Structured JSON logs with request IDs (`logging_config.py`: JSON/text formatter + `request_id` contextvar, `X-Request-ID` echo/generate, structured access log) + consolidated operator-gated `GET /audit/log` (`routes/audit.py`)
- ✅ Automated encrypted backups + restore CLI + offsite upload (`backup.py`: integrity check, retention pruning, Fernet encryption, S3 via boto3 — both optional/graceful; `egi backup --retention-days/--encrypt/--s3-*`, `egi schedule-backup`, `egi restore` decrypts + verifies; restore drill in `docs/OPERATIONS.md`)
- 🚧 PostgreSQL migration path with a migration runner — runner shipped & CI-enforced (`migrate.py`, `server/migrations/*.sql`, `schema_migrations`, `egi migrate [--check]`); `DATABASE_URL` detection + `egi sqlite-to-postgres` cutover (`migrate_pg.py`, psycopg optional) + `docs/POSTGRES.md`. **Postgres runtime is experimental:** a few modules still use SQLite-only SQL (`INSERT OR REPLACE`, `PRAGMA`); SQLite remains the tested default.
- ✅ Load tests and documented SLOs (`docs/PERFORMANCE.md` SLOs, `server/tests/load/locustfile.py`, `frontend/tests/perf/lighthouserc.js`; TTL-cached global dashboard stats)
- ✅ Security/dependency scanning in CI (`.github/workflows/security.yml`: pip-audit + npm audit advisory, bandit blocking on HIGH, gitleaks, optional trivy; `.pre-commit-config.yaml`; `egi rotate-secrets`)
- ✅ Operations manual (`docs/OPERATIONS.md`) and example alerts (`deploy/prometheus-alerts.yml`, `deploy/docker-compose.staging.yml`, `egi deploy-staging`)

**Shipped in this plan:** `schema_migrations` + `system_events` tables; `server/{version,metrics,logging_config,migrate,migrate_pg}.py`; `modules/{health,system_events}.py`; `routes/{audit,system}.py`; backup encryption/retention/S3 + `egi {schedule-backup,migrate,sqlite-to-postgres,rotate-secrets,deploy-staging}`; CI security workflow + pre-commit; `docs/{OPERATIONS,PERFORMANCE,POSTGRES}.md` + `deploy/`. **Remaining:** finish Postgres runtime portability (raw-SQL dialect layer, psycopg connection in `db.get_db`, Postgres CI job).

---

## Plan 16 — Field-Ready Android Mesh & Native Communications
**File:** [`plans/plan-16-field-ready-android-mesh-and-native-comms.md`](plans/plan-16-field-ready-android-mesh-and-native-comms.md)  
**Goal:** Finish the Android mesh and native messaging bridge so EGI works offline between nearby phones and syncs the moment any device gets connectivity.

- ✅ Reports (PFIF notes) over BLE mesh (`MeshRepository.localRecordIndex/envelopesFor/mergeEnvelope` dispatch person+report; reports upload via `CloudSyncClient`)
- ✅ Live mesh UI in the PWA (`MeshScreen.jsx`: toggle+consent, peer count, last sync, queued, manual sync, status text, and recently-seen device list from `peer_synced` events)
- ✅ Wi-Fi Direct bulk socket transfer (`WifiDirectManager.sendBulk` ServerSocket/8988 + length-prefixed `ChunkFraming`; `BulkTransferTest`). 🚧 P2P group-owner negotiation auto-trigger in `BluetoothMeshManager` is still a TODO (device-level fallback)
- ✅ Relay duty-cycling + foreground service (`DutyCycler` advertise/scan/sleep + battery-saver + auto-low-battery + per-cycle logging; `MeshForegroundService` ongoing notification)
- ✅ SMS text-only check-in full flow (Android `SmsCheckinReceiver` creates linked person+report and nudges sync; server `POST /sms/webhook` mirrors it + outbound confirmation; lands reviewed=0 in moderation)
- ✅ Native Android FCM client (`MeshFirebaseMessagingService` → `POST /push/subscribe` kind=fcm, alerts forwarded to PWA) + optional server `firebase-admin`/`pywebpush` paths + `docs/PUSH_SETUP.md`. 🚧 Live delivery needs real VAPID/FCM creds (`google-services.json`)
- ✅ Warning-free Kotlin build + real Room migrations (deprecated `optString`/`GATT_SUCCESS`/`onBackPressed` already fixed; explicit `MIGRATION_1_2` + exported schemas + `MigrationTest`). ⚠️ assembleDebug not run here — no Android SDK in this environment
- 🚧 Android emulator/instrumented tests in CI + manual BLE certification — `.github/workflows/android.yml` (JVM `test` + emulator `connectedCheck`) and new instrumented tests added; manual BLE certification checklist in `docs/TESTING.md` + `mobile/android/scripts/` automation, but real-device sign-off is still pending hardware

---

## Plan 17 — Final Polish & Platform Finishes
**File:** [`plans/plan-17-final-polish-and-platform-finishes.md`](plans/plan-17-final-polish-and-platform-finishes.md)  
**Goal:** Clear the remaining cross-cutting 🚧 items and finish the product.

- ⏳ Event + city selectors in PWA (`DisasterPicker.jsx` city-within-event)
- ⏳ OCR review TUI helper (`egi ocr-review`)
- ⏳ Draw-a-box search tool in the map UI
- ⏳ Face-blur toggle for public-safe thumbnails
- ⏳ Server voice backend with optional `faster-whisper`
- ⏳ Native Android ML Kit offline translation packs
- ⏳ Full PostgreSQL runtime support + CI job

---

## Plan 18 — Android Automation & Validation Agent
**File:** [`plans/plan-18-android-automation-validation-agent.md`](plans/plan-18-android-automation-validation-agent.md)  
**Goal:** Make Android validation repeatable and agent-driven via ADB.

- ✅ Environment detection script (`scripts/detect-env.sh`) sets `JAVA_HOME` and `ANDROID_SDK_ROOT`
- ✅ Lint errors fixed and `lintDebug` passes
- ✅ Room schema JSONs exported (`app/schemas/1.json`, `2.json`) so `MigrationTest` passes
- ✅ `scripts/devices.py` lists connected devices, models, and EGI install state
- ✅ `scripts/install-and-configure.sh` builds APK, installs, grants permissions, and captures launch screenshots
- ✅ `scripts/run-tests.sh` runs lint + unit tests + instrumented tests on attached devices
- 🚧 `scripts/mesh-smoke-test.py` scaffolded for two-device BLE record exchange validation
- ⏳ CI workflow for Android + real-device self-hosted runner

---

## Plan 19 — PWA-in-WebView End-to-End Testing
**File:** [`plans/plan-19-pwa-webview-end-to-end-testing.md`](plans/plan-19-pwa-webview-end-to-end-testing.md)  
**Goal:** Make the embedded PWA fully usable offline and validate critical journeys on real hardware via ADB.

- ✅ PWA renders inside `WebViewAssetLoader` on Samsung and Moto test devices
- ✅ Bundle fonts into the PWA so the UI is identical offline — IBM Plex self-hosted via `@fontsource`, Google Fonts CDN removed, `npm run check:offline` guards against regressions (verified: no font-CDN requests on either device)
- ✅ Intercept `/sync` (and `/persons`, `/persons/{id}/reports`, `/favicon.ico`) so they are served from the native Room DB instead of failing with `ERR_NAME_NOT_RESOLVED` — `PwaApiBridge` (GET reads in `shouldInterceptRequest`; POST writes via `window.EgiNative` + a document-start fetch shim). Verified: `fetchAll` succeeds on both devices, no errors
- ✅ `scripts/pwa-smoke-test.sh` automates guest entry, alias entry, and report creation by driving the real DOM over CDP (`pwa_cdp.py` + `pwa-test-harness.js`) — all three journeys PASS on both devices; Journey C proves a UI-created report lands in Room
- ✅ Baseline screenshot comparison for visual regression — perceptual diff (`pwa_visual.py`), opt-in `EGI_VISUAL=1`, `update-baselines.sh`, per-device baselines (uncommitted)
- 🚧 Two-device mesh validation (`mesh-pwa-e2e-test.py`) — advertise-refresh fix shipped & verified (a PWA-created record now enters the mesh bloom; receiver discovers the peer), but end-to-end BLE propagation is blocked by Android's sub-second scan-window throttle; duty-cycle retuning tracked for plan-18
- ✅ Hands-free permission & consent dialogs (`device_dialogs.py`) — `grant_all()` pm-grants every dangerous permission before launch so the system dialog never appears; `accept_dialogs()` taps Allow/Permitir/Continuar via the `uiautomator` UI tree (clickable buttons only). Wired into `install-and-configure.sh` and the smoke/mesh runners → zero manual taps after install. Verified: consent dialog auto-dismissed on hardware
- ✅ CI: `android-pwa-smoke.yml` (emulator single-device journeys on every PR) + `android-mesh-e2e.yml` (self-hosted two-device, manual/nightly); `TESTING.md` documents the whole stack

---

## Plan 20 — Shelter & Refugee Information Hub
**File:** [`plans/plan-20-shelter-refugee-information-hub.md`](plans/plan-20-shelter-refugee-information-hub.md)  
**Goal:** Turn the current shelter list into a full information hub for victims, responders, and family members.

- ✅ Shelter detail card with capacity, services, contact, and supply needs (`ShelterDetailScreen.jsx`; server `shelters` table + `GET/POST /shelters`)
- ✅ "How to get there" directions from current location or any origin (`lib/directions.js` + native `EgiBridge.openTurnByTurn` Google Maps/Waze/OsmAnd intent; straight-line distance/time + cached route)
- ✅ Official shelter feed / updates from verified staff (`shelter_updates` + `GET/POST /shelters/{id}/updates`; official/volunteer/system role badges, occupancy side-effects, offline queue)
- ✅ "I am here" shelter check-in flow (`shelter_checkins` + `POST /shelters/{id}/checkin`, public family alias search `GET /shelters/checkins/search`, offline queue)
- ✅ Verified shelter operator mode + token management (`shelter_tokens`; commander `egi shelter issue-token/tokens/revoke-token`, `POST /shelters/claim` → trust=official, private roster + CSV export)

**Shipped in this plan:** four additive server tables (`shelters`/`shelter_updates`/`shelter_checkins`/`shelter_tokens`), `modules/shelters.py` + `routes/shelters.py` (filters has_space/accepts_pets/has_medical/needs_supplies, capacity PATCH, feed, check-in, claim, roster CSV); PWA `ShelterDetailScreen.jsx` + tap-through/filters/operator-claim in `SheltersScreen.jsx`, `lib/directions.js`; `egi shelter` CLI; es/en/pt i18n (guc falls back to es); 9 server + 6 frontend tests. **Remaining:** mesh propagation of shelter updates between phones (rides on the BLE certification still pending in plan-16/18); native Android operator UI (PWA covers it today); roster PDF (CSV ships, PDF deferred to the flyer/reportlab path).

---

## Plan 21 — Offline Routing: From X to Y
**File:** [`plans/plan-21-offline-routing-x-to-y.md`](plans/plan-21-offline-routing-x-to-y.md)  
**Goal:** Provide offline-capable directions between any two points relevant to EGI users (shelters, people, hazards, evacuation corridors).

- ✅ Basic directions UI with straight-line distance + walking time (`DirectionsScreen.jsx`; Haversine + bearing/cardinal step list, mi/km, 20-route IndexedDB history; es/en/pt/guc)
- ✅ Cached road-network routing packs + Web Worker graph search (`routing_packs` table + public `GET /routing/packs[/{id}]`; `routeGraph.js` A\* in `workers/routeWorker.js`, `routePack.js` IndexedDB cache; road polyline on the map; La Guaira demo pack seeded)
- ✅ Native Android turn-by-turn bridge (`EgiBridge.getCurrentPosition`/`navigateTo` + `LocationCache.kt` last-known cache + WebView geolocation grant; `openTurnByTurn` intent chain pre-existed; verified on SM-S134DL + Moto G Play)
- ✅ Hazard-aware routing (`hazard_zones` table + public `GET /hazards` / community `POST /hazards`→moderation + operator review; A\* edge avoidance via `hazards.js`; map overlays + route-crosses-hazard warning + "report hazard here")
- ✅ Route sharing over mesh (`route_shares` table + `POST /routes/share` 6h-dedup + `GET /routes/shared`; share + suggested-routes UI, offline-queued). 🚧 BLE-direct propagation rides on the device BLE certification still pending in plan-16/18; today shares sync via the server bridge-node path.
- ✅ Multi-modal and long-distance evacuation routing (`multimodal.js` walk/drive/transit speeds, arrival ranges, long-walk battery warning, `hubToHub` two-leg plan; `evacuation_corridors` table + `GET /corridors` + map overlay). 🚧 Public transit awaits a real GTFS/operator feed (degrades to a "no transit data" state).

---

## Plan 22 — i18n Language Purity Audit & Fix
**File:** [`plans/plan-22-i18n-language-purity-audit.md`](plans/plan-22-i18n-language-purity-audit.md)  
**Goal:** Remove mixed-language UI so Spanish shows only Spanish, English only English, and Portuguese only Portuguese.

- ✅ Audit and catalog every bilingual string and `*En` key
- ✅ Remove bilingual subtitles from `HomeScreen.jsx` and `ReportSheet.jsx` (+ single-`label` `typeDefs` in `view.js`)
- ✅ Purify `es.js`, `en.js`, and `pt.js` dictionaries (8 `*En` keys removed from each; all bilingual ` · ` halves stripped; pt Spanish leaks fixed; 443 identical keys)
- ✅ Add CI check that blocks ` · ` separators and `*En` keys (`frontend/scripts/i18n-check.js` → `npm run check:i18n`, wired into `tests.yml`)
- 🚧 Language-specific regression check shipped as a runtime vitest suite (`tests/i18n.test.js`, +5 purity tests); on-device screenshot baselines deferred (text purity is enforced at the dictionary level where the strings originate)

**Shipped in this plan:** the bilingual "Spanish · English" UI pattern is gone — components render one language per element, the three full dictionaries are monolingual with identical 443-key sets (the only remaining middots are legitimate single-language separators on an 11-key allowlist), and both a CI script (`check:i18n`) and a vitest suite block regressions. **Remaining:** optional on-device screenshot baselines per language (es/en/pt); `guc.js` stays intentionally partial and falls back to es.

---

## Plan 23 — Android Mesh Human Chain & Gateway Bridging
**File:** [`plans/plan-23-android-mesh-human-chain.md`](plans/plan-23-android-mesh-human-chain.md)  
**Goal:** Turn the Bluetooth mesh into a true human-chain relay where records hop across offline Android phones until they reach a gateway with internet.

- ✅ Hop limit (`BleConstants.MAX_HOPS=10`): `MeshRepository` rejects over-limit envelopes, withholds maxed-out records from the advertised index, and counts drops (`MeshRepositoryHopLimitTest`).
- ✅ Gateway flag in BLE advertisements — advert service data is now `[version][flags][bloom]`; the gateway bit is set from a 5-min cloud-reachability window (cleared after repeated failures or on stop), parsed onto `PeerDevice.isGateway` with legacy back-compat (`AdvertData` + `AdvertDataTest`).
- ✅ Gateway-aware connection prioritization — `shouldConnect()` prefers gateway peers (shorter cooldown) when local records are pending for the cloud; gateway upload path covered by `MeshChainTest`.
- ✅ Persistent live notification mirroring the PWA top-bar status (peers, queued, gateway/online state) with a "Sincronizar ahora" action; the PWA toggle now starts the foreground service so relaying survives backgrounding.
- ✅ Wi-Fi Direct bulk transfer — `WifiDirectManager` group negotiation (`awaitConnectionInfo`/`runBulkExchange`) wired into `syncBulkRound` with BLE fallback; real socket transfer verified over loopback (`WifiDirectBulkTransferTest`). 🚧 On-device P2P group-owner negotiation still needs paired-device certification.
- ✅ README update explaining the human-chain model (store-and-forward, gateways, ASCII diagram, limits, Android-only/iOS limitation, privacy) in the root README + es/en/pt copies.
- 🚧 Multi-device real-hardware human-chain certification (3-hop relay, return path, battery benchmark) — checklist + battery procedure shipped in `docs/TESTING.md`; rides on the BLE radio certification still pending in plan-16/18.

**Shipped in this plan:** anti-circulation hop limit; gateway discovery + preference routing; a live foreground-service notification as the default mesh path; completed Wi-Fi Direct bulk socket transfer; a PWA mesh screen that shows whether you are a gateway / a gateway is nearby + a hop-limit hint; trilingual README mesh explainer; new JVM (`AdvertDataTest`, `BulkTransferTest` merge) + instrumented (`MeshRepositoryHopLimitTest`, `MeshChainTest`, `WifiDirectBulkTransferTest`) tests. **Remaining:** real-device 3-hop chain sign-off + battery numbers; on-device Wi-Fi Direct group negotiation. **iOS mesh stays explicitly out of scope** (background BLE restrictions, documented).

---

## Plan 24 — User Preferences, Subscriptions & Alerts
**File:** [`plans/plan-24-user-preferences-subscriptions-alerts.md`](plans/plan-24-user-preferences-subscriptions-alerts.md)  
**Goal:** Let users control what they see, what notifies them, and what they relay over the mesh, so EGI does not overwhelm people with information they do not need.

- ✅ Preference data model and local-first storage with server sync (`user_preferences`/`user_settings` + migration 0006, `modules/preferences.py`, `lib/preferences.js`, IndexedDB-first store with timestamp-guarded LWW sync).
- ✅ Settings UI for per-category display/notify/relay toggles (`SettingsScreen.jsx` + `NotificationSettings.jsx`: category grid, near-me radius, quiet hours, batch digest, test-notification; trilingual).
- ✅ Apply preferences to PWA UI, search, map, and notifications (`view.js` gates feed/search/map/shelters tab + near-me radius, `CategoryFilterNote` indicator; server `modules/notifications.py` gate before push fan-out).
- ✅ Apply preferences to mesh relay (Bluetooth bloom filter) (Android per-category relay opt-outs exclude records from the advertised bloom + index served to peers; received-but-disabled records still stored/shown; PWA mesh share-types section).
- ✅ Operation and disaster-specific subscriptions (`modules/subscriptions.py`, `/operations/{id}/subscribe|unsubscribe|mute` + `/subscriptions`, auto-subscribe on report submit, DisasterPicker follow/mute controls).
- ✅ Abuse guardrails: critical alerts bypass toggles; preference changes are auditable (`notify_own_record_match` life-safety bypass, `life_safety` broadcast override, rate-limited + audit-logged preference/subscription writes).

**Why it sits here:** Preferences touch the mesh (Plan 23), notifications (Plan 11), and every future module (animals, hazards, SAR). Building the unified layer before trust/operations/deduplication means later plans only register a new category instead of reimplementing opt-out logic.

---

## Plan 25 — Trust, Safety & Verification
**File:** [`plans/plan-25-trust-safety-verification.md`](plans/plan-25-trust-safety-verification.md)  
**Goal:** Build a trust and verification layer that supports local watchers at hospitals/shelters, remote diaspora moderators, and authorized devices whose trust spreads through the mesh.

- ✅ Identity tiers and device reputation (record trust signals `author_role`/`org_id`/`location_id`/`signature` + server-computed `trust_tier` in `modules/trust.py`; `device_reputation` table/module with 0-100 score + tier; trust badges in PWA `PersonDetail`/`SearchScreen`; migration 0008).
- ✅ Organization and location authorization with QR-code invites (`modules/{organizations,locations,invites}.py` + routes; TOFU-pinned org signing keys, operator verification, watcher authorization; one-time SHA-256 invite links/`claim_url` for QR; user-bound `POST /trust/invites/redeem`; PWA `OrgAdminScreen`).
- ✅ Moderation queue for flagged reports and shelter updates (`moderation_flags` table; public+rate-limited+offline-queued `POST /flags`, operator `GET /flags(+stats)` and resolve; 'deceased' critical-first; flags ding device reputation; PWA `FlagModal` + ModerationScreen Flags tab).
- ✅ Remote moderator onboarding for diaspora volunteers (`moderators` table + `modules/moderators.py`; `/moderators/signup|me|me/trained|me/queue`, region-scoped queue, roster + digest; PWA `ModeratorOnboardingScreen`).
- ✅ Abuse prevention: rate limiting, device bans, audit log (`modules/rate_limit.py` per-device/user caps wired into `/sync`; commander device ban + blocklist bundle `GET /trust/blocklist` enforced in sync + search; every action audited; CLI `egi device ban|unban|list` + `egi moderation stats|flags`).
- 🚧 Android mesh trust carry: `MeshCrypto` ECDSA sign/verify shipped + the envelope codec preserves trust fields verbatim on direct relay, but `PersonEntity` lacks Room columns so store-and-forward drops `author_role`/`org_id`/`location_id`/`signature` until a Room migration; the cloud recomputes `trust_tier` authoritatively on the next gateway sync. Real-device BLE certification rides the pending mesh sign-off (plan-16/18/23).

---

## Plan 26 — SAR Operations Workflow
**File:** [`plans/plan-26-sar-operations-workflow.md`](plans/plan-26-sar-operations-workflow.md)  
**Goal:** Give civilian volunteers and local coordinators lightweight search-and-rescue coordination tools without replacing professional SAR systems.

- ✅ Operation and sector data model (`sar_*` tables namespaced off the plan-09 `events`/`operations` surface; migration `0009`; `modules/sar.py` + `routes/sar.py`: `GET/POST /sar/operations`, `GET /sar/operations/{id}`, `PATCH /sar/operations/{id}[/status]`; auto-grid or manual sectors; persons M2M; timestamp-guarded LWW like `/sync`).
- ✅ Operations UI with status board (`OperationsScreen.jsx` list + create flow with zone/auto-grid; `OperationDetailScreen.jsx` status board — linked persons, sectors grid, task checklist, checked-in volunteers, recent field reports; `'operations'` category-gated tab; trilingual es/en/pt).
- ✅ Sector assignment and task checklist (`SectorCard.jsx` claim/release/check-in/clear/needs-recheck; one-active-volunteer-per-sector conflict → HTTP 409; per-sector task CRUD; `auto_checkout_stale` sweep for stale claims).
- ✅ Field reports over the mesh (server `sar_field_reports` + `POST /sar/operations/{id}/field-reports` + `GET/POST /sar/sync` LWW; `FieldReportSheet.jsx` offline-queued; Android `RecordEnvelope.TYPE_FIELD_REPORT` transport + JVM round-trip test). 🚧 On-device Room persistence of relayed field reports rides the same pending Room-migration/BLE-certification path as plan-25's trust-column carry; the cloud/bridge path is fully working today.
- ✅ Volunteer check-in/check-out (`POST /sar/operations/{id}/join` idempotent + auto-subscribe, `/sar/sectors/{id}/checkin`, `/sar/volunteers/{id}/checkout`; sector flips `in_progress` on check-in).

**Shipped in this plan:** six additive `sar_*` tables (`sar_operations`/`sar_operation_persons`/`sar_sectors`/`sar_tasks`/`sar_volunteers`/`sar_field_reports`) + migration `0009`; `modules/sar.py` + `routes/sar.py` (operation CRUD, sector claim/release/status with 409 conflict, check-in/out, task checklist, field reports with `sighting`→`needs_recheck` / `cleared` side-effects, `found`→registry update gated on operator confirmation, `/sar/sync` mesh/cloud LWW); access model — public reads + volunteer actions, verified-account operation creation, operator-gated `found` confirmation, every mutation audit-logged; PWA `OperationsScreen`/`OperationDetailScreen`/`SectorCard`/`FieldReportSheet` + store/view wiring + DashboardScreen SAR widgets + trilingual i18n (629 shared keys); Android field-report mesh envelope transport; 13 server pytest + 5 frontend vitest. **Remaining:** on-device Room persistence + BLE propagation of field reports (rides the pending mesh certification in plan-16/18/23); ICS-201/CAP interop and invite-only operations are open questions deferred.

---

## Plan 27 — Data Quality & Deduplication Engine
**File:** [`plans/plan-27-data-quality-deduplication.md`](plans/plan-27-data-quality-deduplication.md)  
**Goal:** Keep the registry clean and accurate as records arrive from civilians, hospitals, OCR, SMS, and the mesh.

- ⏳ Exact deduplication (cedula, phone, record ID).
- ⏳ Fuzzy matching with confidence scoring.
- ⏳ Human review queue for merge candidates.
- ⏳ Conflict resolution rules by source trust tier.
- ⏳ OCR and SMS cleanup pipeline.
- ⏳ Mesh-aware merge propagation.
- ⏳ Registry health dashboard.

---

## Plan 28 — Missing Animals (Pets)
**File:** [`plans/plan-28-missing-animals.md`](plans/plan-28-missing-animals.md)  
**Goal:** Add a separate registry for missing and found pets (dogs, cats, and other animals) that reuses the mesh but never mixes with missing-person data.

- ⏳ Animal data model and server endpoints.
- ⏳ Android mesh support for animal records.
- ⏳ Animal report form, search, and detail UI.
- ⏳ Shelter animal board.
- ⏳ Animal-specific deduplication.
- ⏳ User preferences to opt out of animal content/notifications/mesh forwarding.

---

## Plan 29 — UX Audit & Pre-Flight Checks
**File:** [`plans/plan-29-ux-audit-and-preflight.md`](plans/plan-29-ux-audit-and-preflight.md)  
**Goal:** Run a systematic visual and UX audit as the final step before calling the product polished, then keep a lightweight pre-flight process for every release.

- ⏳ Screenshot baseline of every major screen.
- ⏳ Automated Lighthouse + axe accessibility checks.
- ⏳ Fix known issues: wordmark, background color, shelter lat/lon input.
- ⏳ Design tokens and component audit.
- ⏳ Manual pre-flight checklist.

**Why last:** UX polish should happen after the functional layers (mesh, trust, operations, data quality, animals) are stable, so the audit captures the real final product rather than screens that will change again.

---

## How to use this roadmap

1. Pick a plan file for the area you want to work on.
2. Implement the pending items in the suggested order.
3. Update the status emoji in this file (and the **Last updated** date and **At a glance** table) when a phase ships.
4. Add new plans (`plan-14-*.md`) when the project outgrows the current set.

---

## Cross-cutting priorities

These apply to every plan:

- **Privacy:** collect the minimum, mark unverified data, prefer corrections over silent deletion.
- **Interoperability:** keep records PFIF-aligned; import/export should round-trip.
- **Offline-first:** every feature should degrade gracefully without internet.
- **Test coverage:** new behavior needs a test; manual-only features need a checklist entry.
- **Spanish-first UI:** other languages are welcome, but the crisis context is Spanish-speaking.

---

## Suggested next milestones

### Milestone A — Safe public beta (short term) — ✅ largely shipped
- ✅ Plan 06 IndexedDB + honest auth.
- ✅ Plan 07 CORS, rate limiting, operator/RBAC auth (Plan 08).
- ✅ Cédula search UI.

### Milestone B — Field-ready mesh (medium term) — ✅ code complete
- ✅ Plan 16: reports-over-mesh, live mesh UI, Wi-Fi Direct bulk, duty-cycling + foreground service.
- ✅ SMS text-only check-in full flow + native Android FCM client.
- ✅ Warning-free Kotlin build + real Room migrations.
- 🚧 Run manual BLE tests on real devices (checklist + automation shipped; hardware sign-off pending).

### Milestone C — Operational maturity (long term) — ✅ largely shipped
- ✅ Plan 11 communications hub (SMS two-way, email, push, alerts, delivery tracking) — live behind the default `log` drivers; add real provider creds to go live.
- ✅ Plan 13 (dashboards, data-quality scoring, suggested sectors, SITREP generator + scheduled reports, PWA dashboard).
- ✅ Plan 10 photos table + offline maps and map view (face-blur + bbox-draw tool deferred).
- ✅ Plan 12 CSV/Excel, PDF flyers, webhooks, federation.

### Milestone D — Inclusive, production-ready service (long term) — ✅ largely shipped
- ✅ Plan 14 inclusive crisis access: WhatsApp/Telegram bots, voice notes, on-device translation (+ Wayuu), panic/low-literacy mode, printable shelter posters — live behind the default `log` bot drivers.
- ✅ Plan 15 production operations: structured health/metrics, JSON logs + request-id tracing, automated encrypted/offsite backups + restore drills, migration runner + system events, load tests + SLOs, CI security scans + credential rotation, operations manual + example alerts.

### Milestone E — Finish line: remaining polish (long term) — 🚧 in progress
- 🚧 Plan 17: event/city selector, OCR review TUI, draw-a-box map search, face-blur, faster-whisper voice backend, native Android ML Kit packs, full PostgreSQL runtime.

### Milestone F — Next wave: mesh, preferences, trust, operations, and polish (long term) — 🚧 in progress
- 🚧 Plan 23: human-chain mesh with gateway bridging, live notification, and README.
- ⏳ Plan 24: user preferences, subscriptions & alerts (not animal-only — applies to all categories).
- ✅ Plan 25: trust, safety, and verification (watchers, remote moderators, authorized devices) — server + PWA shipped; Android mesh signing shipped, store-and-forward field carry partial.
- ✅ Plan 26: civilian SAR operations workflow (server + PWA shipped; Android mesh field-report transport shipped, on-device Room persistence partial).
- ⏳ Plan 27: data-quality and deduplication engine.
- ⏳ Plan 28: missing animals registry with preferences handled by Plan 24.
- ⏳ Plan 29: final UX audit and pre-flight checklist.
