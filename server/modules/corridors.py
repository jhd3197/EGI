"""Evacuation-corridor data model + logic (plan-21 Phase 6).

An evacuation corridor is an OFFICIAL recommended path out of a danger area that
the map renders so people know which way to go. Unlike a crowd-sourced route
share, a corridor is authoritative: writes are operator-gated and land trusted
(``source='official'``). It is distinct from a hazard zone (a danger area to
avoid) — a corridor is the safe way out.

``path`` is stored as JSON TEXT (a list of ``[lat, lon]`` pairs) and decoded here
so the HTTP layer and clients always see a real list. ``bbox`` is computed
server-side (never trusted from the client) for cheap overlap filtering, emitted
lon-first like the routing-pack / hazard bbox: ``[minLon, minLat, maxLon,
maxLat]``. Upserts are timestamp-guarded last-write-wins on id (same model as
/sync) so a stale offline/mesh copy can't clobber a newer one.
"""

import json
import uuid
from typing import List, Optional

import db
from models import CorridorRecord, now_iso
from modules import geo


def _new_id() -> str:
    return f"corr-{uuid.uuid4().hex[:10]}"


def _compute_bbox(path: Optional[list]) -> Optional[list]:
    """Return ``[minLon, minLat, maxLon, maxLat]`` for a ``[[lat,lon],...]`` path.

    Coordinates in the path are ``[lat, lon]`` (the wire contract); the bbox is
    emitted lon-first like the routing-pack/hazard bbox. Returns None for an empty
    or malformed path so an unparseable shape never crashes an upsert."""
    return geo.bbox_from_points(path)


def _row_to_corridor(row) -> dict:
    """Decode a DB row: parse ``path`` and ``bbox`` JSON back to lists."""
    d = db.row_to_dict(row)
    for col in ("path", "bbox"):
        raw = d.get(col)
        if raw:
            try:
                d[col] = json.loads(raw)
            except (TypeError, ValueError):
                d[col] = None
    return d


def _bbox_overlaps(stored: Optional[list], query: list) -> bool:
    """Axis-aligned overlap test between two ``[minLon,minLat,maxLon,maxLat]``."""
    return geo.bbox_overlaps(stored, query)


def list_corridors(
    disaster_id: Optional[str] = None,
    bbox: Optional[list] = None,
) -> dict:
    """Evacuation corridors, newest first. Optional disaster + bbox filtering."""
    sql = "SELECT * FROM evacuation_corridors"
    params: list = []
    if disaster_id:
        sql += " WHERE disaster_id = ?"
        params.append(disaster_id)
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        records = [_row_to_corridor(r) for r in rows]
    if bbox is not None:
        records = [r for r in records if _bbox_overlaps(r.get("bbox"), bbox)]
    return {"records": records}


def get_corridor(corridor_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM evacuation_corridors WHERE id = ?", (corridor_id,)
        ).fetchone()
        return _row_to_corridor(row) if row else None


def upsert_corridor(rec: CorridorRecord, *, source: str) -> dict:
    """Create or update an evacuation corridor.

    Timestamp-guarded last-write-wins on update so a stale offline/mesh copy can't
    clobber a newer one (same model as /sync). The bbox is recomputed server-side
    from the path, never trusted from input. Returns the decoded dict (path/bbox
    parsed to lists)."""
    now = now_iso()
    cid = rec.id or _new_id()
    incoming_updated = rec.updatedAt or now
    bbox = _compute_bbox(rec.path)
    path_json = json.dumps(rec.path) if rec.path is not None else None
    with db.get_db() as conn:
        existing = conn.execute(
            "SELECT updated_at FROM evacuation_corridors WHERE id = ?", (cid,)
        ).fetchone()
        if existing and existing["updated_at"] and incoming_updated < existing["updated_at"]:
            row = conn.execute(
                "SELECT * FROM evacuation_corridors WHERE id = ?", (cid,)
            ).fetchone()
            return _row_to_corridor(row)
        conn.execute(
            """
            INSERT INTO evacuation_corridors
            (id, disaster_id, name, status, mode, path, bbox, note, source,
             created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              disaster_id=excluded.disaster_id, name=excluded.name,
              status=excluded.status, mode=excluded.mode, path=excluded.path,
              bbox=excluded.bbox, note=excluded.note, source=excluded.source,
              updated_at=excluded.updated_at
            """,
            (
                cid, rec.disaster_id, rec.name, rec.status or "open",
                rec.mode or "drive", path_json,
                json.dumps(bbox) if bbox is not None else None,
                rec.note, source, rec.createdAt or now, incoming_updated,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM evacuation_corridors WHERE id = ?", (cid,)
        ).fetchone()
        return _row_to_corridor(row)


# ── Demo corridor ─────────────────────────────────────────────────────────────

# A deterministic demo corridor near the La Guaira demo routing-pack bbox
# (`[-66.945, 10.595, -66.915, 10.615]`). Fixed id so re-seeding is idempotent.
_DEMO_CORRIDOR_ID = "corr-la-guaira-demo"
_DEMO_PATH = [
    [10.5970, -66.9430],
    [10.6010, -66.9370],
    [10.6050, -66.9300],
    [10.6090, -66.9230],
    [10.6130, -66.9170],
]


def seed_demo_corridor() -> None:
    """Register the built-in demo evacuation corridor. Idempotent (skips if the
    fixed-id row already exists), mirroring ``routing.seed_demo_packs``."""
    if get_corridor(_DEMO_CORRIDOR_ID):
        return
    rec = CorridorRecord(
        id=_DEMO_CORRIDOR_ID,
        disaster_id="la-guaira-demo",
        name="Corredor de evacuación Litoral",
        status="open",
        mode="drive",
        path=_DEMO_PATH,
        note="Ruta recomendada de evacuación hacia zona segura.",
        source="official",
    )
    upsert_corridor(rec, source="official")
