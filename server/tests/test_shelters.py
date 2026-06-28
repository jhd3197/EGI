"""Tests for the shelter & refugee information hub (plan-20).

Covers the JSON-array round-trip, responder filters, the official update feed
(role tagging + occupancy side-effects), capacity patches, public check-in +
family alias search, and the verified-operator token → claim → official-post
flow. The dev DB has no users, so writes use the no-auth dev bypass except the
auth test, which creates a user to exercise the real gate.
"""

import pytest


def _make_shelter(client, **over):
    body = {
        "disaster_id": "d1", "name": "Refugio Uno", "kind": "refugio",
        "lat": 10.5, "lon": -66.9, "capacity_total": 100, "capacity_available": 30,
        "accepting_new": 1, "services": ["beds", "food", "pets"],
        "supply_needs": ["water"], "target_populations": ["minors"],
    }
    body.update(over)
    r = client.post("/shelters", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_upsert_decodes_json_arrays(client):
    s = _make_shelter(client)
    assert s["services"] == ["beds", "food", "pets"]
    assert s["supply_needs"] == ["water"]
    assert s["accepting_new"] is True
    # round-trips on GET too
    got = client.get(f"/shelters/{s['id']}").json()
    assert got["services"] == ["beds", "food", "pets"]


def test_list_and_filters(client):
    full = _make_shelter(client, name="Lleno", capacity_available=0, accepting_new=0,
                         services=["beds"], supply_needs=[])
    pets = _make_shelter(client, name="Mascotas", services=["beds", "pets"], supply_needs=["food"])
    med = _make_shelter(client, name="Medico", services=["beds", "medical"], supply_needs=[])

    allrows = client.get("/shelters?disaster_id=d1").json()["records"]
    assert len(allrows) == 3
    # has_space hides the full one
    space = client.get("/shelters?disaster_id=d1&has_space=true").json()["records"]
    names = {s["name"] for s in space}
    assert "Lleno" not in names and "Mascotas" in names
    # pets / medical
    assert {s["name"] for s in client.get("/shelters?disaster_id=d1&accepts_pets=true").json()["records"]} == {"Mascotas"}
    assert {s["name"] for s in client.get("/shelters?disaster_id=d1&has_medical=true").json()["records"]} == {"Medico"}
    # needs_supplies (non-empty supply list)
    sup = {s["name"] for s in client.get("/shelters?disaster_id=d1&needs_supplies=true").json()["records"]}
    assert "Mascotas" in sup and "Medico" not in sup


def test_update_feed_tags_role_and_applies_occupancy(client):
    s = _make_shelter(client, occupancy=10)
    r = client.post(f"/shelters/{s['id']}/updates", json={"message": "Casi lleno", "occupancy_delta": 5})
    assert r.status_code == 200
    assert r.json()["author_role"] == "official"  # authorized writer always official
    feed = client.get(f"/shelters/{s['id']}/updates").json()["records"]
    assert feed[0]["message"] == "Casi lleno"
    # occupancy_delta nudged the shelter
    assert client.get(f"/shelters/{s['id']}").json()["occupancy"] == 15


def test_expired_updates_hidden_by_default(client):
    s = _make_shelter(client)
    client.post(f"/shelters/{s['id']}/updates", json={"message": "vieja", "expires_at": "2000-01-01T00:00:00Z"})
    assert client.get(f"/shelters/{s['id']}/updates").json()["records"] == []
    assert len(client.get(f"/shelters/{s['id']}/updates?include_expired=true").json()["records"]) == 1


def test_capacity_patch_is_partial(client):
    s = _make_shelter(client, capacity_available=30, beds_available=20)
    r = client.patch(f"/shelters/{s['id']}/capacity", json={"capacity_available": 5, "accepting_new": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["capacity_available"] == 5
    assert body["accepting_new"] is False
    assert body["beds_available"] == 20  # untouched


def test_checkin_and_family_alias_search(client):
    s = _make_shelter(client, name="Refugio Cancha")
    assert client.post(f"/shelters/{s['id']}/checkin", json={"alias": "Juan Perez", "note": "con familia"}).status_code == 200
    res = client.get("/shelters/checkins/search?alias=juan").json()["records"]
    assert len(res) == 1
    assert res[0]["shelter_name"] == "Refugio Cancha"


def test_stale_upsert_does_not_clobber(client):
    s = _make_shelter(client, name="Nuevo")
    sid = s["id"]
    # Re-upsert with an OLDER updatedAt and a different name: should be ignored.
    client.post("/shelters", json={"id": sid, "name": "Viejo", "updatedAt": "2000-01-01T00:00:00Z"})
    assert client.get(f"/shelters/{sid}").json()["name"] == "Nuevo"


def test_token_claim_grants_official_posting(client):
    # Create a viewer user; once users exist the dev bypass is gone.
    from modules import users, shelters
    from models import ShelterTokenCreate

    s = _make_shelter(client, name="Refugio Token")
    sid = s["id"]
    user = users.create_user("op20@egi.local", "pw-secret-123", role="viewer", name="Op20")
    tok = shelters.issue_token(sid, ShelterTokenCreate(label="x"), "test:commander")["token"]

    login = client.post("/auth/login", json={"email": "op20@egi.local", "password": "pw-secret-123"})
    bearer = login.json()["token"]
    hdr = {"Authorization": "Bearer " + bearer}

    # Before claiming, a viewer is not operator-of and cannot post.
    assert client.post(f"/shelters/{sid}/updates", json={"message": "no"}, headers=hdr).status_code == 403
    # Claim, then the same viewer can post official updates.
    claimed = client.post("/shelters/claim", json={"token": tok}, headers=hdr)
    assert claimed.status_code == 200
    assert claimed.json()["trust"] == "official"
    ok = client.post(f"/shelters/{sid}/updates", json={"message": "abierto"}, headers=hdr)
    assert ok.status_code == 200 and ok.json()["author_role"] == "official"
    # Anonymous is blocked now that users exist.
    assert client.post(f"/shelters/{sid}/updates", json={"message": "spam"}).status_code == 401


def test_claim_rejects_bad_token(client):
    from modules import users

    users.create_user("op21@egi.local", "pw-secret-123", role="viewer", name="Op21")
    bearer = client.post("/auth/login", json={"email": "op21@egi.local", "password": "pw-secret-123"}).json()["token"]
    r = client.post("/shelters/claim", json={"token": "not-a-real-token"}, headers={"Authorization": "Bearer " + bearer})
    assert r.status_code == 400
