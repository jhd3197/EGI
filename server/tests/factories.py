# Shared record factories for the EGI server test suite.
#
# Importable from any test file with a bare ``from factories import ...`` —
# pytest puts the tests/ dir on sys.path (no __init__.py here, prepend import
# mode), the same way conftest.py is discovered.
#
# TEST DATA — NOT REAL. All names/cedulas are obviously fake.


def person_record(**overrides):
    """A minimal valid person record for /sync with obviously-fake defaults.

    Matches the canonical shape used across the sync/persons tests; pass
    overrides for any field a given test cares about.
    """
    base = {
        "id": "egi-test-0001",
        "name": "Juan Pérez de prueba",
        "status": "missing",
        "disaster_id": "d-test",
        "location": "Refugio de prueba",
        "cedula": "V-00000000",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def sync_person(client, **overrides):
    """POST a person via /sync and return the record dict that was sent."""
    rec = person_record(**overrides)
    res = client.post("/sync", json={"records": [rec]})
    assert res.status_code == 200, res.text
    return rec


def create_operation(client, **overrides):
    """Create an operation via POST /operations and return the JSON body."""
    body = {"name": "Operación Prueba"}
    body.update(overrides)
    res = client.post("/operations", json=body)
    assert res.status_code == 200, res.text
    return res.json()
