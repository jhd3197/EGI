"""Search & Rescue operations workflow (plan-26).

Lightweight civilian SAR coordination layered OVER the registry — it does not
replace professional SAR systems. An *operation* links one or more missing
persons and/or a geographic zone; the zone is gridded into *sectors* that
volunteers claim and search; *tasks* are a per-sector checklist; *volunteers*
join and check in/out; *field reports* (Phase 4) flow back over the mesh.

Namespaced ``sar_*`` throughout so it never collides with the plan-09
``operations`` surface (the ``events`` table viewed as operational cases).

Conventions reused from the rest of the server:
  * Upserts are timestamp-guarded last-write-wins on ``id`` (same model as
    ``/sync``) so offline/mesh copies merge cleanly.
  * JSON columns (a sector ``bbox``) are TEXT, decoded here so clients see lists.
  * Mutating helpers audit-log via ``modules.audit`` (plan-26 Phase 6).
"""

import json
import math
import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
from models import (
    FieldReportCreate,
    FieldReportResolve,
    SarOperationCreate,
    SarOperationUpdate,
    SarSyncPayload,
    SarTaskCreate,
    SarTaskUpdate,
    SectorClaim,
    SectorCreate,
    SectorStatusUpdate,
    VolunteerJoin,
    now_iso,
    normalize_ts,
    validate_field_report_type,
    validate_sar_operation_status,
    validate_sector_status,
    validate_status,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _audit(actor: str, action: str, op_id: str, detail: str = "") -> None:
    from modules import audit

    audit.log_action(actor, action, "sar_operation", op_id, detail=detail)


# ── Sector auto-grid ──────────────────────────────────────────────────────────


def _auto_grid_sectors(
    lat: float, lon: float, radius_m: int, n: int
) -> List[dict]:
    """Split the bounding box of a circular zone into an n×n grid of sectors.

    Returns a list of ``{name, lat, lon, bbox}`` dicts (bbox =
    ``[minLon, minLat, maxLon, maxLat]``). A degree of latitude is ~111_320 m;
    longitude is scaled by ``cos(lat)``. Cells are labelled A1, A2, … by row
    letter + column number, the convention search coordinators already use.
    """
    n = max(1, min(int(n), 8))  # cap so a fat-fingered grid can't explode
    if not radius_m or radius_m <= 0:
        radius_m = 1000
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(0.1, math.cos(math.radians(lat))))
    min_lat, max_lat = lat - dlat, lat + dlat
    min_lon, max_lon = lon - dlon, lon + dlon
    step_lat = (max_lat - min_lat) / n
    step_lon = (max_lon - min_lon) / n
    sectors: List[dict] = []
    for row in range(n):
        for col in range(n):
            cell_min_lat = min_lat + row * step_lat
            cell_max_lat = cell_min_lat + step_lat
            cell_min_lon = min_lon + col * step_lon
            cell_max_lon = cell_min_lon + step_lon
            sectors.append({
                "name": f"{chr(ord('A') + row)}{col + 1}",
                "lat": cell_min_lat + step_lat / 2,
                "lon": cell_min_lon + step_lon / 2,
                "bbox": [cell_min_lon, cell_min_lat, cell_max_lon, cell_max_lat],
            })
    return sectors


# ── Row decoders ──────────────────────────────────────────────────────────────


def _row_to_op(row) -> dict:
    return db.row_to_dict(row)


def _row_to_sector(row) -> dict:
    d = db.row_to_dict(row)
    if d.get("bbox"):
        try:
            d["bbox"] = json.loads(d["bbox"])
        except (TypeError, ValueError):
            d["bbox"] = None
    return d


# ── Operations ────────────────────────────────────────────────────────────────


def create_operation(
    data: SarOperationCreate, actor: str = "system", user_id: Optional[str] = None
) -> dict:
    """Create an operation with optional linked persons + sectors.

    Sectors come from ``auto_grid`` (an N×N grid over the zone) OR the explicit
    ``sectors`` list. Timestamp-guarded LWW on ``id`` so a re-synced create can't
    duplicate an operation.
    """
    if not validate_sar_operation_status(data.status):
        raise HTTPException(status_code=400, detail=f"invalid status: {data.status}")
    now = now_iso()
    op_id = data.id or _new_id("sarop")
    created_at = normalize_ts(data.createdAt or now)
    updated_at = normalize_ts(data.updatedAt or now)
    status = data.status or "active"

    with db.get_db() as conn:
        existing = conn.execute(
            "SELECT updated_at FROM sar_operations WHERE id = ?", (op_id,)
        ).fetchone()
        if existing and existing["updated_at"] and updated_at < normalize_ts(existing["updated_at"]):
            return get_operation(op_id)  # stale re-sync: keep stored
        conn.execute(
            """
            INSERT INTO sar_operations
            (id, disaster_id, name, description, status, zone_lat, zone_lon,
             zone_radius_m, created_by, created_by_user_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              disaster_id=excluded.disaster_id, name=excluded.name,
              description=excluded.description, status=excluded.status,
              zone_lat=excluded.zone_lat, zone_lon=excluded.zone_lon,
              zone_radius_m=excluded.zone_radius_m, updated_at=excluded.updated_at
            """,
            (
                op_id, data.disaster_id, data.name, data.description, status,
                data.zone_lat, data.zone_lon, data.zone_radius_m, actor, user_id,
                created_at, updated_at,
            ),
        )
        # Linked missing persons (M2M, idempotent).
        for pid in (data.person_ids or []):
            if pid:
                conn.execute(
                    "INSERT OR IGNORE INTO sar_operation_persons (operation_id, person_id, created_at) "
                    "VALUES (?,?,?)",
                    (op_id, pid, now),
                )
        # Sectors: auto-grid over the zone, else the explicit list.
        sector_defs: List[dict] = []
        if data.auto_grid and data.auto_grid > 1 and data.zone_lat is not None and data.zone_lon is not None:
            sector_defs = _auto_grid_sectors(
                data.zone_lat, data.zone_lon, data.zone_radius_m or 1000, data.auto_grid
            )
        elif data.sectors:
            for s in data.sectors:
                sd = s.model_dump() if hasattr(s, "model_dump") else dict(s)
                sector_defs.append(sd)
        for i, sd in enumerate(sector_defs):
            _insert_sector(conn, op_id, sd, now, default_name=f"Sector {i + 1}")
        conn.commit()
    _audit(actor, "sar_operation_create", op_id, f"status={status}")
    return get_operation(op_id)


