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
`vitest` suite + build on every push and pull request. Android tests are not yet
wired into CI (no SDK in the runner); add a `ktlint`/Android-lint job when the app
matures.

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
