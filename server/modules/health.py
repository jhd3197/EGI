"""Structured health & readiness checks (plan-15 §4).

``GET /health`` answers "is the running process able to serve requests right
now?" by probing the things that actually break a deployment: the SQLite
database (connectivity + WAL mode) and the uploads directory (writable + has
free space). ``GET /ready`` answers the narrower "has startup finished?" used by
systemd/Caddy/Docker readiness probes.

Every check is best-effort and self-contained — a probe never raises; it returns
a ``pass``/``fail`` dict so the aggregate ``/health`` can degrade meaningfully
(HTTP 503 when any *critical* check fails) instead of 500-ing. No personal data
is ever read or returned here (plan-15 §14).
"""

import os
import shutil
import time
from pathlib import Path
from typing import Optional

import db

# A health check fails "low disk" below this many free bytes (default 100 MB).
# Operators can tune it for a small VPS via MIN_FREE_BYTES.
_DEFAULT_MIN_FREE_BYTES = 100 * 1024 * 1024


def _min_free_bytes() -> int:
    try:
        return int(os.environ.get("MIN_FREE_BYTES", "").strip() or _DEFAULT_MIN_FREE_BYTES)
    except ValueError:
        return _DEFAULT_MIN_FREE_BYTES


def check_database() -> dict:
    """Probe DB connectivity and confirm WAL journal mode is active."""
    start = time.monotonic()
    try:
        with db.get_db() as conn:
            conn.execute("SELECT 1").fetchone()
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        response_ms = round((time.monotonic() - start) * 1000, 1)
        result = {"status": "pass", "response_ms": response_ms, "journal_mode": mode}
        if str(mode).lower() != "wal":
            # Not fatal (the DB still answers), but worth flagging to operators.
            result["status"] = "warn"
        return result
    except Exception as exc:  # pragma: no cover - exercised via monkeypatch in tests
        return {"status": "fail", "error": str(exc)}


def check_uploads_dir(upload_dir: Path) -> dict:
    """Confirm the uploads directory exists, is writable, and has free space."""
    upload_dir = Path(upload_dir)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        probe = upload_dir / ".health_write_probe"
        probe.write_bytes(b"ok")
        probe.unlink()
        free = shutil.disk_usage(upload_dir).free
        result = {"status": "pass", "free_bytes": free}
        if free < _min_free_bytes():
            result["status"] = "warn"
        return result
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def check_sync_queue() -> dict:
    """Report the server-side moderation backlog (the closest thing to a queue).

    EGI has no internal outbound sync queue (clients own their queues), so this
    surfaces the untrusted-source moderation backlog — a 0 here means nothing is
    waiting on an operator. Best-effort; never fatal.
    """
    try:
        from modules.moderation import UNTRUSTED_SOURCES

        placeholders = ",".join("?" * len(UNTRUSTED_SOURCES))
        with db.get_db() as conn:
            pending = conn.execute(
                f"SELECT COUNT(*) AS n FROM persons "
                f"WHERE reviewed = 0 AND source IN ({placeholders})",
                tuple(UNTRUSTED_SOURCES),
            ).fetchone()["n"]
        return {"status": "pass", "pending": pending}
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


# Which checks make the whole service unhealthy (-> HTTP 503) when they fail.
# A full uploads disk or a slow moderation count should NOT take the API down,
# so only the database is treated as critical.
_CRITICAL = {"database"}


def health_report(upload_dir: Path, version: Optional[str] = None) -> dict:
    """Aggregate all checks into the structured /health payload + an ok flag.

    Returns ``(payload, ok)``: ``ok`` is False when any critical check failed, so
    the route can map it to HTTP 503.
    """
    if version is None:
        try:
            from version import __version__ as version
        except Exception:  # pragma: no cover
            version = "unknown"

    checks = {
        "database": check_database(),
        "uploads_dir": check_uploads_dir(upload_dir),
        "sync_queue": check_sync_queue(),
    }
    ok = all(
        checks[name]["status"] != "fail" for name in _CRITICAL if name in checks
    )
    payload = {
        "status": "healthy" if ok else "unhealthy",
        "version": version,
        "checks": checks,
    }
    return payload, ok
