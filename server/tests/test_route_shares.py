"""Tests for shareable routes (plan-21 Phase 5).

A route share is a public, alias-only broadcast of a usable path from A to B.
Anyone can POST one; reads are public. The server collapses near-identical
re-shares (same rounded origin/dest + author + mode) within a short window onto
the existing row instead of inserting a duplicate.
"""

from assertions import assert_bbox_validation

ROUTE = {
    "disaster_id": "d1",
    "origin_lat": 10.5000,
    "origin_lon": -66.9000,
    "dest_lat": 10.5200,
    "dest_lon": -66.8800,
    "dest_name": "Refugio Central",
    "polyline": [[10.5000, -66.9000], [10.5100, -66.8900], [10.5200, -66.8800]],
    "mode": "walk",
    "author_alias": "Ana",
    "note": "Camino seguro evitando la inundación",
}


def _post(client, **overrides):
    body = dict(ROUTE)
    body.update(overrides)
    return client.post("/routes/share", json=body)


def test_share_and_list(client):
    r = _post(client)
    assert r.status_code == 200, r.text
    share = r.json()
    assert share["id"].startswith("rs-")
    assert share["mode"] == "walk"
    assert share["source"] == "web"
    # polyline round-trips as a list of [lat, lon] pairs.
    assert isinstance(share["polyline"], list)
    assert share["polyline"][0] == [10.5, -66.9]

    listed = client.get("/routes/shared").json()["records"]
    assert any(s["id"] == share["id"] for s in listed)
    # Single-fetch endpoint returns the decoded record.
    one = client.get(f"/routes/shared/{share['id']}").json()
    assert one["id"] == share["id"]
    assert isinstance(one["polyline"], list)


def test_identical_reshare_dedups(client):
    first = _post(client).json()
    again = _post(client).json()
    # Same dedup_key within the window → same row returned, no new insert.
    assert again["id"] == first["id"]
    records = client.get("/routes/shared").json()["records"]
    assert sum(1 for s in records if s["id"] == first["id"]) == 1
    assert len(records) == 1


def test_different_author_or_mode_creates_new(client):
    first = _post(client).json()
    other_author = _post(client, author_alias="Beto").json()
    other_mode = _post(client, mode="drive").json()
    assert other_author["id"] != first["id"]
    assert other_mode["id"] != first["id"]
    ids = {s["id"] for s in client.get("/routes/shared").json()["records"]}
    assert {first["id"], other_author["id"], other_mode["id"]} <= ids
    assert len(ids) == 3


def test_bbox_filter(client):
    share = _post(client).json()
    # Box covering the origin/dest includes it.
    inside = client.get("/routes/shared?bbox=-67.0,10.4,-66.7,10.6").json()["records"]
    assert any(s["id"] == share["id"] for s in inside)
    # Far-away box excludes it.
    outside = client.get("/routes/shared?bbox=0,0,1,1").json()["records"]
    assert all(s["id"] != share["id"] for s in outside)
    # Malformed bbox → 400.
    assert_bbox_validation(client, "/routes/shared")


def test_invalid_mode_falls_back_to_walk(client):
    share = _post(client, mode="teleport").json()
    assert share["mode"] == "walk"


def test_get_missing_404(client):
    assert client.get("/routes/shared/nope").status_code == 404
