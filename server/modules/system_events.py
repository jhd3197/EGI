"""Operator-facing system events (plan-15 §11).

Distinct from ``audit_log`` (which records *who did what*): this records *what the
system did to itself* — startup, migrations applied, backup success/failure,
degraded health. An operator scanning ``GET /system/events`` should see the
server's own operational story without wading through per-record change history.

Writers are best-effort and never raise, mirroring ``modules.audit`` — recording
a system event must never break the operation that triggered it. Server-local;
never synced over the mesh.
"""

import json
import uuid
from typing import List, Optional

import db
from models import now_iso

VALID_LEVELS = ("info", "warning", "error")


def record(
    event_type: str,
    message: str,
    level: str = "info",
    details: Optional[dict] = None,
) -> None:
    """Append a system event. Best-effort; never raises."""
    if level not in VALID_LEVELS:
        level = "info"
    try:
        with db.get_db() as conn:
            conn.execute(
                "INSERT INTO system_events (id, level, event_type, message, details, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    level,
                    event_type,
                    message,
                    json.dumps(details, ensure_ascii=False) if details else None,
                    now_iso(),
                ),
            )
            conn.commit()
    except Exception:
        pass


def list_events(
    level: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Filterable, paginated read of recent system events (newest first)."""
    limit = max(1, min(int(limit or 200), 1000))
    offset = max(0, int(offset or 0))
    where, params = [], []
    if level:
        where.append("level = ?")
        params.append(level)
    if event_type:
        where.append("event_type = ?")
        params.append(event_type)
    if since:
        where.append("created_at > ?")
        params.append(since)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    with db.get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM system_events{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    entries: List[dict] = [db.row_to_dict(r) for r in rows]
    return {"entries": entries, "count": len(entries)}
