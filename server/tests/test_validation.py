# Input validation + sanitization (plan-07 Phase 9). TEST DATA — NOT REAL.

import db
from validators import strip_html, clean_text


def test_strip_html_removes_tags_keeps_comparisons():
    assert strip_html("<script>alert(1)</script>hola") == "alert(1)hola"
    assert strip_html("<b>x</b>") == "x"
    assert strip_html("edad < 3 y > 1") == "edad < 3 y > 1"  # stray <,> kept


def test_clean_text_rejects_overlong():
    import pytest
    with pytest.raises(ValueError):
        clean_text("a" * 6000, 5000)


def test_sync_strips_html_in_notes(client):
    client.post("/sync", json={"records": [{
        "id": "egi-xss-1", "name": "<script>bad</script>Ana", "status": "missing",
        "notes": "vista <img src=x onerror=alert(1)> cerca",
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    with db.get_db() as conn:
        row = conn.execute("SELECT name, notes FROM persons WHERE id = ?",
                           ("egi-xss-1",)).fetchone()
    assert "<script>" not in row["name"]
    assert row["name"].endswith("Ana")
    assert "<img" not in row["notes"]


def test_overlong_note_rejected_422(client):
    res = client.post("/sync", json={"records": [{
        "id": "egi-long-1", "name": "X", "status": "safe",
        "notes": "n" * 6000,
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    assert res.status_code == 422


def test_import_paper_rejects_non_image(client):
    res = client.post(
        "/import/paper",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
        data={"run_llm": "false"},
    )
    assert res.status_code == 415


def test_report_note_html_stripped(client):
    client.post("/sync", json={"records": [{
        "id": "egi-rep-host", "name": "Host", "status": "missing",
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    res = client.post("/persons/egi-rep-host/reports", json={
        "note": "<script>x</script>visto", "status": "sighted", "confidence": "witness",
    })
    assert res.status_code == 200
    assert "<script>" not in res.json()["note"]
