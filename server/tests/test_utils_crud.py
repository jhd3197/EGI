# Unit tests for modules.crud — the timestamp-guarded last-write-wins primitives.
# Uses a real in-memory SQLite connection with a tiny table.
# TEST DATA — NOT REAL.
import sqlite3

import pytest

from modules import crud


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.execute(
        "CREATE TABLE widgets (id TEXT PRIMARY KEY, name TEXT, updated_at TEXT)"
    )
    yield c
    c.close()


def _insert(conn, rid, name, updated_at):
    conn.execute(
        "INSERT INTO widgets (id, name, updated_at) VALUES (?, ?, ?)",
        (rid, name, updated_at),
    )
    conn.commit()


# ── is_stale ────────────────────────────────────────────────────────────────

def test_is_stale_no_existing_row_is_false():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE widgets (id TEXT PRIMARY KEY, updated_at TEXT)")
    assert crud.is_stale(c, "widgets", "missing", "2026-01-01T00:00:00Z") is False
    c.close()


def test_is_stale_older_incoming_is_stale(conn):
    _insert(conn, "w1", "stored", "2026-06-01T00:00:00Z")
    # Incoming is older than the stored row -> stale.
    assert crud.is_stale(conn, "widgets", "w1", "2026-01-01T00:00:00Z") is True


def test_is_stale_newer_incoming_not_stale(conn):
    _insert(conn, "w1", "stored", "2026-01-01T00:00:00Z")
    assert crud.is_stale(conn, "widgets", "w1", "2026-12-01T00:00:00Z") is False


def test_is_stale_equal_instant_different_format_not_stale(conn):
    # Stored uses Z, incoming uses +00:00 offset — same instant, not stale
    # (normalize_ts canonicalizes both before the lexicographic compare).
    _insert(conn, "w1", "stored", "2026-06-01T00:00:00Z")
    assert crud.is_stale(conn, "widgets", "w1", "2026-06-01T00:00:00+00:00") is False


def test_is_stale_existing_row_no_timestamp_is_false(conn):
    _insert(conn, "w1", "stored", None)
    assert crud.is_stale(conn, "widgets", "w1", "2026-01-01T00:00:00Z") is False


def test_is_stale_incoming_none_is_false(conn):
    _insert(conn, "w1", "stored", "2026-06-01T00:00:00Z")
    assert crud.is_stale(conn, "widgets", "w1", None) is False


# ── lww_upsert ──────────────────────────────────────────────────────────────

def test_lww_upsert_inserts_new_row(conn):
    outcome = crud.lww_upsert(
        conn, "widgets", "w1", "2026-01-01T00:00:00Z",
        {"id": "w1", "name": "first", "updated_at": "2026-01-01T00:00:00Z"},
    )
    conn.commit()
    assert outcome == "written"
    row = conn.execute("SELECT name FROM widgets WHERE id=?", ("w1",)).fetchone()
    assert row[0] == "first"


def test_lww_upsert_newer_replaces(conn):
    _insert(conn, "w1", "old", "2026-01-01T00:00:00Z")
    outcome = crud.lww_upsert(
        conn, "widgets", "w1", "2026-06-01T00:00:00Z",
        {"id": "w1", "name": "new", "updated_at": "2026-06-01T00:00:00Z"},
    )
    conn.commit()
    assert outcome == "written"
    row = conn.execute("SELECT name FROM widgets WHERE id=?", ("w1",)).fetchone()
    assert row[0] == "new"


def test_lww_upsert_older_is_skipped(conn):
    _insert(conn, "w1", "current", "2026-06-01T00:00:00Z")
    outcome = crud.lww_upsert(
        conn, "widgets", "w1", "2026-01-01T00:00:00Z",
        {"id": "w1", "name": "stale", "updated_at": "2026-01-01T00:00:00Z"},
    )
    conn.commit()
    assert outcome == "skipped"
    # The stored row is untouched.
    row = conn.execute("SELECT name FROM widgets WHERE id=?", ("w1",)).fetchone()
    assert row[0] == "current"


def test_lww_upsert_respects_explicit_columns(conn):
    # columns pins order/subset; only listed columns are written.
    outcome = crud.lww_upsert(
        conn, "widgets", "w2", "2026-01-01T00:00:00Z",
        {"id": "w2", "name": "x", "updated_at": "2026-01-01T00:00:00Z", "extra": "ignored"},
        columns=["id", "name", "updated_at"],
    )
    conn.commit()
    assert outcome == "written"
    row = conn.execute("SELECT id, name FROM widgets WHERE id=?", ("w2",)).fetchone()
    assert row == ("w2", "x")
