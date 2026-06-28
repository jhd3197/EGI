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
| `mesh/AdvertDataTest.kt`      | advert `[version][flags][bloom]` codec + gateway flag parsing, legacy-format back-compat (plan-23) |
| `data/RecordMappersTest.kt`   | `isNewer` (sync index diff core), entity↔sync-JSON mapping, camelCase/snake_case casing rule |
| `BulkTransferTest.kt`         | Wi-Fi Direct bulk framing/reassembly across chunk boundaries, `shouldUseWifiDirect` threshold, LWW merge of the streamed set |

Instrumented tests (run on a device/emulator, `mobile/android/app/src/androidTest/`):

| File | Covers |
|------|--------|
| `data/MeshRepositoryReportMergeTest.kt` | report envelope upsert + last-write-wins over real Room |
| `data/MeshRepositoryHopLimitTest.kt`    | hop limit (plan-23): under-limit stored+relayed, at-limit stored-not-relayed, over-limit rejected + counted |
| `MeshChainTest.kt`                       | mesh-received record becomes pending-for-cloud (gateway upload path); relay increments + re-emits hop_count |
| `wifi/WifiDirectBulkTransferTest.kt`     | real `sendBulk`/`receiveBulk` socket transfer over loopback, envelope integrity |

BLE radio exchange is **manual** — see the certification checklists below.

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

## Manual human-chain certification (plan-23)

The human-chain relay — records hopping across several offline phones until one
reaches a gateway, then leaping to the cloud — cannot be proven on an emulator.
Certify on **at least three real devices** (four to verify the return path) before
a mesh release.

**Run metadata**

- Date: ________________  Build / versionName: ________________
- Phone A (gateway, has internet) — model / OS: _____________________
- Phone B (offline relay) — model / OS: ____________________________
- Phone C (offline origin) — model / OS: ___________________________
- Phone D (cloud verifier) — model / OS: ___________________________
- Certified by: __________________  Result (PASS / FAIL): ________

**Chain checklist**

- [ ] **Gateway is advertised.** A has internet and mesh on; in the PWA mesh screen A
      shows the *"Eres un puente a la nube"* badge. B/C (offline) show *"Hay un puente
      a la nube cerca"* when within Bluetooth range of A.
- [ ] **3-hop relay to cloud.** C (offline) creates a report. C syncs with B; B syncs
      with A; A uploads to the cloud. Record appears via `GET /sync` and in the PWA.
      Hops observed on the record (PWA / `hop_count`): ______
- [ ] **Return path.** D edits/creates a record in the cloud; A pulls it; A → B → C
      relay it down so C (still offline) shows the cloud update. Verified on C: [ ] yes
- [ ] **Gateway-aware routing.** With C holding a pending record, C preferentially
      connects to the gateway peer (A) over a non-gateway peer (B) — confirm via the
      `Prioritizing gateway peer …` log line. Observed: [ ] yes
- [ ] **Hop limit holds.** Bounce a record around a dense cluster; confirm `hop_count`
      stops at `MAX_HOPS` (10) and the record stops being re-advertised (no runaway
      circulation / battery burn). Max hop seen: ______
- [ ] **Gateway demotion.** Take A offline; after a couple of failed cloud syncs A
      stops advertising the gateway flag and peers no longer show it as nearby.

**Battery benchmark procedure (plan-23 §8)**

1. Charge the test phone to a known level; note start %. Close other apps.
2. Enable mesh (normal duty cycle), background the app, leave it 30 minutes near at
   least one peer so the radio actually cycles.
3. Note end %. Drain rate = `(start − end) / 0.5` %/hr. Target **< 5 %/hr** in normal
   mode; repeat with battery-saver on (longer sleep) and confirm a lower rate.
4. The `DutyCycler` logs a per-cycle summary every 30 cycles (`adb logcat | grep
   "Duty cycle #"`) — capture one line for the record.

- Normal: start ____ % → end ____ % → ____ %/hr.  Saver: ____ %/hr.

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
