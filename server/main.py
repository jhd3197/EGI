"""EGI Sync Server — FastAPI app wiring only.

Business logic lives in ``modules/`` and the HTTP layer in ``routes/``. This file
just builds the app, configures middleware/uploads, includes the routers, and
serves the SPA via a catch-all that MUST stay last so API routes win.

``ocr_image`` / ``extract_with_llm`` are re-exported here (and ``UPLOAD_DIR`` is
defined here) because the OCR import route reads them off this module at request
time — this is the surface the test suite monkeypatches.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

import db
from ocr import ocr_image, extract_with_llm  # noqa: F401  (re-exported as test hooks)
from routes import duplicates as duplicates_routes
from routes import events as events_routes
from routes import imports as imports_routes
from routes import moderation as moderation_routes
from routes import persons as persons_routes
from routes import sms as sms_routes
from routes import sync as sync_routes

load_dotenv()

app = FastAPI(title="EGI Sync Server")

PORT = int(os.environ.get("PORT", "3000"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", "../frontend/dist")).resolve()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded images
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def startup():
    db.init_db()


@app.get("/health")
def health():
    return {"ok": True, "service": "EGI Sync Server (Python)"}


# API routers. Included before the SPA catch-all so they take precedence.
app.include_router(persons_routes.router)
app.include_router(sync_routes.router)
app.include_router(imports_routes.router)
app.include_router(events_routes.router)
app.include_router(moderation_routes.router)
app.include_router(duplicates_routes.router)
app.include_router(sms_routes.router)


# Serve the frontend SPA. API routes above take precedence.
@app.get("/{path:path}")
def serve_frontend(path: str):
    requested = FRONTEND_DIR / path
    if requested.is_file():
        return FileResponse(requested)
    # For SPA routes, fall back to index.html so the client router takes over.
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend not built")


if __name__ == "__main__":
    import uvicorn

    db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
