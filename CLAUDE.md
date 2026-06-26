# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What EGI is

EGI (Emergencia · Gente · Info) is an offline-first, self-hostable system for family reunification after a disaster. People register others as `missing`, `found`, `safe`, `deceased`, `sighted`, or `care`; data is stored locally on the device first and synced to a community-run server when connectivity returns. A future Android app is planned for Bluetooth LE mesh sync between nearby phones.

The repo has three parts that are loosely coupled by an HTTP sync contract:
- `server/` — Python + FastAPI + SQLite sync hub (the live, working backend).
- `frontend/` — offline-first PWA prototype (the live, working client).
- `mobile/android/` — planned/partially-scaffolded Android app (mostly direction docs).

User-facing strings are Spanish-first; code comments and English strings are the default per `CONTRIBUTING.md`.

## Server (`server/`)

FastAPI app, single SQLite table. This is where almost all real logic lives.

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # edit if needed
python -m db                    # initialize ./data/egi.db
uvicorn main:app --host 0.0.0.0 --port 3000 --reload
```

The server also serves the frontend: with it running, the full app is at `http://localhost:3000`. `python -m db` (i.e. `db.init_db()`) is idempotent and runs automatically on app startup too.

There is no test suite yet. The `npm test` line in `CONTRIBUTING.md` refers to the **deprecated** Node.js server in `server/_legacy_nodejs/` — ignore it; the Python server is canonical.

### Architecture notes

