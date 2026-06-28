"""Hazard-zone data model + logic (plan-21 Phase 4).

A hazard zone is a flagged danger area (flood / landslide / fire / blocked road /
unsafe zone) with a polygon or circle geometry. The map renders them and the
offline router can route around them. Community submissions land as untrusted
``hazard_report`` rows (reviewed=0) and await moderation; operator/official
submissions land trusted (reviewed=1). reviewed=-1 is a soft-delete (rejected).

``geometry`` and ``bbox`` are stored as JSON TEXT and decoded here so the HTTP
layer and clients always see real dicts/lists. ``bbox`` is computed server-side
(never trusted from the client) for cheap overlap filtering, mirroring the
routing-pack bbox convention: ``[minLon, minLat, maxLon, maxLat]``.
"""

import json
import math
import uuid
from typing import List, Optional

import db
from models import HazardRecord, now_iso

# Approximate metres per degree of latitude. Longitude degrees are scaled by
# cos(lat). Good enough for a danger-zone bbox (we only need a coarse envelope).
_M_PER_DEG_LAT = 111320.0


def _new_id() -> str:
    return f"haz-{uuid.uuid4().hex[:10]}"


def _compute_bbox(geometry: Optional[dict]) -> Optional[list]:
    """Return ``[minLon, minLat, maxLon, maxLat]`` for a polygon or circle.

    Coordinates in the geometry are ``[lat, lon]`` (the wire contract); the bbox
    is emitted lon-first like the routing-pack bbox. Returns None for malformed
    geometry so an unparseable shape never crashes an upsert."""
    if not isinstance(geometry, dict):
        return None
    kind = geometry.get("kind")
    try:
        if kind == "polygon":
            coords = geometry.get("coords") or []
            lats = [float(c[0]) for c in coords]
            lons = [float(c[1]) for c in coords]
            if not lats or not lons:
                return None
            return [min(lons), min(lats), max(lons), max(lats)]
        if kind == "circle":
            center = geometry.get("center") or []
            lat = float(center[0])
            lon = float(center[1])
            radius_m = float(geometry.get("radius_m") or 0)
            d_lat = radius_m / _M_PER_DEG_LAT
            cos_lat = math.cos(math.radians(lat))
            d_lon = radius_m / (_M_PER_DEG_LAT * cos_lat) if abs(cos_lat) > 1e-9 else d_lat
            return [lon - d_lon, lat - d_lat, lon + d_lon, lat + d_lat]
    except (TypeError, ValueError, IndexError):
        return None
    return None


def _row_to_hazard(row) -> dict:
    d = db.row_to_dict(row)
    for col in ("geometry", "bbox"):
        raw = d.get(col)
        if raw:
            try:
                d[col] = json.loads(raw)
            except (TypeError, ValueError):
                d[col] = None
    return d


def _bbox_overlaps(stored: Optional[list], query: list) -> bool:
    """Axis-aligned overlap test between two ``[minLon,minLat,maxLon,maxLat]``."""
    if not stored or len(stored) != 4:
        # No stored bbox (malformed geometry) → don't exclude it from results.
        return True
    s_min_lon, s_min_lat, s_max_lon, s_max_lat = stored
    q_min_lon, q_min_lat, q_max_lon, q_max_lat = query
    return not (
        q_max_lon < s_min_lon
        or q_min_lon > s_max_lon
        or q_max_lat < s_min_lat
        or q_min_lat > s_max_lat
    )


def list_hazards(
    disaster_id: Optional[str] = None,
    bbox: Optional[list] = None,
    *,
    include_pending: bool = False,
) -> dict:
    """Active, non-rejected hazards for the map/router.

    "Active" = ``active_until`` is null or lexically greater than now (ISO-8601
    UTC compares as text, same as /sync). Rejected rows (reviewed=-1) are always
    hidden. Pending crowd reports (reviewed=0) are INCLUDED so the map can show
    them flagged — routing avoidance is the client's choice. ``include_pending``
    is accepted for API symmetry; the active set already keeps pending rows.
    """
    sql = "SELECT * FROM hazard_zones WHERE reviewed != -1"
    params: list = []
    if disaster_id:
        sql += " AND disaster_id = ?"
        params.append(disaster_id)
    # Active window: drop expired hazards (active_until in the past).
    sql += " AND (active_until IS NULL OR active_until > ?)"
    params.append(now_iso())
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        records = [_row_to_hazard(r) for r in rows]
    if bbox is not None:
        records = [r for r in records if _bbox_overlaps(r.get("bbox"), bbox)]
    return {"records": records}


def list_pending() -> dict:
    """Community hazard reports awaiting moderation (reviewed=0)."""
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM hazard_zones WHERE reviewed = 0 ORDER BY created_at DESC"
        ).fetchall()
        return {"records": [_row_to_hazard(r) for r in rows]}


def get_hazard(hazard_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM hazard_zones WHERE id = ?", (hazard_id,)
        ).fetchone()
        return _row_to_hazard(row) if row else None


def upsert_hazard(hazard: HazardRecord, *, source: str, reviewed: int) -> dict:
    """Create or update a hazard. Timestamp-guarded last-write-wins on update so a
    stale offline/mesh copy can't clobber a newer one (same model as /sync). The
    bbox is recomputed server-side from the geometry, never trusted from input.
    """
    now = now_iso()
    hid = hazard.id or _new_id()
    incoming_updated = hazard.updatedAt or now
    bbox = _compute_bbox(hazard.geometry)
    with db.get_db() as conn:
        existing = conn.execute(
            "SELECT updated_at FROM hazard_zones WHERE id = ?", (hid,)
        ).fetchone()
        if existing and existing["updated_at"] and incoming_updated < existing["updated_at"]:
            row = conn.execute("SELECT * FROM hazard_zones WHERE id = ?", (hid,)).fetchone()
            return _row_to_hazard(row)
        conn.execute(
            """
            INSERT INTO hazard_zones
            (id, disaster_id, type, geometry, bbox, active_from, active_until,
             source, confidence, reviewed, reporter_name, note, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              disaster_id=excluded.disaster_id, type=excluded.type,
              geometry=excluded.geometry, bbox=excluded.bbox,
              active_from=excluded.active_from, active_until=excluded.active_until,
              source=excluded.source, confidence=excluded.confidence,
              reviewed=excluded.reviewed, reporter_name=excluded.reporter_name,
              note=excluded.note, updated_at=excluded.updated_at
            """,
            (
                hid, hazard.disaster_id, hazard.type,
                json.dumps(hazard.geometry) if hazard.geometry is not None else None,
                json.dumps(bbox) if bbox is not None else None,
                hazard.active_from, hazard.active_until, source, hazard.confidence,
                reviewed, hazard.reporter_name, hazard.note,
                hazard.createdAt or now, incoming_updated,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM hazard_zones WHERE id = ?", (hid,)).fetchone()
        return _row_to_hazard(row)


def review_hazard(hazard_id: str, approve: bool) -> Optional[dict]:
    """Approve (reviewed=1) or reject (reviewed=-1) a hazard. Returns the updated
    hazard, or None if it doesn't exist."""
    with db.get_db() as conn:
        if not conn.execute(
            "SELECT 1 FROM hazard_zones WHERE id = ?", (hazard_id,)
        ).fetchone():
            return None
        conn.execute(
            "UPDATE hazard_zones SET reviewed = ?, updated_at = ? WHERE id = ?",
            (1 if approve else -1, now_iso(), hazard_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM hazard_zones WHERE id = ?", (hazard_id,)).fetchone()
        return _row_to_hazard(row)
