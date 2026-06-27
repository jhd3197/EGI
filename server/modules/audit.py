"""Audit logging: attributable operator actions + append-only record history.

Two append-only trails (plan-07 §8):

  * ``audit_log``      — operator actions (approve/reject/merge/review) and auth
                         events (success/failure). The ``actor`` is a short,
                         non-secret token principal (``op:abc123…``) — never a
                         full token or password.
  * ``record_history`` — per-person change trail (create/update/merge) so a
                         record's evolution is reconstructable.

Both writers are best-effort: they swallow errors and never raise, so a logging
failure can never break the state-changing operation it is recording. This
mirrors ``modules/sync.log_sync``.
"""

from typing import List, Optional

import db
from models import now_iso


def log_action(
    actor: str,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    detail: str = "",
) -> None:
    """Record an operator action / auth event. Best-effort; never raises."""
    try:
        with db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                (actor, action, target_type, target_id, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (actor, action, target_type, target_id, detail, now_iso()),
            )
            conn.commit()
    except Exception:
        pass


def log_history(
    person_id: str,
    change: str,
    actor: str = "system",
    source: Optional[str] = None,
    detail: str = "",
) -> None:
    """Append a change to a person's history. Best-effort; never raises."""
    try:
        with db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO record_history
                (person_id, actor, change, source, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (person_id, actor, change, source, detail, now_iso()),
            )
            conn.commit()
    except Exception:
        pass


def list_actions(limit: int = 100) -> List[dict]:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [db.row_to_dict(r) for r in rows]


def list_history(person_id: str, limit: int = 100) -> List[dict]:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM record_history WHERE person_id = ? ORDER BY id DESC LIMIT ?",
            (person_id, limit),
        ).fetchall()
        return [db.row_to_dict(r) for r in rows]


def query_log(
    source: str = "all",
    actor: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    person_id: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Consolidated, filterable view over ``audit_log`` + ``record_history``.

    ``source`` selects which trail(s): ``actions`` (audit_log), ``history``
    (record_history), or ``all`` (both, merged and sorted by ``created_at`` desc).
    Each returned entry carries a ``kind`` ('action'|'history') so a single
    endpoint can present both. Read-only; never mutates.
    """
    limit = max(1, min(int(limit or 200), 1000))
    offset = max(0, int(offset or 0))
    entries: List[dict] = []

    with db.get_db() as conn:
        if source in ("all", "actions"):
            where, params = [], []
            if actor:
                where.append("actor = ?")
                params.append(actor)
            if action:
                where.append("action = ?")
                params.append(action)
            if target_type:
                where.append("target_type = ?")
                params.append(target_type)
            if person_id:
                where.append("target_id = ?")
                params.append(person_id)
            if since:
                where.append("created_at > ?")
                params.append(since)
            clause = (" WHERE " + " AND ".join(where)) if where else ""
            rows = conn.execute(
                f"SELECT * FROM audit_log{clause} ORDER BY created_at DESC LIMIT ?",
                (*params, limit + offset),
            ).fetchall()
            for r in rows:
                d = db.row_to_dict(r)
                d["kind"] = "action"
                entries.append(d)

        if source in ("all", "history"):
            where, params = [], []
            if actor:
                where.append("actor = ?")
                params.append(actor)
            if action:
                where.append("change = ?")
                params.append(action)
            if person_id:
                where.append("person_id = ?")
                params.append(person_id)
            if since:
                where.append("created_at > ?")
                params.append(since)
            clause = (" WHERE " + " AND ".join(where)) if where else ""
            rows = conn.execute(
                f"SELECT * FROM record_history{clause} ORDER BY created_at DESC LIMIT ?",
                (*params, limit + offset),
            ).fetchall()
            for r in rows:
                d = db.row_to_dict(r)
                d["kind"] = "history"
                entries.append(d)

    entries.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    window = entries[offset:offset + limit]
    return {"entries": window, "count": len(window), "source": source}
