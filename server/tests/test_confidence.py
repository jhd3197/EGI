# Confidence-based derived status. TEST DATA — NOT REAL.


def _person(**overrides):
    base = {
        "id": "egi-conf-1",
        "name": "Carlos Ruiz de prueba",
        "status": "missing",
        "disaster_id": "d-test",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def _report(pid, **overrides):
    base = {
        "person_id": pid,
        "note": "obs",
        "createdAt": "2026-01-02T00:00:00Z",
        "updatedAt": "2026-01-02T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_official_safe_beats_stale_missing(client):
    # Stale 'missing' person, but a recent OFFICIAL 'safe' report → displays safe.
    client.post("/sync", json={"records": [_person(status="missing")]})
    client.post("/persons/egi-conf-1/reports", json=_report(
        "egi-conf-1", status="safe", confidence="official",
        updatedAt="2026-03-01T00:00:00Z"))
    person = client.get("/persons/egi-conf-1").json()
    assert person["status"] == "missing"          # stored is untouched
    assert person["derived_status"] == "safe"     # derived reflects the report


def test_higher_confidence_wins_over_newer_lower(client):
    # A newer witness report vs an older self check-in: self outranks witness.
    client.post("/sync", json={"records": [_person(status="missing")]})
    client.post("/persons/egi-conf-1/reports", json=_report(
        "egi-conf-1", status="sighted", confidence="witness",
        updatedAt="2026-05-01T00:00:00Z"))
    client.post("/persons/egi-conf-1/reports", json=_report(
        "egi-conf-1", status="safe", confidence="self",
        updatedAt="2026-04-01T00:00:00Z"))
    assert client.get("/persons/egi-conf-1").json()["derived_status"] == "safe"


def test_within_tier_latest_wins(client):
    # Same confidence tier → the latest updated_at wins.
    client.post("/sync", json={"records": [_person(status="missing")]})
    client.post("/persons/egi-conf-1/reports", json=_report(
        "egi-conf-1", status="sighted", confidence="witness",
        id="r-old", updatedAt="2026-02-01T00:00:00Z"))
    client.post("/persons/egi-conf-1/reports", json=_report(
        "egi-conf-1", status="safe", confidence="witness",
        id="r-new", updatedAt="2026-04-01T00:00:00Z"))
    assert client.get("/persons/egi-conf-1").json()["derived_status"] == "safe"


def test_note_without_status_does_not_change_derived(client):
    client.post("/sync", json={"records": [_person(status="missing")]})
    client.post("/persons/egi-conf-1/reports", json=_report(
        "egi-conf-1", note="solo una nota", confidence="official"))
    assert client.get("/persons/egi-conf-1").json()["derived_status"] == "missing"


def test_derived_status_in_search(client):
    client.post("/sync", json={"records": [_person(status="missing")]})
    client.post("/persons/egi-conf-1/reports", json=_report(
        "egi-conf-1", status="safe", confidence="official"))
    rec = client.get("/persons", params={"q": "Carlos"}).json()["records"][0]
    assert rec["derived_status"] == "safe"


def test_invalid_confidence_rejected(client):
    client.post("/sync", json={"records": [_person()]})
    res = client.post("/persons/egi-conf-1/reports", json=_report(
        "egi-conf-1", status="safe", confidence="psychic"))
    assert res.status_code == 400
    assert "invalid confidence" in res.json()["detail"]
