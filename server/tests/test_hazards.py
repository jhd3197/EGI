"""Tests for hazard zones (plan-21 Phase 4).

A hazard zone is a flagged danger area the public map renders and the offline
router can avoid. Public POSTs land as community ``hazard_report`` rows
(reviewed=0) awaiting moderation but still visible (flagged); an operator can
approve/reject them. In the test DB no users/tokens exist, so the operator-gated
moderation endpoints use the dev bypass.
"""

POLYGON = {
    "type": "flood",
    "geometry": {"kind": "polygon", "coords": [[10.6, -66.9], [10.6, -66.8], [10.7, -66.8]]},
}


def _post(client, **overrides):
    body = dict(POLYGON)
    body.update(overrides)
    return client.post("/hazards", json=body)


def test_post_lands_pending_and_is_visible(client):
    r = _post(client)
    assert r.status_code == 200, r.text
    haz = r.json()
    assert haz["source"] == "hazard_report"
    assert haz["reviewed"] == 0
    assert haz["id"].startswith("haz-")
    # bbox computed server-side: [minLon, minLat, maxLon, maxLat].
    assert haz["bbox"] == [-66.9, 10.6, -66.8, 10.7]

    listed = client.get("/hazards").json()["records"]
    assert any(h["id"] == haz["id"] for h in listed)


def test_invalid_type_rejected(client):
    r = _post(client, type="meteor")
    assert r.status_code == 400


def test_bbox_filter(client):
    haz = _post(client).json()
    # Overlapping bbox includes it.
    inside = client.get("/hazards?bbox=-67.0,10.5,-66.7,10.8").json()["records"]
    assert any(h["id"] == haz["id"] for h in inside)
    # Far-away bbox excludes it.
    outside = client.get("/hazards?bbox=0,0,1,1").json()["records"]
    assert all(h["id"] != haz["id"] for h in outside)
    # Malformed bbox → 400.
    assert client.get("/hazards?bbox=1,2,3").status_code == 400
    assert client.get("/hazards?bbox=a,b,c,d").status_code == 400


def test_circle_bbox(client):
    r = _post(
        client,
        geometry={"kind": "circle", "center": [10.0, -66.0], "radius_m": 1000},
    )
    haz = r.json()
    minlon, minlat, maxlon, maxlat = haz["bbox"]
    assert minlon < -66.0 < maxlon
    assert minlat < 10.0 < maxlat


def test_review_approve_and_reject(client):
    haz = _post(client).json()
    assert client.get("/hazards/pending").json()["records"]  # dev-bypass operator

    approved = client.post(f"/hazards/{haz['id']}/review", json={"approve": True})
    assert approved.status_code == 200, approved.text
    assert approved.json()["reviewed"] == 1
    # Approved hazard no longer pending.
    assert all(h["id"] != haz["id"] for h in client.get("/hazards/pending").json()["records"])

    # A second hazard, rejected, is hidden from the active list.
    other = _post(client).json()
    rej = client.post(f"/hazards/{other['id']}/review", json={"approve": False})
    assert rej.status_code == 200
    assert rej.json()["reviewed"] == -1
    active = client.get("/hazards").json()["records"]
    assert all(h["id"] != other["id"] for h in active)


def test_review_missing_404(client):
    assert client.post("/hazards/nope/review", json={"approve": True}).status_code == 404


def test_expired_hazard_excluded(client):
    haz = _post(client, active_until="2000-01-01T00:00:00Z").json()
    active = client.get("/hazards").json()["records"]
    assert all(h["id"] != haz["id"] for h in active)
