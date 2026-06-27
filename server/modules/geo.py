"""Geospatial queries over persons/reports (plan-10 phase 3).

Persons and reports now carry optional ``lat``/``lon`` columns (db.py). These
helpers answer "who is near here" and roll points up for an operation map. The
public ``nearby_persons`` reuses the same moderation trust gate as
``modules.persons.search_persons`` so untrusted/rejected/merged rows never leak.

Distances use the haversine formula (great-circle, earth radius 6_371_000 m).
SQLite has no trig over rows, so we pre-filter with a cheap lat/lon bounding box
in SQL, then refine each candidate in Python.
"""

import math
from typing import Optional

from fastapi import HTTPException

import db
from modules.moderation import UNTRUSTED_SOURCES
from modules.persons import _redact_photos

# Meters per degree of latitude (roughly constant). Longitude degrees shrink by
# cos(latitude), handled where used.
_M_PER_DEG_LAT = 111320.0
_EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in meters."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    )
    return _EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))


def nearby_persons(
    lat: float, lon: float, radius_m: float, limit: int = 200
) -> dict:
    """Public-search persons within ``radius_m`` meters of (lat, lon).

    Applies the same trust gate as ``modules.persons.search_persons`` (reviewed
    >= 0; untrusted-source rows hidden until approved; merged duplicates hidden),
    pre-filters with a SQL bounding box, then refines with haversine. Results are
    sorted by ascending distance and capped at ``limit``; each record gains a
    rounded ``distance_m`` field. Photo fields are redacted when photos are off.
    """
    # Bounding-box half-extents in degrees. Guard cos→0 near the poles so the
    # longitude delta stays finite (fall back to a full longitude sweep).
    dlat = radius_m / _M_PER_DEG_LAT
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-12:
        dlon = 180.0
    else:
        dlon = radius_m / (_M_PER_DEG_LAT * abs(cos_lat))

    untrusted = ",".join("?" * len(UNTRUSTED_SOURCES))
    sql = (
        "SELECT * FROM persons"
        " WHERE lat IS NOT NULL AND lon IS NOT NULL"
        " AND reviewed >= 0"
        f" AND NOT (source IN ({untrusted}) AND reviewed = 0)"
        " AND merged_into IS NULL"
        " AND lat BETWEEN ? AND ?"
        " AND lon BETWEEN ? AND ?"
    )
    params = list(UNTRUSTED_SOURCES) + [lat - dlat, lat + dlat, lon - dlon, lon + dlon]

    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    results = []
    for row in rows:
        rec = db.row_to_dict(row)
        dist = haversine_m(lat, lon, rec["lat"], rec["lon"])
        if dist <= radius_m:
            rec["distance_m"] = round(dist)
            _redact_photos(rec)
            results.append(rec)

    results.sort(key=lambda r: r["distance_m"])
    results = results[:limit]
    return {"records": results, "count": len(results)}


