"""Offline routing packs (plan-21, Phase 2).

A *routing pack* is a small cached road-network graph the PWA downloads once and
runs an on-device A* over, so an offline route follows actual roads instead of a
straight line. The server's job is narrow: build/seed a pack, store its JSON
graph file under ``data/routing_packs/``, index its metadata in the
``routing_packs`` table, and serve both. **No routing compute happens here** —
A* is entirely client-side (``frontend/src/lib/routeGraph.js``).

Graph JSON format (server and client depend on it EXACTLY):

    {
      "id": "la-guaira-demo",
      "region": "La Guaira",
      "bbox": [minLon, minLat, maxLon, maxLat],
      "nodes": [[lat, lon], ...],                 # index = node id
      "edges": [[fromIdx, toIdx, meters, flags]], # flags: 1=walk,2=drive+walk
      "version": 1,
      "built_at": "<iso>"
    }

Edges are bidirectional; ``meters`` is precomputed (Haversine). Packs are kept
small so the whole graph fits comfortably in a single download + IndexedDB row.

ASSUMPTION: the demo pack is seeded from ``db.init_db`` (after its transaction
commits) via ``seed_demo_packs()`` rather than lazily on first ``list_packs``,
because the plan's verification runs ``python -m db`` and expects the pack to
exist immediately. ``register_pack`` is version-guarded, so re-seeding is a no-op.
"""

import json
import os
from pathlib import Path
from typing import List, Optional

import db
from models import now_iso
from modules import geo

# Where pack JSON files live. Derived from db.DB_PATH's parent (the server data
# dir) at call time, NOT at import, so it follows the monkeypatched DB_PATH the
# test suite sets — keeping pack files inside each test's tmp dir.
def _packs_dir() -> Path:
    d = Path(db.DB_PATH).resolve().parent / "routing_packs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two lat/lon points."""
    return geo.haversine_m(lat1, lon1, lat2, lon2)


def _row_to_meta(row) -> dict:
    d = db.row_to_dict(row)
    try:
        d["bbox"] = json.loads(d["bbox"]) if d.get("bbox") else None
    except (TypeError, ValueError):
        d["bbox"] = None
    return d


# ── Metadata reads ───────────────────────────────────────────────────────────


def list_packs(region: Optional[str] = None) -> List[dict]:
    """Return pack metadata dicts, optionally filtered by region."""
    sql = "SELECT * FROM routing_packs"
    params: list = []
    if region:
        sql += " WHERE region = ?"
        params.append(region)
    sql += " ORDER BY region COLLATE NOCASE ASC, id ASC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_meta(r) for r in rows]


def get_pack_meta(pack_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM routing_packs WHERE id = ?", (pack_id,)
        ).fetchone()
        return _row_to_meta(row) if row else None


def get_pack_path(pack_id: str) -> Optional[str]:
    """Absolute path to the pack's JSON graph file, or None if absent on disk."""
    meta = get_pack_meta(pack_id)
    if not meta or not meta.get("file_path"):
        return None
    p = Path(meta["file_path"])
    return str(p) if p.is_file() else None


# ── Registration (write) ─────────────────────────────────────────────────────


