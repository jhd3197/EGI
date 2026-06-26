# Moderation queue: pending list, approve/reject, public-search trust gate,
# and stats. All fixtures are obviously fake. TEST DATA — NOT REAL.


def _import_record(client, **overrides):
    """Push a single untrusted record through /sync (source set by the caller)."""
    base = {
        "id": "egi-imp-0001",
        "name": "Registro importado de prueba",
        "status": "missing",
        "source": "pfif_import",
        "reviewed": 0,
        "cedula": "V-00000123",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    res = client.post("/sync", json={"records": [base]})
    assert res.status_code == 200
    return base["id"]


def test_untrusted_record_hidden_from_public_search_until_approved(client):
    rec_id = _import_record(client)

    # Hidden from public search while pending.
    found = [r["id"] for r in client.get("/persons").json()["records"]]
    assert rec_id not in found

    # But present in the moderation queue.
    pending = [r["id"] for r in client.get("/moderation/pending").json()["records"]]
    assert rec_id in pending

    # Approve it -> now visible in public search, gone from the queue.
    res = client.post(f"/moderation/{rec_id}/approve")
    assert res.status_code == 200 and res.json()["reviewed"] == 1

    found = [r["id"] for r in client.get("/persons").json()["records"]]
    assert rec_id in found
    pending = [r["id"] for r in client.get("/moderation/pending").json()["records"]]
    assert rec_id not in pending


def test_reject_soft_deletes_and_hides(client):
    rec_id = _import_record(client, id="egi-imp-rej")
    res = client.post(f"/moderation/{rec_id}/reject")
    assert res.status_code == 200 and res.json()["reviewed"] == -1

    # Rejected: hidden from public search and no longer pending.
    found = [r["id"] for r in client.get("/persons").json()["records"]]
    assert rec_id not in found
    pending = [r["id"] for r in client.get("/moderation/pending").json()["records"]]
    assert rec_id not in pending


def test_trusted_web_record_stays_visible(client):
    # A normal web report (source defaults to 'web') is trusted and must remain
    # visible in public search even though reviewed defaults to 0.
    client.post("/sync", json={"records": [{
        "id": "egi-web-0001", "name": "Reporte web de prueba", "status": "safe",
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    found = [r["id"] for r in client.get("/persons").json()["records"]]
    assert "egi-web-0001" in found


def test_normalize_creates_pending_ai_draft(client):
    res = client.post("/normalize", json={"text": "Busco a mi prima, vista en Caracas"})
    assert res.status_code == 200
    body = res.json()
    assert body["person"]["source"] == "ai_draft"
    assert body["person"]["reviewed"] == 0
    rec_id = body["person"]["id"]

    pending = [r["id"] for r in client.get("/moderation/pending").json()["records"]]
    assert rec_id in pending
    # And not yet in public search.
    found = [r["id"] for r in client.get("/persons").json()["records"]]
    assert rec_id not in found


def test_moderation_stats(client):
    _import_record(client, id="egi-imp-a")
    _import_record(client, id="egi-imp-b")
    client.post("/moderation/egi-imp-a/approve")

    stats = client.get("/moderation/stats").json()
    assert stats["by_source"].get("pfif_import") == 2
    assert stats["approved"] >= 1
    assert stats["pending"] >= 1


def test_approve_reject_unknown_404(client):
    assert client.post("/moderation/nope/approve").status_code == 404
    assert client.post("/moderation/nope/reject").status_code == 404
