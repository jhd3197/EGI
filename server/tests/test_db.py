# Schema creation, migration, and basic CRUD for the SQLite store.
# TEST DATA — NOT REAL.
import sqlite3

import pytest

import db


def _table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def _column_names(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_init_db_creates_all_tables(temp_db):
    with db.get_db() as conn:
        tables = _table_names(conn)
    for expected in {"persons", "events", "cities", "reports", "incidents", "sync_log"}:
        assert expected in tables


def test_persons_table_has_pfif_columns(temp_db):
    with db.get_db() as conn:
        cols = _column_names(conn, "persons")
    # PFIF + mesh provenance columns must all be present after init.
    for col in {
        "given_name", "family_name", "cedula", "sex", "photo_url",
        "last_known_location", "origin_device", "hop_count",
        "created_at", "updated_at",
    }:
        assert col in cols


def test_init_db_is_idempotent(temp_db):
    # Running init twice must not raise (CREATE IF NOT EXISTS + guarded migration).
    db.init_db()
    db.init_db()
    with db.get_db() as conn:
        assert "persons" in _table_names(conn)


def test_basic_person_crud(temp_db):
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO persons (id, name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("egi-test-0001", "Juan Pérez de prueba", "missing",
             "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM persons WHERE id = ?", ("egi-test-0001",)
        ).fetchone()
        record = db.row_to_dict(row)

    assert record["name"] == "Juan Pérez de prueba"
    assert record["status"] == "missing"
    assert record["hop_count"] == 0  # column default


def test_status_check_constraint_rejects_invalid(temp_db):
    # The SQLite CHECK must reject any status outside the six valid values.
    with pytest.raises(sqlite3.IntegrityError):
        with db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO persons (id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                ("egi-test-bad", "not-a-status",
                 "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
            conn.commit()


@pytest.mark.parametrize(
    "status", ["missing", "found", "safe", "deceased", "sighted", "care"]
)
def test_status_check_accepts_all_valid(temp_db, status):
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO persons (id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (f"egi-test-{status}", status,
             "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        conn.commit()


def test_migration_adds_missing_columns(temp_db):
    # Simulate a pre-PFIF database: a persons table without the new columns,
    # then verify the idempotent migration backfills them without data loss.
    with db.get_db() as conn:
        conn.execute("DROP TABLE persons")
        conn.execute(
            """
            CREATE TABLE persons (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO persons (id, name, created_at, updated_at) VALUES (?,?,?,?)",
            ("egi-test-old", "Ana de prueba", "2026-01-01T00:00:00Z",
             "2026-01-01T00:00:00Z"),
        )
        conn.commit()
        db._migrate_persons_columns(conn)
        conn.commit()
        cols = _column_names(conn, "persons")
        # Old row survives, new columns exist.
        row = conn.execute(
            "SELECT name FROM persons WHERE id = ?", ("egi-test-old",)
        ).fetchone()

    assert "cedula" in cols
    assert "origin_device" in cols
    assert row[0] == "Ana de prueba"
