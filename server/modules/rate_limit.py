"""Per-device / per-user rate limiting (plan-25 Phase 5).

The IP-based ``ratelimit.RateLimiter`` is the front-door flood guard. This adds a
second, *identity*-based layer the plan asks for: cap how much a single device
fingerprint or user can do per window — reports per hour, shelter updates per
hour, mesh connections per minute — so a banned-but-rotating-IP device, or one
abusive account, can't keep injecting data.

Same design as ratelimit.py: a tiny in-memory fixed-window counter, no new
dependency, per-process (a safe floor, not a substitute for an edge limit). Keys
are ``"<scope>:<identity>"`` so the scopes don't share a budget. ``allow()``
returns a bool (best-effort, never raises) so callers can skip-and-count rather
than hard-fail a whole sync batch.
"""

import os
import threading
import time
from typing import Dict, Tuple


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


# Per-scope (limit, window_seconds). Generous defaults: a real reporter or shelter
# operator stays well under; an automated flood trips it. 0 disables a scope.
_SCOPES = {
    "report": ("DEVICE_REPORTS_PER_HOUR", 120, 3600),
    "shelter_update": ("DEVICE_SHELTER_UPDATES_PER_HOUR", 60, 3600),
    "mesh_conn": ("DEVICE_MESH_CONN_PER_MIN", 30, 60),
    "flag": ("DEVICE_FLAGS_PER_HOUR", 60, 3600),
}


class IdentityRateLimiter:
    def __init__(self):
        # key -> (window_start_monotonic, count)
        self._hits: Dict[str, Tuple[float, int]] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _limit_window(self, scope: str) -> Tuple[int, int]:
        env, default, window = _SCOPES.get(scope, (None, 0, 60))
        limit = _env_int(env, default) if env else default
        return limit, window

    def allow(self, scope: str, identity: str) -> bool:
        """True if ``identity`` may perform one more ``scope`` action now.

        Records the hit when allowed. A missing identity or a disabled scope
        (limit <= 0) always allows. Never raises.
        """
        try:
            if not identity:
                return True
            limit, window = self._limit_window(scope)
            if limit <= 0:
                return True
            key = f"{scope}:{identity}"
            now = time.monotonic()
            with self._lock:
                start, count = self._hits.get(key, (now, 0))
                if now - start >= window:
                    start, count = now, 0
                if count >= limit:
                    self._hits[key] = (start, count)
                    return False
                self._hits[key] = (start, count + 1)
                return True
        except Exception:
            return True

    def remaining(self, scope: str, identity: str) -> int:
        limit, window = self._limit_window(scope)
        if limit <= 0 or not identity:
            return limit
        key = f"{scope}:{identity}"
        now = time.monotonic()
        with self._lock:
            start, count = self._hits.get(key, (now, 0))
            if now - start >= window:
                return limit
            return max(0, limit - count)


# Module-level singleton shared across the app.
identity_limiter = IdentityRateLimiter()
