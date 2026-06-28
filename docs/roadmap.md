# EGI Roadmap

This is the single source of truth for where EGI is going. Each plan is a self-contained document in [`docs/plans/`](plans/). Status is maintained by hand; update it when a phase ships.

**Last updated:** 2026-06-28 (plan-19 mostly shipped: self-hosted offline fonts, native `/sync`+`/persons` bridge from Room in the WebView, CDP-driven PWA smoke tests — guest/alias/report all green on Samsung SM-S134DL and Moto G Play 2023 — perceptual visual regression, hands-free permission/consent dialog handling, and CI; two-device mesh propagation remains blocked by Android's BLE scan-window throttle and is tracked for plan-18).

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
| 20 | Shelter & refugee information hub | ⏳ pending (plan drafted) |
| 21 | Offline routing: from X to Y | ⏳ pending (plan drafted) |
| 22 | i18n language purity audit & fix | ⏳ pending (plan drafted; Spanish currently leaks English due to bilingual `*En` keys and ` · ` separators) |

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

- ⏳ Shelter detail card with capacity, services, contact, and supply needs
- ⏳ "How to get there" directions from current location or any origin
- ⏳ Official shelter feed / updates from verified staff
- ⏳ "I am here" shelter check-in flow
- ⏳ Verified shelter operator mode + token management

---

## Plan 21 — Offline Routing: From X to Y
**File:** [`plans/plan-21-offline-routing-x-to-y.md`](plans/plan-21-offline-routing-x-to-y.md)  
**Goal:** Provide offline-capable directions between any two points relevant to EGI users (shelters, people, hazards, evacuation corridors).

- ⏳ Basic directions UI with straight-line distance + walking time
- ⏳ Cached road-network routing packs + Web Worker graph search
- ⏳ Native Android turn-by-turn bridge
- ⏳ Hazard-aware routing
- ⏳ Route sharing over mesh
- ⏳ Multi-modal and long-distance evacuation routing

---

## Plan 22 — i18n Language Purity Audit & Fix
**File:** [`plans/plan-22-i18n-language-purity-audit.md`](plans/plan-22-i18n-language-purity-audit.md)  
**Goal:** Remove mixed-language UI so Spanish shows only Spanish, English only English, and Portuguese only Portuguese.

- ⏳ Audit and catalog every bilingual string and `*En` key
- ⏳ Remove bilingual subtitles from `HomeScreen.jsx` and `ReportSheet.jsx`
- ⏳ Purify `es.js`, `en.js`, and `pt.js` dictionaries
- ⏳ Add CI check that blocks ` · ` separators and `*En` keys
- ⏳ Language-specific screenshot baselines / regression check

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