- **`main.py`** is now just app wiring: middleware, `/uploads` mount, `/health`, `include_router()` calls, and the catch-all `GET /{path:path}` that serves the SPA and **must stay last** so API routes take precedence. It re-exports `ocr_image`/`extract_with_llm` and defines `UPLOAD_DIR` because the OCR import route reads those off `main` at request time (the surface the tests monkeypatch). Routes live in `routes/` (thin HTTP adapters: `persons.py`, `sync.py`, `imports.py`, `events.py` — note `imports.py`, not `import.py`, since `import` is reserved), and business logic in `modules/` (`persons`, `reports`, `sync`, `events`, `ocr_import`). Pydantic models and the `validate_status`/`now_iso` helpers are centralized in **`models.py`**.
- **`db.py`** defines the schema inline in the `SCHEMA` string (there is **no separate `schema.sql` file** — an open `schema.sql` buffer in the IDE is empty/non-existent). `get_db()` is a context manager opening a fresh connection per call with WAL mode. The valid `status` values are enforced both by a SQLite `CHECK` constraint here and by `validate_status()`/`VALID_STATUSES` in `models.py` — keep the two lists in sync.
- **`ai.py`** is the local-first multi-provider AI base (`BaseExtractor`): default provider is **Ollama** (local, no API key) with **OpenAI** as an opt-in fallback, configured via `AI_PROVIDER`/`AI_MODEL`. `available()` cheaply checks reachability, `query()` returns raw text or `None`, and `parse_json()` robustly recovers JSON (strips `<think>` blocks and ``` fences, slices the object, drops trailing commas). It never raises and degrades to `None` so AI is always optional. Used by `modules/normalize.py` (the `POST /normalize` free-text→`ai_draft` flow) and as the OCR fallback when `LLM_MODEL` is unset.
- **`research/synthetic.py`** generates fake person records for demos/load tests (`egi generate-synthetic`): internal name dictionary, cédulas in the reserved fake sub-range `V-00500000…` (offset from `egi seed`), weighted statuses, deterministic RNG so `--dry-run` matches a real run. Rows are `source='synthetic'` with a `TEST DATA` provenance, so `egi unseed` removes them.
- **`ocr.py`** handles the paper-import pipeline: `ocr_image()` preprocesses with Pillow then tries pytesseract, falling back to easyocr if installed; `extract_with_llm()` calls Prompture's `extract_with_model()` against the `ExtractedPaperReport` schema. If `LLM_MODEL` is unset, extraction is skipped and the OCR record holds raw text only.
- **Sync model:** `POST /sync` upserts keyed on the client-supplied `id` with **timestamp-guarded last-write-wins**: an incoming record is skipped when its `updatedAt` is older than the stored row's `updated_at` (ISO-8601 UTC compared lexicographically), so a stale mesh relay arriving out of order can't clobber a newer update. The response includes a `skipped` count. `GET /sync?since=ISO8601` returns records with `updated_at > since`. Clients own their record IDs and timestamps.
- **Moderation queue (`modules/moderation.py`, `routes/moderation.py`):** untrusted records (`source` in `ocr`/`ai_draft`/`pfif_import`, plus anything `reviewed=0`) await review. `reviewed` is the trust flag: `0` pending, `1` approved, `-1` rejected (soft-delete — chosen over a `status='rejected'` value so the six valid statuses stay untouched). `GET /moderation/pending`, `POST /moderation/{id}/approve|reject`, `GET /moderation/stats`. The public `GET /persons` search applies the trust gate: it hides `reviewed=-1` and unreviewed untrusted-source rows, but keeps trusted web/seed rows (`reviewed=0`, `source='web'`) visible — don't tighten this to "all reviewed=0" or normal web reports vanish.
- **OCR review flow:** `POST /import/paper` creates a draft with `source='ocr'` and `reviewed=0`. It stays out of the trusted set until a moderator calls `POST /import/paper/{id}/review` (which defaults `reviewed` to 1). Provenance is recorded so users can see which image a record came from.
- **Field name mismatch:** the API/JSON uses camelCase `createdAt`/`updatedAt` on `PersonRecord`, but the DB columns are snake_case `created_at`/`updated_at`. `main.py` maps between them explicitly in the sync INSERT — watch this when adding fields.

### Config (`.env`)

`PORT`, `DB_PATH`, `UPLOAD_DIR`, `FRONTEND_DIR`, `TESSERACT_CMD`, and `LLM_MODEL` (format `provider/model`, e.g. `openai/gpt-4o-mini`). Provider keys come from standard env vars (`OPENAI_API_KEY`, etc.). OCR needs a Tesseract binary installed; point `TESSERACT_CMD` at it if not on PATH.

## Frontend (`frontend/`)

A **React + Vite** app. `npm install` then `npm run dev` (port 5173, proxies the API routes to the Python server on :3000); `npm run build` outputs `frontend/dist/`, which FastAPI serves in production. (It was rewritten from an earlier single-file `.dc`-template prototype that used a generated `support.js` runtime — that prototype is gone.)

Architecture (state flows one way; components are presentational):
- **`src/store.js`** — `useEgi()` hook holds *all* app state in one object with a `setState`-style merge helper, plus the offline cache/sync logic (`fetchAll`, `syncNow`, `queueRecord`) and every action. This is the port of the old `Component` class.
- **`src/lib/view.js`** — `buildView(state, actions)` derives all display-ready values (decorated people, chips, connection styling, responsive flags) in one place. Ported from the prototype's `renderVals()`. Screens read from this `view` object and stay dumb.
- **`src/lib/css.js`** — `css('padding:16px;…')` turns an inline CSS string into a React style object. The whole UI uses inline styles (carried over verbatim from the prototype); merge dynamic values with `{...css('…'), background: x}`.
- **`src/App.jsx`** routes between three states: `showAuth` → `AuthScreen`, `showPicker` → `DisasterPicker`, else `AppShell` (sidebar/topbar/tabbar + the five screens + `ReportSheet`).
- **Sync/offline:** same-origin relative API URLs by default; `localStorage.setItem('egi_api_url', …)` overrides for a remote server. On load it pulls `/sync` + `/persons`; offline it falls back to `localStorage`; new reports queue locally and `POST /sync` when back online.

Note: the prototype's `renderVals` never exposed `showAuth`, so the polished auth screen never rendered and reporting was unreachable for fresh users. The rewrite wires the intended flow (auth → picker → app), which is why `view.js` defines `showAuth/showPicker/showApp` coherently.

## `egi` CLI (`egi_cli/`)

A repo-root Click CLI (`pip install -e .` → `egi` command) wraps dev and data-ops tasks: `backend`, `frontend`, `build`, `seed`, `unseed`, `export-pfif`, `import-pfif`, `generate-synthetic`, `ocr-review`. It is a **dev/operator tool, kept out of the production PWA/APK**. The command group is in `egi_cli/cli.py`; each command is its own module in `egi_cli/commands/`. Command callbacks import server modules **lazily** (after `paths.ensure_server_importable()`, which also loads `server/.env` and pins `DB_PATH`/`UPLOAD_DIR` to `server/`), so the CLI always touches the same DB as a running `egi backend` no matter the CWD. Keep top-level imports in command modules to `click` only.

## Owned dependency: Prompture

`requirements.txt` installs Prompture as an editable local install from `C:/Users/Juan/Documents/GitHub/prompture`. Per the user's policy, Prompture (and Tukuy) are owned repos — if a bug surfaces there while working on EGI, fix it at the source in that repo rather than working around it here, then verify the fix from EGI.

## Cross-cutting conventions

- New status values must be added in three places: the SQLite `CHECK` in `db.py`, `VALID_STATUSES` in `models.py`, and the `status` description in `ocr.py`'s `ExtractedPaperReport`.
- This data is sensitive (names, contacts, locations of people in a crisis). Follow the privacy principles in `README.md`: collect the minimum, mark unverified reports clearly, prefer corrections/history over silent deletion, and add no analytics/tracking.
