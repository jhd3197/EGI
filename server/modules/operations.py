"""Operations: the `events` table promoted to an active operational case (plan-09).

An "operation" is a row in the existing `events` table enriched with the
operational columns added in db.py (commander, status, UTM, closure fields, …).
We deliberately reuse `events` instead of a parallel `searches` table (plan-09
§3). The legacy ``GET/POST /events`` endpoints keep working against the same
rows; this module just exposes the richer operational surface.

Operational ``status`` is one of open|paused|closed, validated here (the column
predates this plan and carries arbitrary PFIF values on old rows, so there is no
SQLite CHECK — see db.py).
"""

import uuid
from typing import Optional

from fastapi import HTTPException

import db
from models import now_iso, validate_operation_status

# Columns on `events` we treat as the operation surface, in a stable order.
_OPERATION_FIELDS = [
    "name", "region", "type", "tag", "date", "status", "commander_id",
    "is_practice", "started_at", "closed_at", "closed_reason", "utm_x", "utm_y",
    "municipality", "contact_person", "contact_phone",
]


def _row(conn, op_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM events WHERE id = ?", (op_id,)).fetchone()
    return db.row_to_dict(row) if row else None


def list_operations(
    status: Optional[str] = None,
    region: Optional[str] = None,
    is_practice: Optional[int] = None,
) -> dict:
    sql = "SELECT * FROM events WHERE 1=1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if region:
        sql += " AND region = ?"
        params.append(region)
    if is_practice is not None:
        sql += " AND is_practice = ?"
        params.append(int(is_practice))
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


def create_operation(data, actor: str = "system") -> dict:
    if not validate_operation_status(data.status):
        raise HTTPException(status_code=400, detail=f"invalid status: {data.status}")
    now = now_iso()
    op_id = f"egi-event-{uuid.uuid4().hex[:8]}"
    status = data.status or "open"
    started_at = data.started_at or now
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO events
            (id, name, region, type, tag, date, status, commander_id, is_practice,
             started_at, utm_x, utm_y, municipality, contact_person, contact_phone,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                op_id, data.name, data.region, data.type, data.tag, data.date,
                status, data.commander_id, int(data.is_practice or 0), started_at,
                data.utm_x, data.utm_y, data.municipality, data.contact_person,
                data.contact_phone, now, now,
            ),
        )
        conn.commit()
        op = _row(conn, op_id)
    _audit(actor, "operation_create", op_id, f"status={status}")
    return op


def get_operation(op_id: str) -> dict:
    with db.get_db() as conn:
        op = _row(conn, op_id)
        if not op:
            raise HTTPException(status_code=404, detail="Operation not found")
        # Stats: persons attached to this operation, broken down by status. Mesh
        # `disaster_id` is the operation/event id (persons.disaster_id).
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM persons "
            "WHERE disaster_id = ? AND merged_into IS NULL GROUP BY status",
            (op_id,),
        ).fetchall()
    by_status = {r["status"]: r["n"] for r in rows}
    op["stats"] = {"persons_by_status": by_status, "persons_total": sum(by_status.values())}
    return op


def update_operation(op_id: str, data, actor: str = "system") -> dict:
    if data.status is not None and not validate_operation_status(data.status):
        raise HTTPException(status_code=400, detail=f"invalid status: {data.status}")
    fields = data.model_dump(exclude_unset=True)
    sets, params = [], []
    for col in _OPERATION_FIELDS:
        if col in fields:
            val = fields[col]
            if col == "is_practice" and val is not None:
                val = int(val)
            sets.append(f"{col} = ?")
            params.append(val)
    with db.get_db() as conn:
        if not _row(conn, op_id):
            raise HTTPException(status_code=404, detail="Operation not found")
        if sets:
            sets.append("updated_at = ?")
            params.append(now_iso())
            params.append(op_id)
            conn.execute(f"UPDATE events SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
        op = _row(conn, op_id)
    _audit(actor, "operation_update", op_id)
    return op


def close_operation(op_id: str, reason: Optional[str], actor: str = "system") -> dict:
    now = now_iso()
    with db.get_db() as conn:
        if not _row(conn, op_id):
            raise HTTPException(status_code=404, detail="Operation not found")
        conn.execute(
            "UPDATE events SET status='closed', closed_at=?, closed_reason=?, updated_at=? "
            "WHERE id = ?",
            (now, reason, now, op_id),
        )
        conn.commit()
        op = _row(conn, op_id)
    _audit(actor, "operation_close", op_id, f"reason={reason or ''}")
    # Outbound webhooks (plan-12, best-effort, post-commit). Lazy import; emit()
    # never raises so a webhook failure can't break the close.
    from modules import webhooks

    webhooks.emit("operation.closed", {
        "id": op_id, "name": op.get("name") if op else None, "closed_reason": reason,
    })
    return op


def reopen_operation(op_id: str, actor: str = "system") -> dict:
    now = now_iso()
    with db.get_db() as conn:
        if not _row(conn, op_id):
            raise HTTPException(status_code=404, detail="Operation not found")
        conn.execute(
            "UPDATE events SET status='open', closed_at=NULL, closed_reason=NULL, updated_at=? "
            "WHERE id = ?",
            (now, op_id),
        )
        conn.commit()
        op = _row(conn, op_id)
    _audit(actor, "operation_reopen", op_id)
    return op


def _audit(actor: str, action: str, op_id: str, detail: str = "") -> None:
    from modules import audit

    audit.log_action(actor, action, "operation", op_id, detail=detail)