def register_pack(meta: dict, graph_json: dict) -> dict:
    """Write the graph JSON file and upsert the metadata row.

    Timestamp/version guarded last-write-wins like /sync: if a pack with this id
    already exists at an equal-or-newer version, the write is skipped and the
    stored metadata is returned unchanged. ``meta`` must carry ``id``; ``region``
    / ``bbox`` / ``version`` are read from ``graph_json`` when absent.
    """
    pack_id = meta["id"]
    region = meta.get("region") or graph_json.get("region")
    bbox = meta.get("bbox") or graph_json.get("bbox")
    version = int(meta.get("version") or graph_json.get("version") or 1)
    nodes = graph_json.get("nodes") or []
    edges = graph_json.get("edges") or []
    now = now_iso()

    with db.get_db() as conn:
        existing = conn.execute(
            "SELECT version, created_at FROM routing_packs WHERE id = ?", (pack_id,)
        ).fetchone()
        if existing and existing["version"] is not None and version <= existing["version"]:
            # Stale or equal: keep the stored pack (and its file) as-is.
            row = conn.execute(
                "SELECT * FROM routing_packs WHERE id = ?", (pack_id,)
            ).fetchone()
            return _row_to_meta(row)

        # Persist the graph file first, then the index row, so the row never
        # points at a missing file.
        file_path = _packs_dir() / f"{pack_id}.json"
        payload = json.dumps(graph_json, separators=(",", ":"))
        file_path.write_text(payload, encoding="utf-8")
        size_bytes = len(payload.encode("utf-8"))
        created_at = existing["created_at"] if existing else now

        conn.execute(
            """
            INSERT INTO routing_packs
            (id, region, bbox, node_count, edge_count, size_bytes, version,
             file_path, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              region=excluded.region, bbox=excluded.bbox,
              node_count=excluded.node_count, edge_count=excluded.edge_count,
              size_bytes=excluded.size_bytes, version=excluded.version,
              file_path=excluded.file_path, updated_at=excluded.updated_at
            """,
            (
                pack_id, region, json.dumps(bbox) if bbox is not None else None,
                len(nodes), len(edges), size_bytes, version,
                str(file_path), created_at, now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM routing_packs WHERE id = ?", (pack_id,)
        ).fetchone()
        return _row_to_meta(row)


# ── Demo pack ────────────────────────────────────────────────────────────────


def build_demo_pack() -> dict:
    """Build a small but real-ish road-network graph for "La Guaira".

    A deterministic grid of streets over a plausible La Guaira bbox, with a
    central block of removed edges so a route genuinely has to bend around it
    rather than going straight. ~36 nodes / ~50 edges — small enough to ship in
    one download, big enough that A* visibly follows the grid.
    """
    # Bounding box around La Guaira, Venezuela (coastal strip).
    min_lat, max_lat = 10.5950, 10.6150
    min_lon, max_lon = -66.9450, -66.9150
    rows, cols = 6, 6

    nodes: List[List[float]] = []
    for r in range(rows):
        for c in range(cols):
            lat = min_lat + (max_lat - min_lat) * (r / (rows - 1))
            lon = min_lon + (max_lon - min_lon) * (c / (cols - 1))
            nodes.append([round(lat, 6), round(lon, 6)])

    def nid(r: int, c: int) -> int:
        return r * cols + c

    # A central "block" (a building/closed area) whose internal grid edges are
    # removed, forcing detours. Removing edges that touch nodes at (r in 2..3,
    # c in 2..3) keeps the rest of the grid fully connected via the perimeter.
    blocked = {(r, c) for r in (2, 3) for c in (2, 3)}

    edges: List[List] = []
    flags = 2  # drive + walk both OK (treated as bidirectional walking for MVP)
    for r in range(rows):
        for c in range(cols):
            a = nid(r, c)
            # Horizontal neighbour
            if c + 1 < cols and not ((r, c) in blocked and (r, c + 1) in blocked):
                b = nid(r, c + 1)
                m = _haversine_m(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1])
                edges.append([a, b, round(m, 1), flags])
            # Vertical neighbour
            if r + 1 < rows and not ((r, c) in blocked and (r + 1, c) in blocked):
                b = nid(r + 1, c)
                m = _haversine_m(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1])
                edges.append([a, b, round(m, 1), flags])

    return {
        "id": "la-guaira-demo",
        "region": "La Guaira",
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "nodes": nodes,
        "edges": edges,
        "version": 1,
        "built_at": now_iso(),
    }


def seed_demo_packs() -> None:
    """Register the built-in demo pack(s). Idempotent (version-guarded)."""
    graph = build_demo_pack()
    register_pack({"id": graph["id"], "region": graph["region"]}, graph)
