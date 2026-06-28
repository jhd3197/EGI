# /sync upload+download round-trip, /persons filters, and conflict resolution.
# TEST DATA — NOT REAL.

from factories import person_record as _person


def test_sync_upload_download_roundtrip(client):
    rec = _person()
    res = client.post("/sync", json={"records": [rec]})
    assert res.status_code == 200
    body = res.json()
    assert body["saved"] == 1
    assert body["skipped"] == 0

    # Download everything since epoch should return the uploaded record.
    got = client.get("/sync", params={"since": "1970-01-01T00:00:00Z"})
    assert got.status_code == 200
    records = got.json()["records"]
    assert len(records) == 1
    assert records[0]["id"] == "egi-test-0001"
    assert records[0]["name"] == "Juan Pérez de prueba"


def test_sync_download_since_filter(client):
    client.post("/sync", json={"records": [
        _person(id="egi-test-old", updatedAt="2026-01-01T00:00:00Z"),
        _person(id="egi-test-new", updatedAt="2026-03-01T00:00:00Z"),
    ]})
    got = client.get("/sync", params={"since": "2026-02-01T00:00:00Z"})
    ids = [r["id"] for r in got.json()["records"]]
    assert ids == ["egi-test-new"]


def test_sync_requires_record_id(client):
    res = client.post("/sync", json={"records": [_person(id=None)]})
    assert res.status_code == 400


def test_sync_rejects_invalid_status(client):
    res = client.post("/sync", json={"records": [_person(status="kidnapped")]})
    assert res.status_code == 400
    assert "invalid status" in res.json()["detail"]


def test_conflict_newer_timestamp_wins(client):
    client.post("/sync", json={"records": [
        _person(name="Versión vieja", updatedAt="2026-01-01T00:00:00Z"),
    ]})
    # Newer update for the same id must overwrite.
    res = client.post("/sync", json={"records": [
        _person(name="Versión nueva", updatedAt="2026-02-01T00:00:00Z"),
    ]})
    assert res.json()["saved"] == 1
    assert res.json()["skipped"] == 0

    got = client.get("/persons", params={"q": "Versión"})
    records = got.json()["records"]
    assert len(records) == 1
    assert records[0]["name"] == "Versión nueva"


def test_conflict_stale_write_is_skipped(client):
    client.post("/sync", json={"records": [
        _person(name="Versión nueva", updatedAt="2026-02-01T00:00:00Z"),
    ]})
    # A stale relay arriving out of order must NOT clobber the newer copy.
    res = client.post("/sync", json={"records": [
        _person(name="Versión vieja", updatedAt="2026-01-01T00:00:00Z"),
    ]})
    assert res.json()["saved"] == 0
    assert res.json()["skipped"] == 1

    person = client.get("/persons/egi-test-0001").json()
    assert person["name"] == "Versión nueva"


def test_persons_filters(client):
    client.post("/sync", json={"records": [
        _person(id="p-miss", name="Desaparecido Uno", status="missing",
                location="Valencia", disaster_id="d-1", cedula="V-11111111"),
        _person(id="p-safe", name="A Salvo Dos", status="safe",
                location="Caracas", disaster_id="d-2", cedula="V-22222222"),
    ]})

    # status filter
    ids = [r["id"] for r in client.get("/persons", params={"status": "safe"}).json()["records"]]
    assert ids == ["p-safe"]

    # location LIKE filter
    ids = [r["id"] for r in client.get("/persons", params={"location": "Valen"}).json()["records"]]
    assert ids == ["p-miss"]

    # disaster_id filter
    ids = [r["id"] for r in client.get("/persons", params={"disaster_id": "d-2"}).json()["records"]]
    assert ids == ["p-safe"]

    # cedula exact filter
    ids = [r["id"] for r in client.get("/persons", params={"cedula": "V-11111111"}).json()["records"]]
    assert ids == ["p-miss"]

    # free-text q across name
    ids = [r["id"] for r in client.get("/persons", params={"q": "Salvo"}).json()["records"]]
    assert ids == ["p-safe"]


