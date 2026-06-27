# Migration runner + system events (plan-15 Phase 4). TEST DATA — NOT REAL.

import db
import migrate
from modules import system_events


def test_baseline_applied_on_init(temp_db):
    # init_db (via the fixture) should have applied the baseline migration.
    assert migrate.check() is True
    with db.get_db() as conn:
        versions = migrate.applied_versions(conn)
    assert "0001" in versions


def test_apply_pending_is_idempotent(temp_db):
    # Re-running applies nothing new.
    applied = migrate.apply_pending()
    assert applied == []


def test_pending_detects_new_migration(temp_db, tmp_path, monkeypatch):
    new_dir = tmp_path / "migrations"
    new_dir.mkdir()
    (new_dir / "0001_baseline.sql").write_text("SELECT 1;", encoding="utf-8")
    (new_dir / "0099_extra.sql").write_text(
        "CREATE TABLE IF NOT EXISTS _mig_test (id TEXT);", encoding="utf-8"
    )
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", new_dir)
    # 0001 already applied by the fixture; 0099 is new.
    pending = migrate.pending()
    versions = [v for v, _ in pending]
    assert "0099" in versions
    assert migrate.check() is False
    applied = migrate.apply_pending()
    assert "0099" in applied
    assert migrate.check() is True


def test_database_url_helpers(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert db.is_postgres() is False
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/egi")
    assert db.is_postgres() is True
    assert db.database_url().startswith("postgresql://")


def test_system_events_record_and_list(client):
    system_events.record("startup", "test boot", level="info", details={"v": "0.1.0"})
    system_events.record("backup_failed", "disk full", level="error")
    r = client.get("/system/events")
    assert r.status_code == 200
    types = {e["event_type"] for e in r.json()["entries"]}
    assert "startup" in types
    assert "backup_failed" in types

    errors = client.get("/system/events?level=error").json()["entries"]
    assert errors and all(e["level"] == "error" for e in errors)


def test_migration_status_endpoint(client):
    r = client.get("/system/migrations")
    assert r.status_code == 200
    body = r.json()
    assert body["up_to_date"] is True
    assert "0001" in body["all"]