def _require_operation(conn, op_id: str) -> None:
    """Raise 404 unless ``op_id`` is a real operation (events row)."""
    row = conn.execute("SELECT id FROM events WHERE id = ?", (op_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Operation not found")


def operation_heatmap(op_id: str) -> dict:
    """Cluster an operation's geolocated persons into weighted map points.

    Groups persons by (lat, lon rounded to ~4 decimals ≈ 11 m) and status, with
    a per-cluster ``weight`` = COUNT(*). Merged duplicates and null coords are
    excluded. ``count`` is the total number of points (clusters).
    """
    with db.get_db() as conn:
        _require_operation(conn, op_id)
        rows = conn.execute(
            "SELECT ROUND(lat, 4) AS rlat, ROUND(lon, 4) AS rlon, status,"
            " COUNT(*) AS weight FROM persons"
            " WHERE disaster_id = ? AND lat IS NOT NULL AND lon IS NOT NULL"
            " AND merged_into IS NULL"
            " GROUP BY rlat, rlon, status",
            (op_id,),
        ).fetchall()
    points = [
        {"lat": r["rlat"], "lon": r["rlon"], "weight": r["weight"], "status": r["status"]}
        for r in rows
    ]
    return {"points": points, "count": len(points)}


def operation_bounds(op_id: str) -> dict:
    """Bounding box over an operation's geolocated persons and their reports.

    Spans persons (``disaster_id = op_id``, not merged) and reports linked to
    those persons, considering only non-null coordinates. Returns all-null
    fields with ``count`` 0 when no coordinates exist.
    """
    with db.get_db() as conn:
        _require_operation(conn, op_id)
        row = conn.execute(
            """
            WITH coords AS (
                SELECT lat, lon FROM persons
                WHERE disaster_id = ? AND merged_into IS NULL
                  AND lat IS NOT NULL AND lon IS NOT NULL
                UNION ALL
                SELECT r.lat, r.lon FROM reports r
                JOIN persons p ON r.person_id = p.id
                WHERE p.disaster_id = ? AND p.merged_into IS NULL
                  AND r.lat IS NOT NULL AND r.lon IS NOT NULL
            )
            SELECT MIN(lat) AS min_lat, MIN(lon) AS min_lon,
                   MAX(lat) AS max_lat, MAX(lon) AS max_lon,
                   COUNT(*) AS count FROM coords
            """,
            (op_id, op_id),
        ).fetchone()
    count = row["count"] if row else 0
    return {
        "min_lat": row["min_lat"] if count else None,
        "min_lon": row["min_lon"] if count else None,
        "max_lat": row["max_lat"] if count else None,
        "max_lon": row["max_lon"] if count else None,
        "count": count,
    }


# Default grid cell size for sector suggestions (~0.005° ≈ 550 m at the equator).
_SECTOR_CELL_DEG = 0.005


def suggested_sectors(op_id: str, top: int = 5,
                      cell_deg: float = _SECTOR_CELL_DEG) -> dict:
    """Suggest search sectors for an operation by report/person density (plan-13).

    Buckets every geolocated person and observation into a square lat/lon grid and
    returns the densest cells as candidate "hot zone" sectors, each with its
    bounding box, centroid and a weight (point count). The commander can dispatch
    teams to the highest-weight sectors first.
    """
    cell = cell_deg if cell_deg and cell_deg > 0 else _SECTOR_CELL_DEG
    top = max(1, min(int(top), 50))
    with db.get_db() as conn:
        _require_operation(conn, op_id)
        rows = conn.execute(
            """
            WITH coords AS (
                SELECT lat, lon FROM persons
                WHERE disaster_id = ? AND merged_into IS NULL
                  AND lat IS NOT NULL AND lon IS NOT NULL
                UNION ALL
                SELECT r.lat, r.lon FROM reports r
                JOIN persons p ON r.person_id = p.id
                WHERE p.disaster_id = ? AND p.merged_into IS NULL
                  AND r.lat IS NOT NULL AND r.lon IS NOT NULL
            )
            SELECT
              CAST(lat / ? AS INTEGER) AS gy,
              CAST(lon / ? AS INTEGER) AS gx,
              COUNT(*) AS weight,
              AVG(lat) AS clat, AVG(lon) AS clon
            FROM coords
            GROUP BY gy, gx
            ORDER BY weight DESC
            LIMIT ?
            """,
            (op_id, op_id, cell, cell, top),
        ).fetchall()
    sectors = []
    for i, r in enumerate(rows):
        gy, gx = r["gy"], r["gx"]
        sectors.append({
            "sector": f"S{i + 1}",
            "weight": r["weight"],
            "centroid": {"lat": round(r["clat"], 6), "lon": round(r["clon"], 6)},
            "bounds": {
                "min_lat": round(gy * cell, 6),
                "min_lon": round(gx * cell, 6),
                "max_lat": round((gy + 1) * cell, 6),
                "max_lon": round((gx + 1) * cell, 6),
            },
        })
    return {"sectors": sectors, "count": len(sectors), "cell_deg": cell}