def test_persons_since_filter(client):
    client.post("/sync", json={"records": [
        _person(id="p-old", updatedAt="2026-01-01T00:00:00Z"),
        _person(id="p-new", updatedAt="2026-05-01T00:00:00Z"),
    ]})
    ids = [r["id"] for r in client.get(
        "/persons", params={"since": "2026-03-01T00:00:00Z"}
    ).json()["records"]]
    assert ids == ["p-new"]


def test_get_person_404(client):
    assert client.get("/persons/does-not-exist").status_code == 404


def test_sync_reports_roundtrip(client):
    # A report attached via the sync payload should upsert and be retrievable.
    client.post("/sync", json={"records": [_person()]})
    res = client.post("/sync", json={
        "records": [],
        "reports": [{
            "id": "egi-report-0001",
            "person_id": "egi-test-0001",
            "author_name": "Reportero de prueba",
            "note": "Visto cerca del refugio",
            "status": "sighted",
            "createdAt": "2026-01-02T00:00:00Z",
            "updatedAt": "2026-01-02T00:00:00Z",
        }],
    })
    assert res.json()["reports"] == 1
    reports = client.get("/persons/egi-test-0001/reports").json()["records"]
    assert len(reports) == 1
    assert reports[0]["note"] == "Visto cerca del refugio"


def test_sync_download_includes_reports(client):
    # A device that only ever reaches the cloud (never the mesh) must still
    # receive reports via GET /sync, alongside persons.
    client.post("/sync", json={"records": [_person()]})
    client.post("/sync", json={
        "records": [],
        "reports": [{
            "id": "egi-report-dl",
            "person_id": "egi-test-0001",
            "author_name": "Reportero de prueba",
            "note": "Nota que viaja por el mesh",
            "status": "safe",
            "createdAt": "2026-01-03T00:00:00Z",
            "updatedAt": "2026-01-03T00:00:00Z",
        }],
    })
    got = client.get("/sync", params={"since": "1970-01-01T00:00:00Z"}).json()
    assert "reports" in got
    ids = [r["id"] for r in got["reports"]]
    assert "egi-report-dl" in ids


def test_lww_equal_instant_different_offset_not_clobbered(client):
    # The same instant expressed as 'Z' then as '+00:00' must be treated as a tie
    # (ties replace, never "stale skipped"), not misordered by raw text compare.
    client.post("/sync", json={"records": [
        _person(name="Z form", updatedAt="2026-02-01T00:00:00Z"),
    ]})
    res = client.post("/sync", json={"records": [
        _person(name="offset form", updatedAt="2026-02-01T00:00:00+00:00"),
    ]})
    # Equal instant → tie → applied (saved), not skipped as stale.
    assert res.json()["saved"] == 1
    assert res.json()["skipped"] == 0
    person = client.get("/persons/egi-test-0001").json()
    assert person["name"] == "offset form"


def test_lww_offset_older_is_skipped(client):
    # A genuinely older instant in '+00:00' form must still lose to a newer 'Z'.
    client.post("/sync", json={"records": [
        _person(name="nueva", updatedAt="2026-02-01T00:00:00Z"),
    ]})
    res = client.post("/sync", json={"records": [
        _person(name="vieja", updatedAt="2026-01-01T00:00:00+00:00"),
    ]})
    assert res.json()["saved"] == 0
    assert res.json()["skipped"] == 1
    assert client.get("/persons/egi-test-0001").json()["name"] == "nueva"


def test_sync_download_reports_since_filter(client):
    client.post("/sync", json={"records": [_person()]})
    client.post("/sync", json={"records": [], "reports": [
        {"id": "rep-old", "person_id": "egi-test-0001", "note": "vieja",
         "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
        {"id": "rep-new", "person_id": "egi-test-0001", "note": "nueva",
         "createdAt": "2026-03-01T00:00:00Z", "updatedAt": "2026-03-01T00:00:00Z"},
    ]})
    got = client.get("/sync", params={"since": "2026-02-01T00:00:00Z"}).json()
    ids = [r["id"] for r in got["reports"]]
    assert ids == ["rep-new"]
