# Data retention + anonymization (plan-07 Phase 8). TEST DATA — NOT REAL.

import db
from models import now_iso
from modules import retention


def _insert(rec_id, **cols):
    base = {
        "id": rec_id, "name": "Persona de prueba", "status": "missing",
        "cedula": "V-00000001", "contact": "0414-0000000",
        "source": "web", "reviewed": 1,
        "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z",
    }
    base.update(cols)
    keys = ", ".join(base.keys())
    qs = ", ".join("?" * len(base))
    with db.get_db() as conn:
        conn.execute(f"INSERT INTO persons ({keys}) VALUES ({qs})", list(base.values()))
        conn.commit()


def test_list_past_retention_by_retained_until(temp_db):
    _insert("egi-ret-1", retained_until="2000-01-01T00:00:00Z")  # long past
    _insert("egi-ret-2", retained_until="2999-01-01T00:00:00Z")  # future, safe
    _insert("egi-ret-3")  # no retention date
    past = retention.list_past_retention(reference_iso=now_iso())
    ids = [r["id"] for r in past]
    assert "egi-ret-1" in ids
    assert "egi-ret-2" not in ids
    assert "egi-ret-3" not in ids  # no older_than -> not included


def test_older_than_includes_undated(temp_db):
    _insert("egi-ret-old", created_at="2020-01-01T00:00:00Z")
    past = retention.list_past_retention(reference_iso="2026-01-01T00:00:00Z", older_than_days=90)
    assert any(r["id"] == "egi-ret-old" for r in past)


def test_anonymize_strips_pii_keeps_status(temp_db):
    _insert("egi-anon-1", retained_until="2000-01-01T00:00:00Z")
    summary = retention.anonymize_records(["egi-anon-1"])
    assert summary["anonymized"] == 1
    with db.get_db() as conn:
        row = db.row_to_dict(conn.execute(
            "SELECT * FROM persons WHERE id = ?", ("egi-anon-1",)).fetchone())
    assert row["name"] is None
    assert row["cedula"] is None
    assert row["contact"] is None
    assert row["status"] == "missing"  # aggregate-safe field kept
    assert row["provenance"].startswith("anonymized")


def test_anonymized_not_relisted(temp_db):
    _insert("egi-anon-2", retained_until="2000-01-01T00:00:00Z")
    retention.anonymize_records(["egi-anon-2"])
    past = retention.list_past_retention(reference_iso=now_iso())
    assert all(r["id"] != "egi-anon-2" for r in past)


def test_retained_until_survives_resync(client):
    # A retention date set server-side must not be wiped by a later sync upsert.
    client.post("/sync", json={"records": [{
        "id": "egi-ret-sync", "name": "X", "status": "safe",
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    with db.get_db() as conn:
        conn.execute("UPDATE persons SET retained_until = ? WHERE id = ?",
                     ("2030-01-01T00:00:00Z", "egi-ret-sync"))
        conn.commit()
    # Re-sync a newer update of the same record.
    client.post("/sync", json={"records": [{
        "id": "egi-ret-sync", "name": "X2", "status": "safe",
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-03-01T00:00:00Z",
    }]})
    with db.get_db() as conn:
        row = conn.execute("SELECT retained_until FROM persons WHERE id = ?",
                           ("egi-ret-sync",)).fetchone()
    assert row["retained_until"] == "2030-01-01T00:00:00Z"
