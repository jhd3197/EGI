"""EGI Sync Server — FastAPI app wiring only.

Business logic lives in ``modules/`` and the HTTP layer in ``routes/``. This file
just builds the app, configures middleware/uploads, includes the routers, and
serves the SPA via a catch-all that MUST stay last so API routes win.

``ocr_image`` / ``extract_with_llm`` are re-exported here (and ``UPLOAD_DIR`` is
defined here) because the OCR import route reads them off this module at request
time — this is the surface the test suite monkeypatches.
"""

import logging
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from dotenv import load_dotenv

import db
from logging_config import configure_logging, request_id_var
from metrics import metrics, route_template
from modules import health as health_mod
from ocr import ocr_image, extract_with_llm  # noqa: F401  (re-exported as test hooks)
from security import SecurityHeadersMiddleware, cors_kwargs
from version import __version__
from routes import action_plans as action_plans_routes
from routes import audit as audit_routes
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
from routes import locations as locations_routes
from routes import messaging as messaging_routes
from routes import moderation as moderation_routes
from routes import moderators as moderators_routes
from routes import organizations as organizations_routes
from routes import persons as persons_routes
from routes import photos as photos_routes
from routes import preferences as preferences_routes
from routes import provenance as provenance_routes
from routes import push as push_routes
from routes import quality as quality_routes
from routes import reports as reports_routes
from routes import corridors as corridors_routes
from routes import hazards as hazards_routes
from routes import routing as routing_routes
from routes import route_shares as route_shares_routes
from routes import sar as sar_routes
from routes import shelters as shelters_routes
from routes import sms as sms_routes
from routes import stats as stats_routes
from routes import sync as sync_routes
from routes import system as system_routes
from routes import trust as trust_routes
from routes import uploads as uploads_routes
from routes import users as users_routes
from routes import webhooks as webhooks_routes

load_dotenv()
configure_logging()

_access_logger = logging.getLogger("egi.access")

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
async def _access_log_middleware(request: Request, call_next):
    """Request-scoped tracing + structured access log (plan-15 §5).

    Generates (or echoes) an ``X-Request-ID``, binds it to a contextvar so every
    log line in this request carries it, logs one structured line per request,
    and returns the id in the response header. Never logs tokens/passwords.
    """
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_var.set(rid)
    start = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        try:
            level = logging.INFO
            if status >= 500:
                level = logging.ERROR
            elif status == 429 or status >= 400:
                level = logging.WARNING
            _access_logger.log(
                level,
                "%s %s -> %s",
                request.method,
                request.url.path,
                status,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": duration_ms,
                    "client_ip": _client_ip(request),
                    "user_id": _user_id_best_effort(request),
                },
            )
        except Exception:
            pass
        request_id_var.reset(token)


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
    try:
        from modules import system_events

        system_events.record("startup", f"EGI server {__version__} started", level="info")
    except Exception:
        pass


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


def _client_ip(request: Request) -> str:
    """Best-effort client IP. Honors X-Forwarded-For only behind a trusted proxy."""
    if os.environ.get("RATE_LIMIT_TRUST_FORWARDED", "").strip().lower() in (
        "1", "true", "yes",
    ):
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _user_id_best_effort(request: Request):
    """Resolve the caller's user id for the access log, or None. Never raises.

    Only attempts a lookup when an Authorization header is present, so anonymous
    traffic costs nothing. Tokens are never logged — only the resolved id.
    """
    if "authorization" not in request.headers:
        return None
    try:
        from auth import current_user

        user = current_user(request.headers.get("authorization"))
        return user["id"] if user else None
    except Exception:
        return None


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
app.include_router(audit_routes.router)
app.include_router(system_routes.router)
# Geo router MUST precede the persons router so the literal GET /persons/nearby
# isn't shadowed by GET /persons/{person_id} (cross-router match is by order).
app.include_router(geo_routes.router)
app.include_router(persons_routes.router)
app.include_router(photos_routes.router)
app.include_router(sync_routes.router)
app.include_router(imports_routes.router)
app.include_router(provenance_routes.router)
app.include_router(events_routes.router)
app.include_router(exchange_routes.router)
app.include_router(operations_routes.router)
app.include_router(stats_routes.router)
app.include_router(quality_routes.router)
app.include_router(reports_routes.router)
app.include_router(routing_routes.router)
app.include_router(route_shares_routes.router)
app.include_router(hazards_routes.router)
app.include_router(corridors_routes.router)
app.include_router(shelters_routes.router)
app.include_router(sar_routes.router)
app.include_router(alerts_routes.router)
app.include_router(action_plans_routes.router)
app.include_router(moderation_routes.router)
app.include_router(moderation_routes.flags_router)
app.include_router(moderators_routes.router)
app.include_router(trust_routes.router)
app.include_router(organizations_routes.router)
app.include_router(organizations_routes.redeem_router)
app.include_router(locations_routes.router)
app.include_router(duplicates_routes.router)
app.include_router(sms_routes.router)
app.include_router(bots_routes.router)
app.include_router(messaging_routes.router)
app.include_router(push_routes.router)
app.include_router(preferences_routes.router)
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
