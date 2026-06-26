# EGI Server (Python)

A FastAPI + SQLite sync server for EGI. Designed to be small, easy to deploy, and ready for OCR + structured LLM extraction via [Prompture](https://github.com/jhd3197/prompture).

## Requirements

- Python 3.10+
- Tesseract OCR installed (see below), OR `easyocr` in `requirements.txt`.
- Prompture installed (local editable install points to `C:/Users/Juan/Documents/GitHub/prompture` by default).

## Install Tesseract

- **Windows**: download installer from https://github.com/UB-Mannheim/tesseract/wiki or use Chocolatey: `choco install tesseract`.
- **macOS**: `brew install tesseract tesseract-lang`.
- **Ubuntu/Debian**: `sudo apt install tesseract-ocr tesseract-ocr-spa`.

Edit `TESSERACT_CMD` in `.env` if the binary is not on PATH.

## Setup

```bash
cd server
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# edit .env if needed
python -m db
uvicorn main:app --host 0.0.0.0 --port 3000 --reload
```

Initialize the database:

```bash
python -m db
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve the EGI web app (frontend) |
| GET | `/health` | Health check |
| GET | `/persons` | Search records (q, status, location, disaster_id, since, limit) |
| GET | `/persons/{id}` | Get one record |
| POST | `/sync` | Upload a batch of records from web/mobile |
| GET | `/sync?since=ISO8601` | Download records changed since timestamp |
| POST | `/import/paper` | Upload a paper image; OCR + optional LLM extraction |
| GET | `/import/paper` | List OCR draft records |
| GET | `/import/paper/{id}` | Get one OCR record |
| POST | `/import/paper/{id}/review` | Approve/edit an OCR record |

Uploaded images are saved to `uploads/` and served at `/uploads/{filename}`.

## OCR / paper import flow

1. A volunteer or family member takes a photo of a paper list.
2. `POST /import/paper` runs OCR and optionally calls an LLM to extract fields.
3. The server creates a draft record with `source='ocr'` and `reviewed=0`.
4. A moderator reviews the record and calls `POST /import/paper/{id}/review` to publish it.
5. The record then syncs normally to all clients.

Provenance is stored so users can see: *"Extracted from uploaded paper image 'foto.jpg' via OCR"*.

## LLM extraction with Prompture

Set in `.env`:

```env
LLM_MODEL=openai/gpt-4o-mini
```

Prompture supports many providers under the `provider/model` string:

- `openai/gpt-4o-mini`
- `groq/llama-3.1-8b-instant`
- `ollama/llama3.1:8b`
- `claude/claude-sonnet-4-6`
- `google/gemini-1.5-pro`

Provider API keys are read from standard env vars (`OPENAI_API_KEY`, `GROQ_API_KEY`, etc.).

If `LLM_MODEL` is not set, OCR records are created with raw text only and must be completed manually.

## Deployment

Use `gunicorn` + `uvicorn.workers.UvicornWorker` or run with systemd. Put behind HTTPS with Caddy or Nginx.

Back up `data/egi.db` and `uploads/` regularly.
