"""Lightweight in-memory rate limiting for write endpoints.

The plan (plan-07 §5) allows ``slowapi`` *or* a small in-memory middleware. We
choose the latter to avoid a new dependency on a community server that may run
on a Raspberry Pi: a single-process fixed-window counter keyed by client IP.

Used as a FastAPI dependency on the handful of write routes that an abusive
script could flood (``/sync``, ``/import/paper``, ``/normalize``,
``/sms/webhook``, ``/persons/{id}/reports``). Normal human traffic stays well
under the limit; a burst of automated POSTs gets ``429 Too Many Requests`` with
a ``Retry-After`` header.

Caveats (documented, not hidden): the counters live in process memory, so the
limit is per-worker and resets on restart. For multi-worker or multi-host
deployments an operator should put the real limit at the reverse proxy; this is
a safe floor, not a replacement for that.
"""

import os
import threading
import time
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


class RateLimiter:
    """Fixed-window per-IP counter. Thread-safe for uvicorn's worker threads."""

    def __init__(self, max_requests: Optional[int] = None, window_seconds: Optional[int] = None):
        # Read config lazily from the env at construction; ``configure()`` lets
        # tests override without touching the environment.
        self.max_requests = (
            max_requests if max_requests is not None else _env_int("RATE_LIMIT_MAX", 30)
        )
        self.window_seconds = (
            window_seconds if window_seconds is not None
            else _env_int("RATE_LIMIT_WINDOW", 300)
        )
        self.trusted_ips = _parse_trusted(os.environ.get("RATE_LIMIT_TRUSTED_IPS", ""))
        self.trust_forwarded = os.environ.get(
            "RATE_LIMIT_TRUST_FORWARDED", ""
        ).strip().lower() in ("1", "true", "yes")
        # ip -> (window_start_monotonic, count)
        self._hits: Dict[str, Tuple[float, int]] = {}
        self._lock = threading.Lock()

    def configure(self, max_requests: int, window_seconds: int) -> None:
        """Reset limits and clear counters (used by the test suite)."""
        with self._lock:
            self.max_requests = max_requests
            self.window_seconds = window_seconds
            self._hits.clear()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    @property
    def enabled(self) -> bool:
        # max <= 0 disables limiting entirely (an explicit operator opt-out).
        return self.max_requests > 0

    def client_ip(self, request: Request) -> str:
        if self.trust_forwarded:
            fwd = request.headers.get("x-forwarded-for")
            if fwd:
                return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> None:
        """Raise 429 if the caller is over the limit; otherwise record the hit."""
        if not self.enabled:
            return
        ip = self.client_ip(request)
        if ip in self.trusted_ips:
            return
        now = time.monotonic()
        with self._lock:
            window_start, count = self._hits.get(ip, (now, 0))
            if now - window_start >= self.window_seconds:
                # Window elapsed -> start a fresh one.
                window_start, count = now, 0
            count += 1
            self._hits[ip] = (window_start, count)
            if count > self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - window_start)))
                raise HTTPException(
                    status_code=429,
                    detail="Too Many Requests",
                    headers={"Retry-After": str(retry_after)},
                )


def _parse_trusted(raw: str) -> set:
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


# Module-level singleton shared by every rate-limited route.
limiter = RateLimiter()


def rate_limit(request: Request) -> None:
    """FastAPI dependency: enforce the shared limiter on this request."""
    limiter.check(request)
