# Operations, versioned action plans, tasks, and operations-sync (plan-09).
# TEST DATA — NOT REAL. All names/emails are obviously fake.
#
# Covers: operation CRUD + stats + close/reopen, action-plan versioning and
# activation, default task seeding + copy-from-previous, the task state machine,
# RBAC gating across viewer/operator/commander/admin, and /sync/operations.

from modules import action_plans, operations

from factories import create_operation as _create_op
from helpers.auth import bearer as _bearer
from helpers.auth import make_user_with_headers as _make_user


# ── Operation CRUD ───────────────────────────────────────────────────────────

def test_create_operation_defaults_to_open(client):
    op = _create_op(client, region="Sur", utm_x=1.5, utm_y=2.5)
    assert op["id"].startswith("egi-event-")
    assert op["status"] == "open"
    assert op["started_at"]
    assert op["utm_x"] == 1.5


def test_create_operation_rejects_bad_status(client):
    res = client.post("/operations", json={"name": "X", "status": "frozen"})
    assert res.status_code == 400


def test_get_operation_includes_person_stats(client):
    op = _create_op(client)
    # Two persons attached to this operation via disaster_id.
    client.post("/sync", json={"records": [
        {"id": "p-op-1", "name": "Ana", "status": "missing", "disaster_id": op["id"],
         "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
        {"id": "p-op-2", "name": "Beto", "status": "found", "disaster_id": op["id"],
         "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
    ]})
    res = client.get(f"/operations/{op['id']}")
    assert res.status_code == 200
    stats = res.json()["stats"]
    assert stats["persons_total"] == 2
    assert stats["persons_by_status"]["missing"] == 1


def test_get_operation_404(client):
    assert client.get("/operations/nope").status_code == 404


def test_patch_operation_updates_fields(client):
    op = _create_op(client)
    res = client.patch(f"/operations/{op['id']}", json={"municipality": "Valle", "contact_phone": "555"})
    assert res.status_code == 200
    assert res.json()["municipality"] == "Valle"
    assert res.json()["contact_phone"] == "555"


def test_list_operations_filters(client):
    _create_op(client, region="Norte")
    _create_op(client, region="Sur", is_practice=1)
    assert len(client.get("/operations").json()["records"]) == 2
    assert len(client.get("/operations", params={"region": "Norte"}).json()["records"]) == 1
    assert len(client.get("/operations", params={"is_practice": 1}).json()["records"]) == 1


def test_close_and_reopen_operation(client):
    op = _create_op(client)
    res = client.post(f"/operations/{op['id']}/close", json={"reason": "encontrado"})
    assert res.status_code == 200
    assert res.json()["status"] == "closed"
    assert res.json()["closed_reason"] == "encontrado"
    assert res.json()["closed_at"]
    res = client.post(f"/operations/{op['id']}/reopen")
    assert res.json()["status"] == "open"
    assert res.json()["closed_at"] is None


def test_legacy_events_upsert_preserves_operational_columns(client):
    op = _create_op(client, utm_x=9.9)
    # A legacy /events upsert must not wipe plan-09 columns.
    res = client.post("/events", json={"id": op["id"], "name": "renombrada", "status": "open"})
    assert res.status_code == 200
    got = client.get(f"/operations/{op['id']}").json()
    assert got["utm_x"] == 9.9
    assert got["name"] == "renombrada"


# ── Action plan versioning + activation ──────────────────────────────────────

def test_first_plan_is_active_second_is_not(client):
    op = _create_op(client)
    p1 = client.post(f"/operations/{op['id']}/action-plans", json={"description": "v1"}).json()
    assert p1["version"] == 1 and p1["is_active"] == 1
    p2 = client.post(f"/operations/{op['id']}/action-plans", json={"description": "v2"}).json()
    assert p2["version"] == 2 and p2["is_active"] == 0


def test_activate_switches_active_plan(client):
    op = _create_op(client)
    p1 = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    p2 = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    client.post(f"/action-plans/{p2['id']}/activate")
    plans = {p["id"]: p["is_active"] for p in client.get(f"/operations/{op['id']}/action-plans").json()["records"]}
    assert plans[p1["id"]] == 0 and plans[p2["id"]] == 1


def test_create_plan_seeds_default_tasks(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    tasks = client.get(f"/action-plans/{p['id']}/tasks").json()["records"]
    assert len(tasks) == 6  # default templates
    assert all(t["state"] == "pending" for t in tasks)


def test_create_plan_without_seed(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={"seed_defaults": False}).json()
    assert client.get(f"/action-plans/{p['id']}/tasks").json()["records"] == []


def test_copy_from_previous_copies_tasks(client):
    op = _create_op(client)
    p1 = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    # Mark one task done in v1; the copy should reset it to pending.
    t = client.get(f"/action-plans/{p1['id']}/tasks").json()["records"][0]
    client.patch(f"/tasks/{t['id']}", json={"state": "done"})
    p2 = client.post(f"/operations/{op['id']}/action-plans", json={"copy_from_previous": True}).json()
    copied = client.get(f"/action-plans/{p2['id']}/tasks").json()["records"]
    assert len(copied) == 6
    assert all(c["state"] == "pending" for c in copied)


def test_update_plan_description(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    res = client.patch(f"/action-plans/{p['id']}", json={"description": "actualizado"})
    assert res.json()["description"] == "actualizado"


def test_delete_active_plan_is_rejected(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    assert p["is_active"] == 1
    # admin bypass via dev (no users); the 409 is about being active, not RBAC.
    res = client.delete(f"/action-plans/{p['id']}")
    assert res.status_code == 409


def test_delete_inactive_plan_soft_deletes(client):
    op = _create_op(client)
    client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    p2 = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    assert p2["is_active"] == 0
    assert client.delete(f"/action-plans/{p2['id']}").status_code == 200
    ids = [p["id"] for p in client.get(f"/operations/{op['id']}/action-plans").json()["records"]]
    assert p2["id"] not in ids
    # Version numbers still advance past the deleted version (UNIQUE preserved).
    p3 = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    assert p3["version"] == 3


# ── Task state machine ───────────────────────────────────────────────────────

def test_task_done_stamps_completion_and_revert_clears(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    t = client.get(f"/action-plans/{p['id']}/tasks").json()["records"][0]
    done = client.patch(f"/tasks/{t['id']}", json={"state": "done"}).json()
    assert done["state"] == "done" and done["completed_at"] and done["completed_by"]
    reverted = client.patch(f"/tasks/{t['id']}", json={"state": "in_progress"}).json()
    assert reverted["completed_at"] is None and reverted["completed_by"] is None


def test_task_invalid_state_rejected(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    t = client.get(f"/action-plans/{p['id']}/tasks").json()["records"][0]
    assert client.patch(f"/tasks/{t['id']}", json={"state": "wat"}).status_code == 400


def test_create_and_delete_task(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={"seed_defaults": False}).json()
    res = client.post(f"/action-plans/{p['id']}/tasks", json={"title": "Nueva tarea"})
    assert res.status_code == 200
    tid = res.json()["id"]
    assert len(client.get(f"/action-plans/{p['id']}/tasks").json()["records"]) == 1
    assert client.delete(f"/tasks/{tid}").status_code == 200
    assert client.get(f"/action-plans/{p['id']}/tasks").json()["records"] == []


def test_create_task_requires_title(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={"seed_defaults": False}).json()
    assert client.post(f"/action-plans/{p['id']}/tasks", json={}).status_code == 400


# ── RBAC gating (real user accounts) ─────────────────────────────────────────

def test_viewer_cannot_create_operation(client):
    _, vh = _make_user("viewer@example.test", "viewer")
    res = client.post("/operations", json={"name": "X"}, headers=vh)
    assert res.status_code == 403


def test_operator_cannot_create_operation_commander_can(client):
    _, oh = _make_user("op@example.test", "operator")
    _, ch = _make_user("cmd@example.test", "commander")
    assert client.post("/operations", json={"name": "X"}, headers=oh).status_code == 403
    assert client.post("/operations", json={"name": "Y"}, headers=ch).status_code == 200


def test_operator_cannot_create_plan_commander_can(client):
    _, oh = _make_user("op2@example.test", "operator")
    _, ch = _make_user("cmd2@example.test", "commander")
    op = client.post("/operations", json={"name": "Op"}, headers=ch).json()
    assert client.post(f"/operations/{op['id']}/action-plans", json={}, headers=oh).status_code == 403
    assert client.post(f"/operations/{op['id']}/action-plans", json={}, headers=ch).status_code == 200


def test_delete_plan_requires_admin(client):
    _, ch = _make_user("cmd3@example.test", "commander")
    _, ah = _make_user("admin3@example.test", "admin")
    op = client.post("/operations", json={"name": "Op"}, headers=ch).json()
    client.post(f"/operations/{op['id']}/action-plans", json={}, headers=ch)  # v1 active
    p2 = client.post(f"/operations/{op['id']}/action-plans", json={}, headers=ch).json()
    assert client.delete(f"/action-plans/{p2['id']}", headers=ch).status_code == 403
    assert client.delete(f"/action-plans/{p2['id']}", headers=ah).status_code == 200


def test_operator_only_updates_own_task(client):
    opA, ahdr = _make_user("opa@example.test", "operator")
    _, bhdr = _make_user("opb@example.test", "operator")
    _, chdr = _make_user("cmd4@example.test", "commander")
    op = client.post("/operations", json={"name": "Op"}, headers=chdr).json()
    p = client.post(f"/operations/{op['id']}/action-plans", json={"seed_defaults": False}, headers=chdr).json()
    # Commander creates a task assigned to operator A.
    t = client.post(f"/action-plans/{p['id']}/tasks",
                    json={"title": "Tarea A", "assignee_id": opA["id"]}, headers=chdr).json()
    # Operator B (not assignee) is forbidden; operator A is allowed.
    assert client.patch(f"/tasks/{t['id']}", json={"state": "done"}, headers=bhdr).status_code == 403
    assert client.patch(f"/tasks/{t['id']}", json={"state": "done"}, headers=ahdr).status_code == 200


def test_operator_cannot_reassign_task(client):
    opA, ahdr = _make_user("opa2@example.test", "operator")
    opB, _ = _make_user("opb2@example.test", "operator")
    _, chdr = _make_user("cmd5@example.test", "commander")
    op = client.post("/operations", json={"name": "Op"}, headers=chdr).json()
    p = client.post(f"/operations/{op['id']}/action-plans", json={"seed_defaults": False}, headers=chdr).json()
    t = client.post(f"/action-plans/{p['id']}/tasks",
                    json={"title": "T", "assignee_id": opA["id"]}, headers=chdr).json()
    # Operator A owns the task but reassigning to B requires commander.
    res = client.patch(f"/tasks/{t['id']}", json={"assignee_id": opB["id"]}, headers=ahdr)
    assert res.status_code == 403


# ── /sync/operations ─────────────────────────────────────────────────────────

def test_sync_operations_download(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    d = client.get("/sync/operations").json()
    assert any(o["id"] == op["id"] for o in d["operations"])
    assert any(pl["id"] == p["id"] for pl in d["action_plans"])
    assert len(d["tasks"]) == 6


def test_sync_operations_upload_lww(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    t = client.get(f"/action-plans/{p['id']}/tasks").json()["records"][0]
    # Newer field change applies.
    res = client.post("/sync/operations", json={"tasks": [
        {"id": t["id"], "state": "in_progress", "notes": "desde el campo",
         "updatedAt": "2099-01-01T00:00:00Z"}]})
    assert res.json() == {"saved": 1, "skipped": 0}
    cur = [x for x in client.get(f"/action-plans/{p['id']}/tasks").json()["records"] if x["id"] == t["id"]][0]
    assert cur["state"] == "in_progress" and cur["notes"] == "desde el campo"
    # Stale change is skipped.
    res = client.post("/sync/operations", json={"tasks": [
        {"id": t["id"], "state": "pending", "updatedAt": "2000-01-01T00:00:00Z"}]})
    assert res.json() == {"saved": 0, "skipped": 1}
    # Unknown id is skipped, not an error.
    res = client.post("/sync/operations", json={"tasks": [
        {"id": "ghost", "state": "done", "updatedAt": "2099-01-01T00:00:00Z"}]})
    assert res.json() == {"saved": 0, "skipped": 1}


def test_sync_operations_upload_rejects_bad_state(client):
    op = _create_op(client)
    p = client.post(f"/operations/{op['id']}/action-plans", json={}).json()
    t = client.get(f"/action-plans/{p['id']}/tasks").json()["records"][0]
    res = client.post("/sync/operations", json={"tasks": [
        {"id": t["id"], "state": "bogus", "updatedAt": "2099-01-01T00:00:00Z"}]})
    assert res.status_code == 400


# ── module-level versioning sanity (no HTTP) ─────────────────────────────────

def test_module_create_operation_and_plan(temp_db):
    from models import ActionPlanCreate, OperationCreate
    op = operations.create_operation(OperationCreate(name="Modulo"), actor="user:test")
    plan = action_plans.create_plan(op["id"], ActionPlanCreate(), actor="user:test")
    assert plan["version"] == 1 and plan["is_active"] == 1
    tasks = action_plans.list_tasks(plan["id"])["records"]
    assert len(tasks) == 6
