# Geospatial endpoints (plan-10 phase 3): nearby person lookup + operation
# heatmap/bounds. TEST DATA — NOT REAL. All names/coords are fake.
#
# Covers: the haversine/bounding-box nearby query (close in, far out, distance_m
# present) at both the module and HTTP layers, plus per-operation heatmap point
# clustering and the bounds box spanning persons + their reports.

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import geo
from routes import geo as geo_routes
from routes import persons as persons_routes

# A reference point (fake coordinates near Caracas) and a person ~150 m north of
# it (≈0.00135° latitude) plus one ~5 km away that must fall outside a 1 km query.
REF_LAT, REF_LON = 10.5000, -66.9000
NEAR_LAT, NEAR_LON = 10.50135, -66.9000   # ~150 m north
FAR_LAT, FAR_LON = 10.5450, -66.9000      # ~5 km north


def _seed_geo_persons(client, op_id=None):
    """Seed one near + one far person (both trusted web source) via /sync."""
    base = {"createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"}
    near = {"id": "p-near", "name": "Cerca", "status": "missing",
            "lat": NEAR_LAT, "lon": NEAR_LON, **base}
    far = {"id": "p-far", "name": "Lejos", "status": "missing",
           "lat": FAR_LAT, "lon": FAR_LON, **base}
    if op_id:
        near["disaster_id"] = op_id
        far["disaster_id"] = op_id
    res = client.post("/sync", json={"records": [near, far]})
    assert res.status_code == 200, res.text


# ── module-level haversine / nearby (no routing involved) ────────────────────

def test_haversine_known_distance():
    # One degree of latitude is ~111.2 km; assert within 1%.
    d = geo.haversine_m(0.0, 0.0, 1.0, 0.0)
    assert abs(d - 111195) < 1200


def test_nearby_persons_module_filters_by_radius(client):
    _seed_geo_persons(client)
    out = geo.nearby_persons(REF_LAT, REF_LON, radius_m=1000)
    ids = [r["id"] for r in out["records"]]
    assert "p-near" in ids and "p-far" not in ids
    assert out["count"] == 1
    near = out["records"][0]
    assert "distance_m" in near and 100 <= near["distance_m"] <= 300


def test_nearby_persons_module_wider_radius_includes_far(client):
    _seed_geo_persons(client)
    out = geo.nearby_persons(REF_LAT, REF_LON, radius_m=10000)
    ids = [r["id"] for r in out["records"]]
    assert "p-near" in ids and "p-far" in ids
    # Sorted by ascending distance.
    assert out["records"][0]["id"] == "p-near"


def test_nearby_persons_excludes_untrusted_unreviewed(client):
    # An OCR-source, unreviewed person at the near point must be hidden by the
    # public trust gate even though it is within radius.
    client.post("/sync", json={"records": [
        {"id": "p-ocr", "name": "OCR", "status": "missing", "source": "ocr",
         "reviewed": 0, "lat": NEAR_LAT, "lon": NEAR_LON,
         "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
    ]})
    out = geo.nearby_persons(REF_LAT, REF_LON, radius_m=1000)
    assert [r["id"] for r in out["records"]] == []


# ── /persons/nearby via HTTP, with geo router ordered before persons ─────────

def _routed_client():
    """Fresh app that includes the geo router BEFORE the persons router (and
    without the SPA catch-all), so /persons/nearby isn't shadowed. This mirrors
    the wiring the orchestrator must add to main.py. Shares the same temp DB as
    the `client` fixture, so seeding via `client` is visible here."""
    app = FastAPI()
    app.include_router(geo_routes.router)      # MUST come first
    app.include_router(persons_routes.router)
    return TestClient(app)


def test_nearby_http_returns_close_excludes_far(client):
    # Seed through the main client (same temp DB), then query via a router-ordered app.
    op = client.post("/operations", json={"name": "Geo Op"}).json()
    _seed_geo_persons(client, op_id=op["id"])
    routed = _routed_client()
    res = routed.get("/persons/nearby", params={"lat": REF_LAT, "lon": REF_LON, "radius_m": 1000})
    assert res.status_code == 200, res.text
    body = res.json()
    ids = [r["id"] for r in body["records"]]
    assert "p-near" in ids and "p-far" not in ids
    assert body["records"][0]["distance_m"] >= 0


def test_nearby_http_rejects_bad_coords(client):
    routed = _routed_client()
    res = routed.get("/persons/nearby", params={"lat": 999, "lon": 0})
    assert res.status_code == 400


# ── operation heatmap + bounds via HTTP (unambiguous paths) ──────────────────

def test_operation_heatmap_returns_points(client):
    op = client.post("/operations", json={"name": "Heat Op"}).json()
    _seed_geo_persons(client, op_id=op["id"])
    res = _routed_client().get(f"/operations/{op['id']}/heatmap")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == 2
    coords = {(p["lat"], p["lon"]) for p in body["points"]}
    assert (round(NEAR_LAT, 4), round(NEAR_LON, 4)) in coords
    assert all(p["weight"] >= 1 for p in body["points"])


def test_operation_heatmap_404_for_unknown_op(client):
    assert _routed_client().get("/operations/ghost/heatmap").status_code == 404


def test_operation_bounds_spans_persons(client):
    op = client.post("/operations", json={"name": "Bounds Op"}).json()
    _seed_geo_persons(client, op_id=op["id"])
    res = _routed_client().get(f"/operations/{op['id']}/bounds")
    assert res.status_code == 200, res.text
    b = res.json()
    assert b["count"] == 2
    assert b["min_lat"] == min(NEAR_LAT, FAR_LAT)
    assert b["max_lat"] == max(NEAR_LAT, FAR_LAT)


def test_operation_bounds_includes_report_coords(client):
    op = client.post("/operations", json={"name": "Bounds Op 2"}).json()
    _seed_geo_persons(client, op_id=op["id"])
    # A report on the near person at a more extreme coordinate widens the box.
    rep_lat = 10.6000
    client.post("/persons/p-near/reports", json={
        "id": "rep-geo-1", "person_id": "p-near", "status": "sighted",
        "lat": rep_lat, "lon": -66.9000,
        "createdAt": "2026-01-02T00:00:00Z", "updatedAt": "2026-01-02T00:00:00Z"})
    res = _routed_client().get(f"/operations/{op['id']}/bounds")
    b = res.json()
    assert b["max_lat"] == rep_lat
    assert b["count"] == 3


def test_operation_bounds_empty_when_no_coords(client):
    op = client.post("/operations", json={"name": "Empty Op"}).json()
    res = _routed_client().get(f"/operations/{op['id']}/bounds")
    b = res.json()
    assert b["count"] == 0 and b["min_lat"] is None