def _insert_sector(conn, op_id: str, sd: dict, now: str, default_name: str = "Sector") -> str:
    sid = sd.get("id") or _new_id("sec")
    bbox = sd.get("bbox")
    conn.execute(
        """
        INSERT INTO sar_sectors
        (id, operation_id, name, status, lat, lon, radius_m, bbox, notes,
         created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            sid, op_id, sd.get("name") or default_name, "unassigned",
            sd.get("lat"), sd.get("lon"), sd.get("radius_m"),
            json.dumps(bbox) if bbox is not None else None, sd.get("notes"),
            now, now,
        ),
    )
    return sid


def list_operations(
    disaster_id: Optional[str] = None, status: Optional[str] = None
) -> dict:
    sql = "SELECT * FROM sar_operations WHERE 1=1"
    params: list = []
    if disaster_id:
        sql += " AND disaster_id = ?"
        params.append(disaster_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY (status='active') DESC, created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        ops = []
        for r in rows:
            op = _row_to_op(r)
            # Cheap summary counters for the list view.
            op["sector_count"] = conn.execute(
                "SELECT COUNT(*) FROM sar_sectors WHERE operation_id = ?", (op["id"],)
            ).fetchone()[0]
            op["volunteer_count"] = conn.execute(
                "SELECT COUNT(*) FROM sar_volunteers WHERE operation_id = ? AND status != 'checked_out'",
                (op["id"],),
            ).fetchone()[0]
            op["person_count"] = conn.execute(
                "SELECT COUNT(*) FROM sar_operation_persons WHERE operation_id = ?", (op["id"],)
            ).fetchone()[0]
            ops.append(op)
        return {"records": ops}


def get_operation(op_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM sar_operations WHERE id = ?", (op_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Operation not found")
        op = _row_to_op(row)
        # Linked persons, joined with the registry name/status when known.
        persons = conn.execute(
            """
            SELECT op.person_id AS id, p.name, p.status, p.cedula
            FROM sar_operation_persons op
            LEFT JOIN persons p ON p.id = op.person_id
            WHERE op.operation_id = ?
            ORDER BY op.created_at ASC
            """,
            (op_id,),
        ).fetchall()
        sectors = conn.execute(
            "SELECT * FROM sar_sectors WHERE operation_id = ? ORDER BY name COLLATE NOCASE ASC",
            (op_id,),
        ).fetchall()
        tasks = conn.execute(
            "SELECT * FROM sar_tasks WHERE operation_id = ? ORDER BY created_at ASC", (op_id,)
        ).fetchall()
        volunteers = conn.execute(
            "SELECT * FROM sar_volunteers WHERE operation_id = ? AND status != 'checked_out' "
            "ORDER BY created_at ASC",
            (op_id,),
        ).fetchall()
        field_reports = conn.execute(
            "SELECT * FROM sar_field_reports WHERE operation_id = ? ORDER BY created_at DESC LIMIT 50",
            (op_id,),
        ).fetchall()
        # Sector status breakdown for the status board.
        sector_status: dict = {}
        for s in sectors:
            sector_status[s["status"]] = sector_status.get(s["status"], 0) + 1
    op["persons"] = [db.row_to_dict(p) for p in persons]
    op["sectors"] = [_row_to_sector(s) for s in sectors]
    op["tasks"] = [db.row_to_dict(t) for t in tasks]
    op["volunteers"] = [db.row_to_dict(v) for v in volunteers]
    op["field_reports"] = [db.row_to_dict(f) for f in field_reports]
    op["stats"] = {
        "sectors_total": len(sectors),
        "sectors_by_status": sector_status,
        "volunteers_active": len(volunteers),
        "persons_total": len(persons),
    }
    return op


def update_operation(op_id: str, data: SarOperationUpdate, actor: str = "system") -> dict:
    if data.status is not None and not validate_sar_operation_status(data.status):
        raise HTTPException(status_code=400, detail=f"invalid status: {data.status}")
    fields = data.model_dump(exclude_unset=True)
    cols = ["name", "description", "status", "zone_lat", "zone_lon", "zone_radius_m"]
    sets, params = [], []
    for col in cols:
        if col in fields:
            sets.append(f"{col} = ?")
            params.append(fields[col])
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM sar_operations WHERE id = ?", (op_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Operation not found")
        if sets:
            sets.append("updated_at = ?")
            params.append(now_iso())
            params.append(op_id)
            conn.execute(f"UPDATE sar_operations SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
    _audit(actor, "sar_operation_update", op_id)
    return get_operation(op_id)


def set_status(op_id: str, status: str, reason: Optional[str], actor: str = "system") -> dict:
    if not validate_sar_operation_status(status):
        raise HTTPException(status_code=400, detail=f"invalid status: {status}")
    now = now_iso()
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM sar_operations WHERE id = ?", (op_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Operation not found")
        if status == "closed":
            conn.execute(
                "UPDATE sar_operations SET status=?, closed_at=?, closed_reason=?, updated_at=? WHERE id=?",
                (status, now, reason, now, op_id),
            )
        else:
            conn.execute(
                "UPDATE sar_operations SET status=?, closed_at=NULL, closed_reason=NULL, updated_at=? WHERE id=?",
                (status, now, op_id),
            )
        conn.commit()
    _audit(actor, "sar_operation_status", op_id, f"status={status}")
    return get_operation(op_id)


# ── Volunteers (plan-26 Phase 2/3) ────────────────────────────────────────────


def join_operation(
    op_id: str, data: VolunteerJoin, actor: str = "anon",
    user_id: Optional[str] = None,
) -> dict:
    """Enroll a volunteer in an operation. Idempotent per (operation, identity):
    re-joining returns the existing volunteer row rather than duplicating it. The
    identity is the user id when present, otherwise the device id, otherwise a new
    anonymous row."""
    now = now_iso()
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM sar_operations WHERE id = ?", (op_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Operation not found")
        existing = None
        if user_id:
            existing = conn.execute(
                "SELECT * FROM sar_volunteers WHERE operation_id = ? AND user_id = ?",
                (op_id, user_id),
            ).fetchone()
        elif data.device_id:
            existing = conn.execute(
                "SELECT * FROM sar_volunteers WHERE operation_id = ? AND device_id = ?",
                (op_id, data.device_id),
            ).fetchone()
        if existing:
            # Re-joining clears a prior check-out and refreshes the alias/role.
            conn.execute(
                "UPDATE sar_volunteers SET status = CASE WHEN status='checked_out' THEN 'joined' ELSE status END, "
                "alias = COALESCE(?, alias), role = COALESCE(?, role), last_seen_at = ?, updated_at = ? WHERE id = ?",
                (data.alias, data.role, now, now, existing["id"]),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM sar_volunteers WHERE id = ?", (existing["id"],)).fetchone()
            return db.row_to_dict(row)
        vid = _new_id("vol")
        conn.execute(
            """
            INSERT INTO sar_volunteers
            (id, operation_id, alias, user_id, device_id, role, status, last_seen_at,
             created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (vid, op_id, data.alias, user_id, data.device_id,
             data.role or "field_volunteer", "joined", now, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sar_volunteers WHERE id = ?", (vid,)).fetchone()
    # Auto-subscribe a logged-in volunteer to the operation (plan-24 Phase 6).
    if user_id:
        try:
            from modules import subscriptions
            subscriptions.subscribe(user_id, op_id)
        except Exception:
            pass
    _audit(actor, "sar_operation_join", op_id, f"volunteer={vid} role={data.role or 'field_volunteer'}")
    return db.row_to_dict(row)


def change_volunteer_role(volunteer_id: str, role: str, actor: str = "anon") -> dict:
    """Switch a volunteer's role "hat" (plan-27.5 Phase 3) without leaving the
    operation. The role only changes what the app surfaces first; it never
    removes the volunteer from the operation or releases their sector."""
    now = now_iso()
    with db.get_db() as conn:
        vol = conn.execute("SELECT * FROM sar_volunteers WHERE id = ?", (volunteer_id,)).fetchone()
        if not vol:
            raise HTTPException(status_code=404, detail="Volunteer not found")
        conn.execute(
            "UPDATE sar_volunteers SET role=?, last_seen_at=?, updated_at=? WHERE id=?",
            (role, now, now, volunteer_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sar_volunteers WHERE id = ?", (volunteer_id,)).fetchone()
    _audit(actor, "sar_volunteer_role", vol["operation_id"], f"volunteer={volunteer_id} role={role}")
    return db.row_to_dict(row)


# ── Sectors (plan-26 Phase 3) ─────────────────────────────────────────────────


def _get_sector(conn, sector_id: str):
    return conn.execute("SELECT * FROM sar_sectors WHERE id = ?", (sector_id,)).fetchone()


def claim_sector(sector_id: str, data: SectorClaim, actor: str = "anon") -> dict:
    """Claim a sector for a volunteer. Conflict prevention: one active volunteer
    per sector — if the sector is already assigned to a *different* volunteer and
    not yet cleared, raise 409 so two volunteers can't claim it simultaneously."""
    now = now_iso()
    with db.get_db() as conn:
        sec = _get_sector(conn, sector_id)
        if not sec:
            raise HTTPException(status_code=404, detail="Sector not found")
        held = sec["assigned_volunteer_id"]
        if (
            held
            and held != data.volunteer_id
            and sec["status"] in ("assigned", "in_progress")
        ):
            raise HTTPException(
                status_code=409,
                detail="Sector already claimed by another volunteer",
            )
        conn.execute(
            "UPDATE sar_sectors SET status='assigned', assigned_to=?, assigned_user_id=?, "
            "assigned_volunteer_id=?, updated_at=? WHERE id=?",
            (data.alias, None, data.volunteer_id, now, sector_id),
        )
        conn.commit()
        row = _get_sector(conn, sector_id)
    _audit(actor, "sar_sector_claim", sec["operation_id"], f"sector={sector_id}")
    return _row_to_sector(row)


def release_sector(sector_id: str, actor: str = "anon") -> dict:
    """Release a sector back to ``unassigned`` (unless already cleared)."""
    now = now_iso()
    with db.get_db() as conn:
        sec = _get_sector(conn, sector_id)
        if not sec:
            raise HTTPException(status_code=404, detail="Sector not found")
        new_status = "unassigned" if sec["status"] in ("assigned", "in_progress") else sec["status"]
        conn.execute(
            "UPDATE sar_sectors SET status=?, assigned_to=NULL, assigned_user_id=NULL, "
            "assigned_volunteer_id=NULL, updated_at=? WHERE id=?",
            (new_status, now, sector_id),
        )
        conn.commit()
        row = _get_sector(conn, sector_id)
    _audit(actor, "sar_sector_release", sec["operation_id"], f"sector={sector_id}")
    return _row_to_sector(row)


def update_sector(sector_id: str, data: SectorStatusUpdate, actor: str = "anon") -> dict:
    """Update a sector's status and/or notes. Stamps ``cleared_at`` when moving to
    ``cleared``."""
    if data.status is not None and not validate_sector_status(data.status):
        raise HTTPException(status_code=400, detail=f"invalid sector status: {data.status}")
    now = now_iso()
    with db.get_db() as conn:
        sec = _get_sector(conn, sector_id)
        if not sec:
            raise HTTPException(status_code=404, detail="Sector not found")
        sets, params = [], []
        if data.status is not None:
            sets.append("status = ?")
            params.append(data.status)
            if data.status == "cleared":
                sets.append("cleared_at = ?")
                params.append(now)
        if data.notes is not None:
            sets.append("notes = ?")
            params.append(data.notes)
        if sets:
            sets.append("updated_at = ?")
            params.append(now)
            params.append(sector_id)
            conn.execute(f"UPDATE sar_sectors SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
        row = _get_sector(conn, sector_id)
    _audit(actor, "sar_sector_update", sec["operation_id"], f"sector={sector_id} status={data.status}")
    return _row_to_sector(row)


def checkin_sector(sector_id: str, volunteer_id: str, actor: str = "anon") -> dict:
    """Mark a volunteer as actively searching a sector. Moves the sector to
    ``in_progress`` and the volunteer to ``checked_in`` (one active volunteer per
    sector — a 409 if someone else holds it)."""
    now = now_iso()
    with db.get_db() as conn:
        sec = _get_sector(conn, sector_id)
        if not sec:
            raise HTTPException(status_code=404, detail="Sector not found")
        held = sec["assigned_volunteer_id"]
        if held and held != volunteer_id and sec["status"] in ("assigned", "in_progress"):
            raise HTTPException(status_code=409, detail="Sector held by another volunteer")
        if not conn.execute("SELECT 1 FROM sar_volunteers WHERE id = ?", (volunteer_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Volunteer not found")
        conn.execute(
            "UPDATE sar_sectors SET status='in_progress', assigned_volunteer_id=?, updated_at=? WHERE id=?",
            (volunteer_id, now, sector_id),
        )
        conn.execute(
            "UPDATE sar_volunteers SET status='checked_in', sector_id=?, checked_in_at=?, "
            "checked_out_at=NULL, last_seen_at=?, updated_at=? WHERE id=?",
            (sector_id, now, now, now, volunteer_id),
        )
        conn.commit()
        row = _get_sector(conn, sector_id)
    _audit(actor, "sar_sector_checkin", sec["operation_id"], f"sector={sector_id} volunteer={volunteer_id}")
    return _row_to_sector(row)


def checkout_sector(volunteer_id: str, actor: str = "anon") -> dict:
    """Check a volunteer out of whatever sector they were searching."""
    now = now_iso()
    with db.get_db() as conn:
        vol = conn.execute("SELECT * FROM sar_volunteers WHERE id = ?", (volunteer_id,)).fetchone()
        if not vol:
            raise HTTPException(status_code=404, detail="Volunteer not found")
        conn.execute(
            "UPDATE sar_volunteers SET status='checked_out', checked_out_at=?, last_seen_at=?, "
            "updated_at=? WHERE id=?",
            (now, now, now, volunteer_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sar_volunteers WHERE id = ?", (volunteer_id,)).fetchone()
    _audit(actor, "sar_sector_checkout", vol["operation_id"], f"volunteer={volunteer_id}")
    return db.row_to_dict(row)


def auto_checkout_stale(timeout_minutes: int = 180) -> int:
    """Auto check-out volunteers whose last check-in is older than the timeout.

    Returns the number checked out. Best-effort sweep (cron/CLI or opportunistic);
    privacy-friendly — we never track live GPS, just release a stale claim so a
    sector frees up. Compares ISO-8601 lexicographically against a cutoff.
    """
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)).isoformat()
    now = now_iso()
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT id FROM sar_volunteers WHERE status='checked_in' AND "
            "(checked_in_at IS NULL OR checked_in_at < ?)",
            (cutoff,),
        ).fetchall()
        for r in rows:
            conn.execute(
                "UPDATE sar_volunteers SET status='checked_out', checked_out_at=?, updated_at=? WHERE id=?",
                (now, now, r["id"]),
            )
        conn.commit()
        return len(rows)


# ── Tasks (plan-26 Phase 3) ───────────────────────────────────────────────────


def add_task(op_id: str, data: SarTaskCreate, actor: str = "anon") -> dict:
    now = now_iso()
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM sar_operations WHERE id = ?", (op_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Operation not found")
        if data.sector_id and not _get_sector(conn, data.sector_id):
            raise HTTPException(status_code=404, detail="Sector not found")
        tid = _new_id("sartask")
        conn.execute(
            """
            INSERT INTO sar_tasks
            (id, operation_id, sector_id, title, kind, done, notes, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (tid, op_id, data.sector_id, data.title, data.kind or "custom", 0, data.notes, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sar_tasks WHERE id = ?", (tid,)).fetchone()
    _audit(actor, "sar_task_create", op_id, f"task={tid}")
    return db.row_to_dict(row)


def update_task(task_id: str, data: SarTaskUpdate, actor: str = "anon") -> dict:
    now = now_iso()
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM sar_tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        sets, params = [], []
        if data.done is not None:
            sets.append("done = ?")
            params.append(1 if data.done else 0)
            if data.done:
                sets.append("completed_at = ?")
                params.append(now)
                sets.append("completed_by = ?")
                params.append(data.completed_by or actor)
            else:
                sets.append("completed_at = NULL")
                sets.append("completed_by = NULL")
        if data.title is not None:
            sets.append("title = ?")
            params.append(data.title)
        if data.notes is not None:
            sets.append("notes = ?")
            params.append(data.notes)
        if sets:
            sets.append("updated_at = ?")
            params.append(now)
            params.append(task_id)
            conn.execute(f"UPDATE sar_tasks SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
        row = conn.execute("SELECT * FROM sar_tasks WHERE id = ?", (task_id,)).fetchone()
    _audit(actor, "sar_task_update", row["operation_id"], f"task={task_id}")
    return db.row_to_dict(row)


def delete_task(task_id: str, actor: str = "anon") -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM sar_tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        conn.execute("DELETE FROM sar_tasks WHERE id = ?", (task_id,))
        conn.commit()
    _audit(actor, "sar_task_delete", row["operation_id"], f"task={task_id}")
    return {"deleted": True, "id": task_id}


# ── Field reports (plan-26 Phase 4) ───────────────────────────────────────────


def _row_to_field_report(row) -> dict:
    d = db.row_to_dict(row)
    # Decode the report-type-specific structured payload (plan-27.5: building
    # inspection checklist / facility-match verdict) so clients see an object.
    if d.get("checklist"):
        try:
            d["checklist"] = json.loads(d["checklist"])
        except (TypeError, ValueError):
            d["checklist"] = None
    return d


def _inspection_needs_recheck(checklist) -> bool:
    """True when a building-inspection checklist warrants a sector re-check:
    unsafe, occupants still present, access blocked, or follow-up requested."""
    if not isinstance(checklist, dict):
        return False
    if checklist.get("safety_level") == "unsafe":
        return True
    return bool(
        checklist.get("occupants_present")
        or checklist.get("access_blocked")
        or checklist.get("needs_followup")
    )


def _upsert_field_report(
    conn, data: FieldReportCreate, op_id: Optional[str], now: str,
    reporter_user_id: Optional[str] = None,
):
    """Insert or LWW-update a field report on the open connection. Returns
    ``(row_id, is_new)`` or ``(None, False)`` when skipped as stale."""
    if data.type is not None and not validate_field_report_type(data.type):
        raise HTTPException(status_code=400, detail=f"invalid field-report type: {data.type}")
    fr_id = data.id or _new_id("fr")
    created_at = normalize_ts(data.createdAt or now)
    updated_at = normalize_ts(data.updatedAt or now)
    existing = conn.execute(
        "SELECT updated_at FROM sar_field_reports WHERE id = ?", (fr_id,)
    ).fetchone()
    if existing and existing["updated_at"] and updated_at < normalize_ts(existing["updated_at"]):
        return None, False  # stale relay
    is_new = existing is None
    checklist_json = (
        json.dumps(data.checklist) if getattr(data, "checklist", None) is not None else None
    )
    conn.execute(
        """
        INSERT INTO sar_field_reports
        (id, operation_id, sector_id, person_id, type, note, lat, lon, photo_url,
         reporter_alias, reporter_user_id, origin_device, source, checklist,
         facility_id, reviewed, applied, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?,?)
        ON CONFLICT(id) DO UPDATE SET
          operation_id=excluded.operation_id, sector_id=excluded.sector_id,
          person_id=excluded.person_id, type=excluded.type, note=excluded.note,
          lat=excluded.lat, lon=excluded.lon, photo_url=excluded.photo_url,
          reporter_alias=excluded.reporter_alias, source=excluded.source,
          checklist=excluded.checklist, facility_id=excluded.facility_id,
          updated_at=excluded.updated_at
        """,
        (
            fr_id, op_id or data.operation_id, data.sector_id, data.person_id, data.type,
            data.note, data.lat, data.lon, data.photo_url, data.reporter_alias,
            reporter_user_id, data.origin_device, data.source or "web", checklist_json,
            getattr(data, "facility_id", None), created_at, updated_at,
        ),
    )
    return fr_id, is_new


def create_field_report(
    op_id: str, data: FieldReportCreate, actor: str = "anon",
    user_id: Optional[str] = None,
) -> dict:
    """File a field report against an operation (sighting/cleared/needs_help/found).

    Side-effects are applied conservatively:
      * ``cleared`` moves the linked sector to ``cleared`` (a search result).
      * ``found`` is recorded but does NOT auto-update the registry — it lands
        ``reviewed=0`` and a moderator/verified volunteer confirms it via
        ``resolve_field_report`` (plan-26 Phase 6) before the person record moves.
    """
    now = now_iso()
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM sar_operations WHERE id = ?", (op_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Operation not found")
        fr_id, _is_new = _upsert_field_report(conn, data, op_id, now, reporter_user_id=user_id)
        if fr_id is None:
            raise HTTPException(status_code=409, detail="Stale field report")
        # `cleared` is a search outcome on a sector — reflect it immediately.
        if data.type == "cleared" and data.sector_id:
            sec = _get_sector(conn, data.sector_id)
            if sec:
                conn.execute(
                    "UPDATE sar_sectors SET status='cleared', cleared_at=?, updated_at=? WHERE id=?",
                    (now, now, data.sector_id),
                )
        # `needs_recheck` lead: a sighting on a sector flags it for follow-up.
        if data.type == "sighting" and data.sector_id:
            conn.execute(
                "UPDATE sar_sectors SET status='needs_recheck', updated_at=? WHERE id=? AND status!='cleared'",
                (now, data.sector_id),
            )
        # A building inspection that finds the building unsafe, still occupied, or
        # needing follow-up flags its sector for re-check (plan-27.5 Phase 5).
        if data.type == "building_inspection" and data.sector_id and _inspection_needs_recheck(data.checklist):
            conn.execute(
                "UPDATE sar_sectors SET status='needs_recheck', updated_at=? WHERE id=? AND status!='cleared'",
                (now, data.sector_id),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM sar_field_reports WHERE id = ?", (fr_id,)).fetchone()
    _audit(actor, "sar_field_report", op_id, f"type={data.type} report={fr_id}")
    return _row_to_field_report(row)


def list_field_reports(op_id: str, only_pending: bool = False) -> dict:
    sql = "SELECT * FROM sar_field_reports WHERE operation_id = ?"
    params: list = [op_id]
    if only_pending:
        sql += " AND reviewed = 0 AND type IN ('found','needs_help')"
    sql += " ORDER BY created_at DESC LIMIT 200"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [_row_to_field_report(r) for r in rows]}


def resolve_field_report(
    fr_id: str, data: FieldReportResolve, actor: str = "system"
) -> dict:
    """Confirm or dismiss a field report (plan-26 Phase 6).

    When a ``found`` report is confirmed and links a person, the registry status
    is updated (default ``found``) — but only here, behind the operator/verified
    gate enforced by the route, never automatically at creation. A correction
    report+history row is written and a ``person.updated`` webhook emitted.
    """
    now = now_iso()
    with db.get_db() as conn:
        fr = conn.execute("SELECT * FROM sar_field_reports WHERE id = ?", (fr_id,)).fetchone()
        if not fr:
            raise HTTPException(status_code=404, detail="Field report not found")
        reviewed = 1 if data.confirmed else -1
        applied = 0
        person_update = None
        # A confirmed `found` OR a confirmed facility `person_is_here` match is a
        # registry update — both behind the operator/verified gate on the route.
        applies_to_registry = fr["type"] == "found"
        if fr["type"] == "facility_match" and fr["checklist"]:
            try:
                applies_to_registry = json.loads(fr["checklist"]).get("verdict") == "person_is_here"
            except (TypeError, ValueError):
                applies_to_registry = False
        if data.confirmed and applies_to_registry and fr["person_id"]:
            new_status = data.person_status or "found"
            if not validate_status(new_status):
                raise HTTPException(status_code=400, detail=f"invalid status: {new_status}")
            p = conn.execute(
                "SELECT id, status FROM persons WHERE id = ?", (fr["person_id"],)
            ).fetchone()
            if p:
                conn.execute(
                    "UPDATE persons SET status=?, updated_at=? WHERE id=?",
                    (new_status, now, fr["person_id"]),
                )
                applied = 1
                person_update = {"id": fr["person_id"], "status": new_status}
        conn.execute(
            "UPDATE sar_field_reports SET reviewed=?, confirmed_by=?, applied=?, updated_at=? WHERE id=?",
            (reviewed, actor if data.confirmed else None, applied, now, fr_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sar_field_reports WHERE id = ?", (fr_id,)).fetchone()
    _audit(
        actor, "sar_field_report_resolve", fr["operation_id"] or "",
        f"report={fr_id} confirmed={data.confirmed} applied={applied}",
    )
    # Registry side-effects (best-effort, post-commit), mirroring sync.py.
    if person_update:
        try:
            from modules import audit
            audit.log_history(
                person_update["id"], "update", actor=actor, source="sar_field_report",
                detail=f"status -> {person_update['status']} (found confirmed)",
            )
        except Exception:
            pass
        try:
            from modules import webhooks
            webhooks.emit("person.updated", {
                "id": person_update["id"], "status": person_update["status"],
                "source": "sar_field_report", "updatedAt": now,
            })
        except Exception:
            pass
    return _row_to_field_report(row)


# ── Facility watcher integration (plan-27.5 Phase 4) ──────────────────────────


def _facility_coords(conn, facility_id: str):
    row = conn.execute(
        "SELECT id, name, lat, lon FROM shelters WHERE id = ?", (facility_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Facility not found")
    return row


def operations_near_facility(facility_id: str, radius_m: float = 20000) -> dict:
    """Active operations whose zone centre is within ``radius_m`` of the facility.

    A facility watcher uses this to find SAR operations near their hospital/shelter
    to subscribe to. Operations with no zone are still returned (they may be
    person-centric) so the watcher can opt in. Already-watched operations are
    flagged ``watching=True``.
    """
    from modules.geo import haversine_m

    with db.get_db() as conn:
        fac = _facility_coords(conn, facility_id)
        ops = conn.execute(
            "SELECT * FROM sar_operations WHERE status = 'active' ORDER BY created_at DESC"
        ).fetchall()
        watched = {
            r["operation_id"]
            for r in conn.execute(
                "SELECT operation_id FROM sar_facility_watch WHERE facility_id = ?",
                (facility_id,),
            ).fetchall()
        }
    results = []
    for r in ops:
        op = _row_to_op(r)
        if fac["lat"] is not None and op.get("zone_lat") is not None and op.get("zone_lon") is not None:
            dist = haversine_m(fac["lat"], fac["lon"], op["zone_lat"], op["zone_lon"])
            if dist > radius_m:
                continue
            op["distance_m"] = round(dist)
        op["watching"] = op["id"] in watched
        results.append(op)
    return {"records": results, "count": len(results)}


def subscribe_facility(op_id: str, facility_id: str, actor: str = "system", user_id: Optional[str] = None) -> dict:
    """A facility watcher subscribes a facility to an operation (idempotent)."""
    now = now_iso()
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM sar_operations WHERE id = ?", (op_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Operation not found")
        _facility_coords(conn, facility_id)  # 404 if facility missing
        existing = conn.execute(
            "SELECT id FROM sar_facility_watch WHERE operation_id = ? AND facility_id = ?",
            (op_id, facility_id),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE sar_facility_watch SET user_id = COALESCE(?, user_id), updated_at = ? WHERE id = ?",
                (user_id, now, existing["id"]),
            )
            wid = existing["id"]
        else:
            wid = _new_id("fwatch")
            conn.execute(
                "INSERT INTO sar_facility_watch (id, operation_id, facility_id, user_id, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (wid, op_id, facility_id, user_id, now, now),
            )
        conn.commit()
    _audit(actor, "sar_facility_watch", op_id, f"facility={facility_id}")
    return {"id": wid, "operation_id": op_id, "facility_id": facility_id, "watching": True}


def list_facility_watch(facility_id: str) -> dict:
    """Operations a facility is currently watching."""
    with db.get_db() as conn:
        rows = conn.execute(
            """
            SELECT o.* FROM sar_facility_watch w
            JOIN sar_operations o ON o.id = w.operation_id
            WHERE w.facility_id = ?
            ORDER BY o.created_at DESC
            """,
            (facility_id,),
        ).fetchall()
    return {"records": [_row_to_op(r) for r in rows], "count": len(rows)}


def facility_match_candidates(op_id: str, facility_id: str) -> dict:
    """Missing persons linked to an operation, for a facility watcher to check.

    Each candidate carries any prior facility-match verdict this facility already
    filed (so the one-tap UI shows what's been answered). The full person record is
    deliberately NOT exposed here — only the fields a watcher needs to match a
    patient/guest (name, status, cédula, last-known location).
    """
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM sar_operations WHERE id = ?", (op_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Operation not found")
        rows = conn.execute(
            """
            SELECT op.person_id AS id, p.name, p.status, p.cedula, p.last_known_location
            FROM sar_operation_persons op
            LEFT JOIN persons p ON p.id = op.person_id
            WHERE op.operation_id = ?
            ORDER BY op.created_at ASC
            """,
            (op_id,),
        ).fetchall()
        prior = {}
        for fr in conn.execute(
            "SELECT person_id, checklist, reviewed FROM sar_field_reports "
            "WHERE operation_id = ? AND type = 'facility_match' AND facility_id = ? "
            "ORDER BY created_at DESC",
            (op_id, facility_id),
        ).fetchall():
            if fr["person_id"] and fr["person_id"] not in prior and fr["checklist"]:
                try:
                    prior[fr["person_id"]] = json.loads(fr["checklist"]).get("verdict")
                except (TypeError, ValueError):
                    pass
    candidates = []
    for r in rows:
        d = db.row_to_dict(r)
        d["facility_verdict"] = prior.get(d["id"])
        candidates.append(d)
    return {"records": candidates, "count": len(candidates)}


def create_facility_match(
    op_id: str, facility_id: str, person_id: str, verdict: str,
    note: Optional[str] = None, actor: str = "anon", user_id: Optional[str] = None,
) -> dict:
    """File a facility-match verdict as a ``facility_match`` field report.

    Lands ``reviewed=0`` (into the operation status board + moderation queue) like
    any untrusted lead. A ``person_is_here`` verdict is a strong lead a coordinator
    can confirm via ``resolve_field_report`` to update the person record.
    """
    from models import FieldReportCreate

    now = now_iso()
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM sar_operations WHERE id = ?", (op_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Operation not found")
        fac = _facility_coords(conn, facility_id)
        data = FieldReportCreate(
            operation_id=op_id, person_id=person_id, type="facility_match",
            note=note, facility_id=facility_id, checklist={"verdict": verdict},
            reporter_alias=fac["name"], source="facility_watch",
            lat=fac["lat"], lon=fac["lon"],
        )
        fr_id, _is_new = _upsert_field_report(conn, data, op_id, now, reporter_user_id=user_id)
        conn.commit()
        row = conn.execute("SELECT * FROM sar_field_reports WHERE id = ?", (fr_id,)).fetchone()
    _audit(actor, "sar_facility_match", op_id, f"facility={facility_id} person={person_id} verdict={verdict}")
    return _row_to_field_report(row)


# ── Mesh / cloud sync (plan-26 Phase 4) ───────────────────────────────────────


def sync_download(since: Optional[str] = None) -> dict:
    """Pull operations + sectors + field reports changed after ``since`` for
    offline field use. Operation/sector state is server/coordinator-managed;
    field reports are what flows back up (``sync_upload``)."""
    since = since or "1970-01-01T00:00:00Z"
    with db.get_db() as conn:
        ops = conn.execute(
            "SELECT * FROM sar_operations WHERE updated_at > ? ORDER BY updated_at ASC", (since,)
        ).fetchall()
        sectors = conn.execute(
            "SELECT * FROM sar_sectors WHERE updated_at > ? ORDER BY updated_at ASC", (since,)
        ).fetchall()
        reports = conn.execute(
            "SELECT * FROM sar_field_reports WHERE updated_at > ? ORDER BY updated_at ASC", (since,)
        ).fetchall()
        return {
            "operations": [_row_to_op(r) for r in ops],
            "sectors": [_row_to_sector(s) for s in sectors],
            "field_reports": [_row_to_field_report(f) for f in reports],
        }


def sync_upload(payload: SarSyncPayload) -> dict:
    """Apply field reports created offline (mesh/cloud) with timestamp-guarded
    LWW on id — a stale relay can't clobber a newer report. Side-effects
    (``cleared``/``sighting`` sector nudges) apply on first arrival only."""
    now = now_iso()
    saved = skipped = 0
    with db.get_db() as conn:
        for fr in payload.field_reports:
            op_id = fr.operation_id
            try:
                fr_id, is_new = _upsert_field_report(conn, fr, op_id, now)
            except HTTPException:
                skipped += 1
                continue
            if fr_id is None:
                skipped += 1
                continue
            if is_new and fr.type == "cleared" and fr.sector_id:
                conn.execute(
                    "UPDATE sar_sectors SET status='cleared', cleared_at=?, updated_at=? WHERE id=?",
                    (now, now, fr.sector_id),
                )
            if is_new and fr.type == "building_inspection" and fr.sector_id and _inspection_needs_recheck(fr.checklist):
                conn.execute(
                    "UPDATE sar_sectors SET status='needs_recheck', updated_at=? WHERE id=? AND status!='cleared'",
                    (now, fr.sector_id),
                )
            saved += 1
        conn.commit()
    return {"saved": saved, "skipped": skipped}
