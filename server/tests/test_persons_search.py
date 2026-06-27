# Soft-normalized cedula search + cursor pagination for /persons.
# TEST DATA — NOT REAL.
from modules.persons import normalize_cedula


def _person(**overrides):
    base = {
        "id": "egi-test-0001",
        "name": "Juan Pérez de prueba",
        "status": "missing",
        "disaster_id": "d-test",
        "location": "Refugio de prueba",
        "cedula": "V-26.345.789",
        "source": "web",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_normalize_cedula_unit():
    assert normalize_cedula("V-26.345.789") == "26345789"
    assert normalize_cedula("26.345.789") == "26345789"
    assert normalize_cedula("26345789") == "26345789"
    assert normalize_cedula("E-12 345") == "12345"
    assert normalize_cedula("") == ""


def test_cedula_search_finds_normalized(client):
    client.post("/sync", json={"records": [_person()]})
    # Bare digits should find the dotted/prefixed stored cedula.
    res = client.get("/persons", params={"cedula": "26345789"})
    ids = [r["id"] for r in res.json()["records"]]
    assert ids == ["egi-test-0001"]


def test_cedula_search_exact_still_works(client):
    client.post("/sync", json={"records": [_person()]})
    res = client.get("/persons", params={"cedula": "V-26.345.789"})
    assert len(res.json()["records"]) == 1


def test_cedula_search_no_false_match(client):
    client.post("/sync", json={"records": [_person()]})
    res = client.get("/persons", params={"cedula": "99999999"})
    assert res.json()["records"] == []


def test_pagination_cursor_walks_all_records(client):
    recs = [
        _person(
            id=f"egi-test-{i:04d}",
            cedula=f"V-{i:08d}",
            updatedAt=f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
        )
        for i in range(10)
    ]
    client.post("/sync", json={"records": recs})

    seen = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 3}
        if cursor:
            params["cursor"] = cursor
        body = client.get("/persons", params=params).json()
        seen.extend(r["id"] for r in body["records"])
        pages += 1
        if not body["has_more"]:
            assert body["next_cursor"] is None
            break
        cursor = body["next_cursor"]
        assert cursor
        assert pages < 20  # guard against an infinite loop

    # Every record returned exactly once across pages.
    assert len(seen) == 10
    assert len(set(seen)) == 10


def test_pagination_response_shape(client):
    client.post("/sync", json={"records": [_person()]})
    body = client.get("/persons").json()
    assert "records" in body
    assert "has_more" in body
    assert "next_cursor" in body
    assert body["has_more"] is False
