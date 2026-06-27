"""EGI Sync Server — FastAPI app wiring only.

Business logic lives in ``modules/`` and the HTTP layer in ``routes/``. This file
just builds the app, configures middleware/uploads, includes the routers, and
serves the SPA via a catch-all that MUST stay last so API routes win.

``ocr_image`` / ``extract_with_llm`` are re-exported here (and ``UPLOAD_DIR`` is
defined here) because the OCR import route reads them off this module at request
time — this is the surface the test suite monkeypatches.
"""

import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from dotenv import load_dotenv

import db
from metrics import metrics, route_template
from modules import health as health_mod
from ocr import ocr_image, extract_with_llm  # noqa: F401  (re-exported as test hooks)
from security import SecurityHeadersMiddleware, cors_kwargs
from version import __version__
from routes import action_plans as action_plans_routes
from routes import alerts as alerts_routes
from routes import auth as auth_routes
from routes import bots as bots_routes
from routes import duplicates as duplicates_routes
from routes import events as events_routes
from routes import exchange as exchange_routes
from routes import federation as federation_routes
from routes import geo as geo_routes
from routes import operations as operations_routes
from routes import imports as imports_routes
from routes import messaging as messaging_routes
from routes import moderation as moderation_routes
from routes import persons as persons_routes
from routes import photos as photos_routes
from routes import push as push_routes
from routes import quality as quality_routes
from routes import reports as reports_routes
from routes import sms as sms_routes
from routes import stats as stats_routes
from routes import sync as sync_routes
from routes import uploads as uploads_routes
from routes import users as users_routes
from routes import webhooks as webhooks_routes

load_dotenv()

app = FastAPI(title="EGI Sync Server")

PORT = int(os.environ.get("PORT", "3000"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", "../frontend/dist")).resolve()

# Readiness flag: flipped True once startup finishes (DB init + bootstrap). The
# /ready probe reads this so orchestrators only route traffic to a warmed app.
_READY = False

# Security headers on every response (added first so it wraps outermost).
app.add_middleware(SecurityHeadersMiddleware)


@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    """Record per-request count + latency for Prometheus (plan-15 §4.3).

    Best-effort and privacy-safe: the recorded route is the template
    (``/persons/{id}``), never the concrete path, so no personal id leaks into a
    metric label. A metrics failure can never break the request.
    """
    start = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        try:
            metrics.observe_request(
                request.method,
                route_template(request),
                status,
                time.monotonic() - start,
            )
        except Exception:
            pass

# CORS is env-driven: locked to ALLOWED_ORIGINS in production, wildcard only in
# explicit dev mode (see security.py). Defaults closed so a forgotten ENV is safe.
app.add_middleware(CORSMiddleware, **cors_kwargs())

# NOTE: uploaded photos are NOT served from a public static mount anymore. They
# are high-risk crisis data, so they go through the operator-gated, ENABLE_PHOTOS
# guarded GET /uploads/{filename} route (routes/uploads.py).


@app.on_event("startup")
def startup():
    global _READY
    db.init_db()
    _bootstrap_admin()
    _READY = True


def _bootstrap_admin():
    """First-run migration helper (plan-08 §7).

    If a legacy ``OPERATOR_TOKENS`` is configured but no user accounts exist yet,
    seed one ``admin`` account with a random password and print a one-time setup
    message so the operator can log in and create real users. Best-effort: never
    blocks startup.
    """
    import secrets

    from auth import operator_auth_enabled
    from modules import users

    if not operator_auth_enabled():
        return
    try:
        if users.count_users() > 0:
            return
        email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "admin@egi.local")
        password = secrets.token_urlsafe(16)
        users.create_user(email, password, role="admin", name="Bootstrap Admin")
        print(
            "\n" + "=" * 64 +
            "\n[EGI plan-08] Bootstrapped an admin account from OPERATOR_TOKENS."
            f"\n  email:    {email}"
            f"\n  password: {password}"
            "\n  Log in at POST /auth/login, then create real users and remove"
            "\n  OPERATOR_TOKENS from your environment. This is shown ONCE.\n" +
            "=" * 64 + "\n"
        )
    except Exception as e:  # pragma: no cover - never block startup
        print(f"[EGI plan-08] admin bootstrap skipped: {e}")


@app.get("/health")
def health():
    """Structured health check (plan-15 §4.1).

    Probes the database and uploads dir. Returns 503 if a critical check fails so
    a load balancer pulls the instance instead of serving errors.
    """
    payload, ok = health_mod.health_report(UPLOAD_DIR, version=__version__)
    if not ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/ready")
def ready():
    """Readiness probe (plan-15 §4.2): 200 only after startup completed."""
    if _READY:
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "starting"})


@app.get("/metrics")
def prometheus_metrics():
    """Prometheus metrics in text exposition format (plan-15 §4.3).

    No personal data — only HTTP method/route/status and operational counts.
    """
    return PlainTextResponse(
        metrics.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# API routers. Included before the SPA catch-all so they take precedence.
app.include_router(auth_routes.router)
app.include_router(users_routes.router)
# Geo router MUST precede the persons router so the literal GET /persons/nearby
# isn't shadowed by GET /persons/{person_id} (cross-router match is by order).
app.include_router(geo_routes.router)
app.include_router(persons_routes.router)
app.include_router(photos_routes.router)
app.include_router(sync_routes.router)
app.include_router(imports_routes.router)
app.include_router(events_routes.router)
app.include_router(exchange_routes.router)
app.include_router(operations_routes.router)
app.include_router(stats_routes.router)
app.include_router(quality_routes.router)
app.include_router(reports_routes.router)
app.include_router(alerts_routes.router)
app.include_router(action_plans_routes.router)
app.include_router(moderation_routes.router)
app.include_router(duplicates_routes.router)
app.include_router(sms_routes.router)
app.include_router(bots_routes.router)
app.include_router(messaging_routes.router)
app.include_router(push_routes.router)
app.include_router(uploads_routes.router)
app.include_router(webhooks_routes.router)
app.include_router(federation_routes.router)


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
