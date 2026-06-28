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
    SarOperationCreate,
    SarOperationUpdate,
    SarTaskCreate,
    SarTaskUpdate,
    SectorClaim,
    SectorCreate,
    SectorStatusUpdate,
    VolunteerJoin,
    now_iso,
    normalize_ts,
    validate_sar_operation_status,
    validate_sector_status,
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
