"""Security configuration: CORS origins and response security headers.

Kept as a small top-level module (like ``ai.py`` / ``ocr.py``) so ``main.py``
stays wiring-only. Everything here is driven by ``.env`` so a community operator
can lock the server down without touching code.

Defense in depth (plan-07 §3): a single misconfiguration should not expose all
crisis data, so CORS defaults to *closed* in production and the wildcard is
only honored in explicit development mode.
"""

import os
from typing import List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def photos_enabled() -> bool:
    """Whether uploaded photos are served/exposed at all (plan-07 §7).

    Defaults to **false**: photos of people in crisis are high-risk, so a fresh
    deployment never exposes them. When enabled, photos are still served only
    through the operator-gated ``GET /uploads/{filename}`` route, never publicly.
    """
    return os.environ.get("ENABLE_PHOTOS", "false").strip().lower() in (
        "1", "true", "yes",
    )


def is_dev() -> bool:
    """True only in explicit development mode (``ENV=development``).

    Anything else — including unset — is treated as production, so a forgotten
    ``ENV`` fails safe (closed CORS) rather than open.
    """
    return os.environ.get("ENV", "production").strip().lower() == "development"


def get_allowed_origins() -> List[str]:
    """Parse ``ALLOWED_ORIGINS`` (comma-separated) into a list.

    Precedence:
      1. ``ALLOWED_ORIGINS`` set -> use exactly those origins (the prod path).
      2. Unset + dev mode        -> ``["*"]`` (convenience for local work).
      3. Unset + prod            -> ``[]`` (closed; cross-origin calls rejected).

    The PWA is served same-origin by FastAPI, so a locked-down deployment needs
    no origins at all — ``ALLOWED_ORIGINS`` is only for separately-hosted clients.
    """
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        return origins
    if is_dev():
        return ["*"]
    return []


def cors_kwargs() -> dict:
    """Keyword args for ``CORSMiddleware`` derived from the environment."""
    return {
        "allow_origins": get_allowed_origins(),
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


# Static security headers applied to every response. Values follow OWASP
# secure-headers guidance; the Permissions-Policy disables browser features the
# PWA never uses (camera is requested by the native app, not the web client).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers (and optional CSP) to every response.

    The Content-Security-Policy is opt-in via ``CONTENT_SECURITY_POLICY`` because
    the PWA relies on inline styles carried over from its prototype; a too-strict
    default policy would break it. Operators who want a CSP set the full header
    value in ``.env`` (a recommended value ships in ``.env.example``).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        csp = os.environ.get("CONTENT_SECURITY_POLICY", "").strip()
        if csp:
            response.headers.setdefault("Content-Security-Policy", csp)
        return response
