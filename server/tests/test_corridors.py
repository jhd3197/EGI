"""Tests for evacuation corridors (plan-21 Phase 6).

An evacuation corridor is an OFFICIAL recommended path out of a danger area.
Reads are public; writes are operator-gated (in the test DB no users/tokens exist,
so the operator-gated POST uses the dev bypass). A deterministic demo corridor is
seeded by db.init_db, so it is present immediately after the schema is created.
"""

from assertions import assert_bbox_validation

CORRIDOR = {
    "disaster_id": "d1",
    "name": "Salida norte",
    "status": "open",
    "mode": "drive",
    "path": [[10.500, -66.900], [10.510, -66.890], [10.520, -66.880]],
    "note": "Ruta de evacuación recomendada",
}


def _post(client, **overrides):
    body = dict(CORRIDOR)
    body.update(overrides)
    return client.post("/corridors", json=body)


def test_demo_corridor_present_after_init(client):
    records = client.get("/corridors").json()["records"]
    demo = next((c for c in records if c["id"] == "corr-la-guaira-demo"), None)
    assert demo is not None, "demo corridor should be seeded by db.init_db"
    assert demo["status"] == "open"
    assert demo["mode"] == "drive"
    assert demo["source"] == "official"
    # path round-trips as a list of [lat, lon] pairs.
    assert isinstance(demo["path"], list)
    assert demo["path"][0] == [10.5970, -66.9430]
    # bbox computed server-side, lon-first.
    assert demo["bbox"] == [-66.9430, 10.5970, -66.9170, 10.6130]


def test_operator_post_creates_and_lists(client):
    r = _post(client)
    assert r.status_code == 200, r.text
    corr = r.json()
    assert corr["id"].startswith("corr-")
    assert corr["source"] == "official"
    assert corr["status"] == "open"
    # path round-trips as a list.
    assert isinstance(corr["path"], list)
    assert corr["path"][0] == [10.5, -66.9]
    # bbox computed server-side: [minLon, minLat, maxLon, maxLat].
    assert corr["bbox"] == [-66.9, 10.5, -66.88, 10.52]

    listed = client.get("/corridors").json()["records"]
    assert any(c["id"] == corr["id"] for c in listed)
    # Single-fetch endpoint returns the decoded record.
    one = client.get(f"/corridors/{corr['id']}").json()
    assert one["id"] == corr["id"]
    assert isinstance(one["path"], list)


def test_bbox_filter(client):
    corr = _post(client).json()
    # Box covering the path includes it.
    inside = client.get("/corridors?bbox=-67.0,10.4,-66.7,10.6").json()["records"]
    assert any(c["id"] == corr["id"] for c in inside)
    # Far-away box excludes it.
    outside = client.get("/corridors?bbox=0,0,1,1").json()["records"]
    assert all(c["id"] != corr["id"] for c in outside)
    # Malformed bbox → 400.
    assert_bbox_validation(client, "/corridors")


def test_invalid_status_rejected(client):
    r = _post(client, status="exploded")
    assert r.status_code == 422


def test_invalid_mode_falls_back_to_drive(client):
    corr = _post(client, mode="teleport").json()
    assert corr["mode"] == "drive"


def test_get_missing_404(client):
    assert client.get("/corridors/nope").status_code == 404
