# EGI Testing & Quality

Lightweight, practical tests meant to run on every change and catch real breakage
in a crisis tool. Implements `docs/plans/plan-03-testing-and-quality.md`.

## Running the tests

### Server (Python / FastAPI) — `pytest`

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt   # runtime deps + pytest + httpx
pytest
```

Tests live in `server/tests/`:

| File | Covers |
|------|--------|
| `test_db.py`  | schema creation, the `status` CHECK constraint, idempotent init, the PFIF column migration, basic CRUD |
| `test_sync.py`| `/sync` upload+download round-trip, `/persons` filters (q, status, location, disaster_id, cedula, since), conflict resolution (newer timestamp wins / stale write skipped), invalid-status rejection, reports round-trip |
| `test_ocr.py` | `/import/paper` draft creation with the **OCR engine and LLM mocked**, the review/publish flow, and `extract_with_llm` skip/mock paths |

Each test gets a fresh temp SQLite DB via the `temp_db` / `client` fixtures in
`conftest.py` (a temp **file**, not `:memory:`, because `db.get_db()` opens a new
connection per call). No Tesseract binary or LLM provider key is required — the OCR
tests stub `main.ocr_image` and mock the `prompture` extraction.

### Web app (PWA) — `vitest`

```bash
cd frontend
npm install
npm test            # vitest run
npm run build       # must still succeed
```

Tests live in `frontend/tests/`:

| File | Covers |
|------|--------|
| `indexeddb.test.js` | offline read/write/delete of the local queue. NOTE: the app persists to **localStorage**, not IndexedDB — the pure helpers in `src/lib/offlineQueue.js` mirror the `egi.pendingRecords` contract in `src/store.js` |
| `form.test.js` | person-record validation in `src/lib/validatePerson.js` (required name, valid status, sane age, loose cédula format) |

### Android (Kotlin) — JVM unit tests

```bash
cd mobile/android
./gradlew test       # requires the Android SDK / Gradle toolchain
```

Tests live in `mobile/android/app/src/test/`:

| File | Covers |
|------|--------|
| `mesh/EnvelopeCodecTest.kt`   | record envelope + index serialization/deserialization, `relayed()` hop increment |
| `mesh/BloomFilterTest.kt`     | the BLE-advert bloom filter — no false negatives, byte round-trip |
| `data/RecordMappersTest.kt`   | `isNewer` (sync index diff core), entity↔sync-JSON mapping, camelCase/snake_case casing rule |

BLE hardware exchange is **manual** — see the checklist below.

## CI

`.github/workflows/tests.yml` runs the server `pytest` suite and the frontend
`vitest` suite + build on every push and pull request.

`.github/workflows/android.yml` (plan-16 Phase 8) runs the Android module in
`mobile/android` on every push and pull request:

- **JVM unit tests** — `./gradlew test` on JDK 17 with Gradle caching.
- **Instrumented (emulator) tests** — `./gradlew connectedCheck` on an API-30
  `default` x86_64 AVD via `reactivecircus/android-emulator-runner`, with AVD
  snapshot caching. Requires KVM hardware acceleration on the runner.

BLE radio exchange, Wi-Fi Direct, foreground-service survival, battery drain, SMS
and FCM delivery cannot run on an emulator — certify them by hand on real devices
(see the BLE certification checklist below).

## Manual test checklist

Things that are hard to automate — tick these before a release:

- [ ] Two Android phones exchange a record over BLE with no internet.
- [ ] One phone gets internet; cloud receives the merged dataset.
- [ ] Web PWA works fully offline after first load.
- [ ] OCR import creates an unreviewed draft.
- [ ] Moderator review publishes the draft and it syncs.
- [ ] Search by cédula returns the correct person.
- [ ] Duplicate reports do not create duplicate persons.
- [ ] Large photo upload does not crash sync.

## Manual BLE certification (plan-16)

Field-readiness of the Android mesh and native comms layer **cannot** be proven by
the emulator CI — BLE radio, Wi-Fi Direct, the foreground service, battery, SMS and
FCM all need real hardware. Certify on **at least two real devices** before a mesh
release and sign off below.

**Run metadata**

- Date: ________________  Build / versionName: ________________
- Device A — model / OS: ____________________________________
- Device B — model / OS: ____________________________________
- Device C (bridge) — model / OS: ___________________________
- Certified by: __________________  Result (PASS / FAIL): ________

**Checklist**

- [ ] **PERSON over BLE, offline.** Both phones in airplane mode (Bluetooth on, no
      Wi-Fi/cellular). A registers a person; B receives the record over BLE and shows
      it. Records used: ____________________
- [ ] **REPORT over BLE, offline.** Same offline setup. A attaches a report to an
      existing person; B receives the report and it appears in that person's timeline.
- [ ] **Third phone bridges to cloud.** C carries the merged dataset, regains Wi-Fi,
      syncs; person + report appear via `GET /sync` and in the PWA. Verified via
      (URL / PWA): ____________________
- [ ] **Wi-Fi Direct bulk transfer.** Transfer of >50 records or a photo batch falls
      back to Wi-Fi Direct and merges identically to the BLE path (no dupes, no loss).
      Record/photo count: ____________________
- [ ] **Mesh survives backgrounding ≥10 min.** App backgrounded for at least 10
      minutes; foreground-service notification stays visible; peers re-discover and
      sync afterward. Elapsed: ______ min.  Notification visible: [ ] yes
- [ ] **Battery drain measured (30 min).** Normal mode, ~30 min mesh run; record the
      delta. Start %: ____  End %: ____  Drain: ____ %/hr (target < 5%/hr).
- [ ] **SMS check-in.** Send `EGI CHECKIN <cedula> <name> <location>`; a local record
      is created with `source='sms'`, syncs to the cloud, and lands **unreviewed**
      (`reviewed=0`) in the moderation queue.
- [ ] **FCM native alert.** With `google-services.json` configured, an FCM alert for a
      subscribed operation is received natively and forwarded into the PWA.
- [ ] **Sign-off.** All of the above PASS on both devices; notes / accepted issues:
      ____________________________________________________________

## Quality gates

Before merging a feature:

1. Server tests pass (`cd server && pytest`).
2. New behavior has at least one test.
3. Manual checklist updated if needed.
4. No hardcoded secrets.
5. Privacy-sensitive fields (names, contacts, locations, cédulas) handled carefully —
   collect the minimum, mark unverified reports, prefer corrections/history over
   silent deletion, add no analytics/tracking.

## Test data policy

- **Never** commit real cédulas, names, or photos.
- Use obviously fake data: `Juan Pérez de prueba`, `V-00000000`.
- Mark fixtures with a `TEST DATA — NOT REAL` comment.
