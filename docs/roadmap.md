# EGI Roadmap

This is the single source of truth for where EGI is going. Each plan is a self-contained document in [`docs/plans/`](plans/). Status is maintained by hand; update it when a phase ships.

---

## Legend

- ✅ Done
- 🚧 In progress
- ⏳ Pending
- 🛑 Blocked / deferred

---

## Plan 01 — Foundations & Alignment
**File:** [`plans/plan-01-foundations.md`](plans/plan-01-foundations.md)  
**Goal:** Define what EGI is, align the stack with the bridge-node vision, and outline the PFIF-aligned data model.

- ✅ Offline-first web PWA
- ✅ FastAPI server + SQLite
- ✅ Android folder + WebView direction
- ✅ PFIF-style schema (`events`, `cities`, `reports`, `incidents`)
- ✅ Basic person + report records
- ⏳ Event + city selectors in PWA
- ⏳ Self check-in flow
- ⏳ Search by cédula and name (UI)
- ⏳ Offline map tiles

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
- 🚧 Reports (PFIF notes) over the mesh
- 🚧 GATT encryption + privacy warning
- 🚧 Mesh UI in the PWA
- ⏳ Wi-Fi Direct bulk transfer
- ⏳ Relay duty-cycling + foreground service
- ⏳ SMS text-only check-in

---

## Plan 03 — Testing & Quality
**File:** [`plans/plan-03-testing-and-quality.md`](plans/plan-03-testing-and-quality.md)  
**Goal:** Fast, practical tests that catch real breakage.

- ✅ Server pytest suite (`test_sync.py`, `test_db.py`, `test_ocr.py`)
- ✅ Frontend vitest suite (`form.test.js`, `indexeddb.test.js`)
- ✅ CI workflow for server + frontend tests
- ✅ Kotlin JVM unit tests (envelope, bloom filter, mappers)
- ✅ Manual test checklist
- 🚧 Android emulator/instrumented tests in CI
- ⏳ BLE hardware manual test certification

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
- 🚧 `egi export-pfif` / `egi import-pfif` CLI commands
- ⏳ XML PFIF export
- ⏳ OCR review TUI helper

---

## Plan 05 — Mesh Hardening & Data Quality
**File:** [`plans/plan-05-mesh-hardening-and-data-quality.md`](plans/plan-05-mesh-hardening-and-data-quality.md)  
**Goal:** Complete the mesh, add data-quality features, and make the Android build field-ready.

- ✅ Fuzzy duplicate detection (`/duplicates/pending`, merge, reject)
- ✅ Confidence-based status derivation (`self > official > witness > ocr`)
- ✅ Moderation queue (`/moderation/pending`, approve, reject, stats)
- ✅ `dedup_rejections` table to avoid re-suggesting rejected clusters
- ✅ Soft-merge preserves history
- 🚧 Reports over mesh
- 🚧 GATT encryption
- 🚧 Mesh UI in PWA
- ⏳ Wi-Fi Direct bulk socket transfer
- ⏳ Duty-cycling + foreground service
- ⏳ SMS fallback
- ⏳ Warning-free Kotlin build + real Room migrations

---

## Plan 06 — Product & UX Hardening
**File:** [`plans/plan-06-product-and-ux-hardening.md`](plans/plan-06-product-and-ux-hardening.md)  
**Goal:** Make the PWA usable, trustworthy, and resilient in a real crisis.

- ⏳ Migrate offline cache from `localStorage` to IndexedDB
- ⏳ Replace fake Google auth with honest guest/alias flow
- ⏳ i18n scaffold (es / en / pt)
- ⏳ Accessibility pass (Lighthouse ≥ 90)
- ⏳ Redesign home with three clear actions
- ⏳ Fast sighting and safe-registration flows
- ⏳ Prominent cédula search + scan
- ⏳ Pagination in `/persons`
- ⏳ Mesh status UI
- ⏳ Moderator UI in the PWA

---

## Plan 07 — Security, Privacy & Operations
**File:** [`plans/plan-07-security-privacy-and-operations.md`](plans/plan-07-security-privacy-and-operations.md)  
**Goal:** Protect crisis data and make public deployment repeatable.

- ⏳ CORS restricted to known origins
- ⏳ Security headers middleware
- ⏳ Rate limiting on write endpoints
- ⏳ Operator bearer-token auth for moderation
- ⏳ Photo upload access control (disabled by default)
- ⏳ Audit logging for moderator actions
- ⏳ VPS / Docker deployment guide
- ⏳ `egi backup` + restore command
- ⏳ Data retention + anonymization policy
- ⏳ Security review checklist

---

## How to use this roadmap

1. Pick a plan file for the area you want to work on.
2. Implement the pending items in the suggested order.
3. Update the status emoji in this file when a phase ships.
4. Add new plans (`plan-08-*.md`) when the project outgrows the current set.

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

### Milestone A — Safe public beta (short term)
- Finish Plan 06 Phases 1–2 (IndexedDB + honest auth).
- Finish Plan 07 Phases 1–3 (CORS, rate limiting, operator auth).
- Ship cédula search UI.

### Milestone B — Field-ready mesh (medium term)
- Finish Plan 05 remaining items (encryption, mesh UI, duty-cycling).
- Complete reports-over-mesh.
- Run manual BLE tests on real devices.

### Milestone C — Operational maturity (long term)
- Finish Plan 07 (deployment guide, backups, retention).
- Add photos with privacy controls.
- Add offline maps and rescuer view.
