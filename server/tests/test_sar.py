"""Tests for the Search & Rescue operations workflow (plan-26).

Covers the operation data model + CRUD (Phase 1), sector claim conflict +
check-in/out + the task checklist (Phase 3), field reports and the found→registry
update behind the operator gate (Phase 4 + Phase 6), and the mesh/cloud sync LWW.
All data is fake (see docs/TESTING.md).
"""


def _make_person(client, pid="person-sar-1", status="missing"):
    body = {"records": [{"id": pid, "name": "Ana Test", "status": status}]}
    r = client.post("/sync", json=body)
    assert r.status_code == 200, r.text


def _create_op(client, **over):
    payload = {
        "name": "Búsqueda La Guaira 3",
        "disaster_id": "venezuela-2026",
        "zone_lat": 10.6,
        "zone_lon": -66.85,
        "zone_radius_m": 1500,
        "auto_grid": 3,
    }
    payload.update(over)
    r = client.post("/sar/operations", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ── Phase 1: data model + CRUD ────────────────────────────────────────────────


def test_create_operation_auto_grid_and_persons(client):
    _make_person(client)
    op = _create_op(client, person_ids=["person-sar-1"])
    assert op["status"] == "active"
    assert op["stats"]["sectors_total"] == 9  # 3x3 grid
    assert op["stats"]["persons_total"] == 1
    # sectors are labelled A1..C3
    names = {s["name"] for s in op["sectors"]}
    assert "A1" in names and "C3" in names


def test_create_operation_manual_sectors(client):
    op = _create_op(client, auto_grid=None, zone_lat=None, zone_lon=None,
                    sectors=[{"name": "North"}, {"name": "South"}])
    assert op["stats"]["sectors_total"] == 2


def test_list_and_get_operation(client):
    op = _create_op(client)
    r = client.get("/sar/operations?disaster_id=venezuela-2026")
    assert r.status_code == 200
    recs = r.json()["records"]
    assert len(recs) == 1
    assert recs[0]["sector_count"] == 9
    r = client.get(f"/sar/operations/{op['id']}")
    assert r.status_code == 200
    assert "sectors" in r.json() and "stats" in r.json()


def test_get_missing_operation_404(client):
    assert client.get("/sar/operations/nope").status_code == 404


def test_status_transitions_and_validation(client):
    op = _create_op(client)
    oid = op["id"]
    r = client.patch(f"/sar/operations/{oid}/status", json={"status": "paused"})
    assert r.json()["status"] == "paused"
    r = client.patch(f"/sar/operations/{oid}/status", json={"status": "closed", "reason": "found"})
    assert r.json()["status"] == "closed"
    assert r.json()["closed_reason"] == "found"
    # invalid status rejected by the model
    assert client.patch(f"/sar/operations/{oid}/status", json={"status": "bogus"}).status_code == 422


# ── Phase 3: sectors, volunteers, tasks ───────────────────────────────────────


def test_sector_claim_conflict(client):
    op = _create_op(client)
    sec = op["sectors"][0]["id"]
    v1 = client.post(f"/sar/operations/{op['id']}/join", json={"alias": "V1", "device_id": "d1"}).json()
    v2 = client.post(f"/sar/operations/{op['id']}/join", json={"alias": "V2", "device_id": "d2"}).json()
    r = client.post(f"/sar/sectors/{sec}/claim", json={"alias": "V1", "volunteer_id": v1["id"]})
    assert r.status_code == 200 and r.json()["status"] == "assigned"
    # second volunteer cannot claim the same active sector
    r = client.post(f"/sar/sectors/{sec}/claim", json={"alias": "V2", "volunteer_id": v2["id"]})
    assert r.status_code == 409
    # release frees it
    assert client.post(f"/sar/sectors/{sec}/release").json()["status"] == "unassigned"
    r = client.post(f"/sar/sectors/{sec}/claim", json={"alias": "V2", "volunteer_id": v2["id"]})
    assert r.status_code == 200


def test_join_is_idempotent(client):
    op = _create_op(client)
    a = client.post(f"/sar/operations/{op['id']}/join", json={"alias": "V", "device_id": "dd"}).json()
    b = client.post(f"/sar/operations/{op['id']}/join", json={"alias": "V", "device_id": "dd"}).json()
    assert a["id"] == b["id"]


def test_checkin_checkout(client):
    op = _create_op(client)
    sec = op["sectors"][0]["id"]
    v = client.post(f"/sar/operations/{op['id']}/join", json={"alias": "V", "device_id": "d"}).json()
    r = client.post(f"/sar/sectors/{sec}/checkin", json={"volunteer_id": v["id"]})
    assert r.json()["status"] == "in_progress"
    r = client.post(f"/sar/volunteers/{v['id']}/checkout")
    assert r.json()["status"] == "checked_out"


def test_task_checklist(client):
    op = _create_op(client)
    t = client.post(f"/sar/operations/{op['id']}/tasks",
                    json={"title": "Ask neighbors", "kind": "ask_neighbors"}).json()
    assert t["done"] == 0
    r = client.patch(f"/sar/tasks/{t['id']}", json={"done": True, "completed_by": "V"})
    assert r.json()["done"] == 1 and r.json()["completed_at"]
    assert client.delete(f"/sar/tasks/{t['id']}").json()["deleted"] is True


# ── Phase 4 + 6: field reports + found→registry behind the operator gate ──────


def test_sighting_flags_sector_needs_recheck(client):
    op = _create_op(client)
    sec = op["sectors"][0]["id"]
    client.post(f"/sar/operations/{op['id']}/field-reports",
                json={"type": "sighting", "sector_id": sec, "note": "saw someone"})
    detail = client.get(f"/sar/operations/{op['id']}").json()
    s = [x for x in detail["sectors"] if x["id"] == sec][0]
    assert s["status"] == "needs_recheck"


def test_found_report_requires_confirmation_to_update_registry(client):
    _make_person(client, pid="person-found", status="missing")
    op = _create_op(client, person_ids=["person-found"])
    fr = client.post(f"/sar/operations/{op['id']}/field-reports",
                     json={"type": "found", "person_id": "person-found", "note": "located"}).json()
    assert fr["reviewed"] == 0 and fr["applied"] == 0
    # person is still missing until a verified confirmation
    p = client.get("/persons/person-found").json()
    assert p["status"] == "missing"
    # confirm (operator-gated; no users configured → dev bypass) applies the update
    r = client.post(f"/sar/field-reports/{fr['id']}/resolve", json={"confirmed": True})
    assert r.status_code == 200 and r.json()["applied"] == 1
    p = client.get("/persons/person-found").json()
    assert p["status"] == "found"


def test_found_report_dismiss_does_not_update_registry(client):
    _make_person(client, pid="person-dismiss", status="missing")
    op = _create_op(client, person_ids=["person-dismiss"])
    fr = client.post(f"/sar/operations/{op['id']}/field-reports",
                     json={"type": "found", "person_id": "person-dismiss"}).json()
    r = client.post(f"/sar/field-reports/{fr['id']}/resolve", json={"confirmed": False})
    assert r.json()["reviewed"] == -1 and r.json()["applied"] == 0
    assert client.get("/persons/person-dismiss").json()["status"] == "missing"


def test_sync_download_upload_lww(client):
    op = _create_op(client)
    sec = op["sectors"][0]["id"]
    dl = client.get("/sar/sync").json()
    assert len(dl["operations"]) == 1 and len(dl["sectors"]) == 9
    up = client.post("/sar/sync", json={"field_reports": [
        {"id": "fr-mesh-1", "operation_id": op["id"], "type": "cleared", "sector_id": sec, "note": "mesh"}
    ]})
    assert up.json()["saved"] == 1
    # a stale re-send (older updatedAt) is skipped
    up2 = client.post("/sar/sync", json={"field_reports": [
        {"id": "fr-mesh-1", "operation_id": op["id"], "type": "cleared", "updatedAt": "2000-01-01T00:00:00Z"}
    ]})
    assert up2.json()["skipped"] == 1
