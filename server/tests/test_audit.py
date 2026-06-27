# Audit logging: record_history creation trail + recoverable moderator actions.
# TEST DATA — NOT REAL.

from modules import audit


def _new_record(client, rec_id, **over):
    base = {
        "id": rec_id, "name": "Registro de prueba", "status": "missing",
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }
    base.update(over)
    client.post("/sync", json={"records": [base]})


def test_sync_creation_is_recorded_once(client):
    _new_record(client, "egi-hist-1")
    hist = audit.list_history("egi-hist-1")
    creates = [h for h in hist if h["change"] == "create"]
    assert len(creates) == 1
    assert creates[0]["actor"] == "sync"

    # Re-syncing a newer update of the same id does NOT add another 'create'.
    _new_record(client, "egi-hist-1", updatedAt="2026-02-01T00:00:00Z")
    creates = [h for h in audit.list_history("egi-hist-1") if h["change"] == "create"]
    assert len(creates) == 1


def test_moderation_action_recoverable_from_audit(client):
    _new_record(client, "egi-hist-2", source="pfif_import", reviewed=0)
    client.post("/moderation/egi-hist-2/reject")
    actions = audit.list_actions()
    rejects = [a for a in actions if a["action"] == "reject" and a["target_id"] == "egi-hist-2"]
    assert rejects
    # Logs never contain a full token (actor is a short principal or 'sync').
    assert all("Bearer" not in (a["actor"] or "") for a in actions)
