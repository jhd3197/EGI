# Seeding, synthetic generation, and PFIF export/import round-trip.
# Exercises the logic the egi CLI commands wrap. TEST DATA — NOT REAL.
import json

import db
import pfif
from research import synthetic
from seed import seed as seedmod


def _count(table):
    with db.get_db() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_seed_then_unseed_is_exact(temp_db):
    counts = seedmod.seed_database(person_count=10, report_count=5)
    assert counts["persons"] == 10
    assert counts["reports"] == 5
    assert counts["events"] >= 1
    assert _count("persons") == 10

    removed = seedmod.remove_seeded_data()
    assert removed["persons"] == 10
    # Everything seeded is gone.
    for table in ("persons", "reports", "events", "cities", "incidents"):
        assert _count(table) == 0


def test_seeded_rows_are_marked_test_data(temp_db):
    seedmod.seed_database(person_count=5, report_count=2)
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT id, source, provenance, cedula, reviewed FROM persons"
        ).fetchall()
    assert rows
    for r in rows:
        assert r["id"].startswith("egi-seed-person-")
        assert r["source"] == "seed"
        assert "TEST DATA" in (r["provenance"] or "")
        assert (r["cedula"] or "").startswith("V-00")
        assert r["reviewed"] == 1


def test_unseed_dry_run_does_not_delete(temp_db):
    seedmod.seed_database(person_count=4, report_count=1)
    removed = seedmod.remove_seeded_data(dry_run=True)
    assert removed["persons"] == 4
    assert _count("persons") == 4  # nothing actually deleted


def test_pfif_json_export_matches_sync_schema(temp_db):
    seedmod.seed_database(person_count=6, report_count=3)
    text, counts = pfif.export_records(fmt="json")
    payload = json.loads(text)  # must be valid JSON
    assert counts["records"] == 6
    assert "_comment" in payload and "records" in payload and "reports" in payload
    # /sync-shaped: camelCase timestamps on each record.
    assert "createdAt" in payload["records"][0]
    assert "updatedAt" in payload["records"][0]


def test_pfif_json_roundtrip_no_duplicates(temp_db):
    seedmod.seed_database(person_count=6, report_count=3)
    text, _ = pfif.export_records(fmt="json")

    # Re-importing the same file must skip everything as duplicates.
    result = pfif.import_text(text)
    assert result["persons"] == 0
    assert result["reports"] == 0
    assert result["skipped"] == 9  # 6 persons + 3 reports


def test_pfif_export_wipe_import_restores(temp_db):
    seedmod.seed_database(person_count=6, report_count=3)
    text, _ = pfif.export_records(fmt="json")
    seedmod.remove_seeded_data()
    assert _count("persons") == 0

    result = pfif.import_text(text)
    assert result["persons"] == 6
    assert result["reports"] == 3
    with db.get_db() as conn:
        row = conn.execute("SELECT source, reviewed FROM persons LIMIT 1").fetchone()
    assert row["source"] == "pfif_import"
    assert row["reviewed"] == 0  # imported records await moderation


def test_pfif_xml_roundtrip(temp_db):
    seedmod.seed_database(person_count=4, report_count=2)
    text, counts = pfif.export_records(fmt="xml")
    assert text.lstrip().startswith("<?xml")
    seedmod.remove_seeded_data()
    result = pfif.import_text(text)
    assert result["persons"] == 4
    assert result["reports"] == 2


def test_pfif_import_auto_approve(temp_db):
    seedmod.seed_database(person_count=3, report_count=0)
    text, _ = pfif.export_records(fmt="json")
    seedmod.remove_seeded_data()
    pfif.import_text(text, auto_approve=True)
    with db.get_db() as conn:
        reviewed = {r[0] for r in conn.execute("SELECT reviewed FROM persons").fetchall()}
    assert reviewed == {1}


def test_synthetic_dry_run_writes_nothing(temp_db):
    result = synthetic.generate_persons(count=5, dry_run=True)
    assert result["created"] == 0
    assert len(result["preview"]) == 5
    assert _count("persons") == 0


def test_synthetic_uses_reserved_cedula_range(temp_db):
    result = synthetic.generate_persons(count=5)
    assert result["created"] == 5
    with db.get_db() as conn:
        cedulas = [r[0] for r in conn.execute("SELECT cedula FROM persons").fetchall()]
    assert all(c.startswith("V-005") for c in cedulas)
    # Generated rows carry a TEST DATA provenance so unseed removes them.
    removed = seedmod.remove_seeded_data()
    assert removed["persons"] == 5
