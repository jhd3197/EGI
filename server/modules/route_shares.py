"""Shareable route records + logic (plan-21 Phase 5).

A route share is a victim or responder broadcasting "here is a usable path from
A to B" so others can reuse it (e.g. a safe walking route around flooding). It is
deliberately low-trust and public: anyone can share, like a shelter check-in.

``polyline`` is stored as JSON TEXT (a list of ``[lat, lon]`` pairs) and decoded
here so the HTTP layer and clients always see a real list. To avoid a flood of
near-identical re-shares (the same path posted repeatedly as someone walks it),
``share_route`` computes a ``dedup_key`` (a hash of the rounded origin/dest +
author + mode); if a row with that key was created within the last 6 hours we
return the existing row instead of inserting a duplicate (plan-21 §8.4). A genuine
re-share carrying a newer ``updatedAt`` still updates the matched row in place
(timestamp-guarded last-write-wins on id, same model as /sync, shelters, hazards).
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import db
from models import RouteShareRecord, now_iso

# Window during which an identical re-share collapses onto the existing row.
_DEDUP_WINDOW_HOURS = 6


def _new_id() -> str:
    return f"rs-{uuid.uuid4().hex[:10]}"


def _round(v: Optional[float]) -> str:
    """Round a coordinate to 4 dp (~11 m) for the dedup key, or '' if absent."""
    try:
        return f"{float(v):.4f}"
    except (TypeError, ValueError):
        return ""


def _dedup_key(rec: RouteShareRecord) -> str:
    """sha256 hex of rounded origin/dest (4 dp) + author_alias + mode.

    De-duplicates near-identical shares: two posts of the same path from the same
    alias in the same mode hash to the same key (small GPS jitter rounds away)."""
    parts = "|".join(
        [
            _round(rec.origin_lat),
            _round(rec.origin_lon),
            _round(rec.dest_lat),
            _round(rec.dest_lon),
            (rec.author_alias or "").strip().lower(),
            (rec.mode or "walk"),
        ]
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


def _row_to_share(row) -> dict:
    """Decode a DB row to a dict with ``polyline`` parsed from JSON to a list."""
    d = db.row_to_dict(row)
    raw = d.get("polyline")
    if raw:
        try:
            d["polyline"] = json.loads(raw)
        except (TypeError, ValueError):
            d["polyline"] = None
    return d


def _bbox_overlaps_point(bbox: list, lat, lon) -> bool:
    """True if (lat, lon) falls inside ``[minLon, minLat, maxLon, maxLat]``."""
    if lat is None or lon is None:
        return False
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def share_route(rec: RouteShareRecord, *, source: str) -> dict:
    """Create a route share, or return an existing near-identical one.

    Computes a dedup_key; if a row with the same key was created within the last
    ``_DEDUP_WINDOW_HOURS`` it is returned as-is (no duplicate insert) — unless the
    incoming record carries a newer ``updatedAt``, in which case it updates that
    row in place (timestamp-guarded last-write-wins on id). Returns the decoded
    dict (polyline parsed to a list)."""
    now = now_iso()
    key = _dedup_key(rec)
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=_DEDUP_WINDOW_HOURS)
    ).isoformat()
    incoming_updated = rec.updatedAt or now
    polyline_json = json.dumps(rec.polyline) if rec.polyline is not None else None
    with db.get_db() as conn:
        # Recent identical share? Collapse onto it (newest within the window).
        existing = conn.execute(
            "SELECT * FROM route_shares WHERE dedup_key = ? AND created_at > ? "
            "ORDER BY created_at DESC LIMIT 1",
            (key, cutoff),
        ).fetchone()
        if existing:
            # A re-share with a newer timestamp updates the matched row in place;
            # an older/equal one is a no-op and returns the stored row.
            if existing["updated_at"] and incoming_updated <= existing["updated_at"]:
                return _row_to_share(existing)
            conn.execute(
                """
                UPDATE route_shares SET
                  disaster_id=?, origin_lat=?, origin_lon=?, dest_lat=?, dest_lon=?,
                  dest_name=?, polyline=?, mode=?, author_alias=?, note=?,
                  source=?, updated_at=?
                WHERE id=?
                """,
                (
                    rec.disaster_id, rec.origin_lat, rec.origin_lon,
                    rec.dest_lat, rec.dest_lon, rec.dest_name, polyline_json,
                    rec.mode or "walk", rec.author_alias, rec.note, source,
                    incoming_updated, existing["id"],
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM route_shares WHERE id = ?", (existing["id"],)
            ).fetchone()
            return _row_to_share(row)

        rid = rec.id or _new_id()
        # Timestamp-guarded last-write-wins on id (same model as /sync), so a
        # stale offline/mesh copy of a known id can't clobber a newer one.
        prior = conn.execute(
            "SELECT updated_at FROM route_shares WHERE id = ?", (rid,)
        ).fetchone()
        if prior and prior["updated_at"] and incoming_updated < prior["updated_at"]:
            row = conn.execute(
                "SELECT * FROM route_shares WHERE id = ?", (rid,)
            ).fetchone()
            return _row_to_share(row)
        conn.execute(
            """
            INSERT INTO route_shares
            (id, disaster_id, origin_lat, origin_lon, dest_lat, dest_lon,
             dest_name, polyline, mode, author_alias, note, dedup_key, source,
             created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              disaster_id=excluded.disaster_id, origin_lat=excluded.origin_lat,
              origin_lon=excluded.origin_lon, dest_lat=excluded.dest_lat,
              dest_lon=excluded.dest_lon, dest_name=excluded.dest_name,
              polyline=excluded.polyline, mode=excluded.mode,
              author_alias=excluded.author_alias, note=excluded.note,
              dedup_key=excluded.dedup_key, source=excluded.source,
              updated_at=excluded.updated_at
            """,
            (
                rid, rec.disaster_id, rec.origin_lat, rec.origin_lon,
                rec.dest_lat, rec.dest_lon, rec.dest_name, polyline_json,
                rec.mode or "walk", rec.author_alias, rec.note, key, source,
                rec.createdAt or now, incoming_updated,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM route_shares WHERE id = ?", (rid,)
        ).fetchone()
        return _row_to_share(row)


def list_shared(
    disaster_id: Optional[str] = None,
    bbox: Optional[list] = None,
    limit: int = 100,
) -> dict:
    """Shared routes, newest first. Optional disaster + bbox filtering.

    ``bbox`` is ``[minLon, minLat, maxLon, maxLat]``; a share matches when its
    ORIGIN or DEST point falls inside the box (so a route into or out of a viewed
    area shows up)."""
    sql = "SELECT * FROM route_shares"
    params: list = []
    if disaster_id:
        sql += " WHERE disaster_id = ?"
        params.append(disaster_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        records = [_row_to_share(r) for r in rows]
    if bbox is not None and len(bbox) == 4:
        records = [
            r for r in records
            if _bbox_overlaps_point(bbox, r.get("origin_lat"), r.get("origin_lon"))
            or _bbox_overlaps_point(bbox, r.get("dest_lat"), r.get("dest_lon"))
        ]
    return {"records": records}


def get_route_share(share_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM route_shares WHERE id = ?", (share_id,)
        ).fetchone()
        return _row_to_share(row) if row else None
