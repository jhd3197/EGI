# Backup/restore round-trip (plan-07 Phase 7). TEST DATA — NOT REAL.

import sqlite3

import backup as backup_mod


def _make_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES ('hola')")
    conn.commit()
    conn.close()


def test_backup_creates_tarball(tmp_path):
    db = tmp_path / "data" / "egi.db"
    db.parent.mkdir(parents=True)
    _make_db(db)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "a.jpg").write_bytes(b"img-bytes")

    out = tmp_path / "backups"
    archive = backup_mod.create_backup(db, uploads, out, timestamp="20260101T000000Z")
    assert archive.exists()
    assert archive.name == "egi-backup-20260101T000000Z.tar.gz"


def test_restore_round_trip(tmp_path):
    db = tmp_path / "data" / "egi.db"
    db.parent.mkdir(parents=True)
    _make_db(db)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "photo.jpg").write_bytes(b"original")

    archive = backup_mod.create_backup(
        db, uploads, tmp_path / "backups", timestamp="20260101T000000Z"
    )

    # Restore into a fresh location and verify the data survived.
    new_db = tmp_path / "restored" / "egi.db"
    new_uploads = tmp_path / "restored_uploads"
    summary = backup_mod.restore_backup(archive, new_db, new_uploads)
    assert summary["restored_db"] is True
    assert summary["restored_uploads"] == 1

    conn = sqlite3.connect(str(new_db))
    rows = conn.execute("SELECT v FROM t").fetchall()
    conn.close()
    assert rows == [("hola",)]
    assert (new_uploads / "photo.jpg").read_bytes() == b"original"


def test_no_uploads_flag_excludes_uploads(tmp_path):
    db = tmp_path / "data" / "egi.db"
    db.parent.mkdir(parents=True)
    _make_db(db)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "x.jpg").write_bytes(b"img")

    archive = backup_mod.create_backup(
        db, uploads, tmp_path / "b", timestamp="t", include_uploads=False
    )
    new_db = tmp_path / "r" / "egi.db"
    new_uploads = tmp_path / "ru"
    summary = backup_mod.restore_backup(archive, new_db, new_uploads)
    assert summary["restored_db"] is True
    assert summary["restored_uploads"] == 0


def test_integrity_check_passes_on_good_db(tmp_path):
    db = tmp_path / "egi.db"
    _make_db(db)
    assert backup_mod.integrity_check(db) is True


def test_integrity_check_fails_on_corrupt_db(tmp_path):
    db = tmp_path / "broken.db"
    db.write_bytes(b"this is not a sqlite database")
    assert backup_mod.integrity_check(db) is False


def test_create_backup_aborts_on_corrupt_db(tmp_path):
    import pytest

    db = tmp_path / "data" / "egi.db"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"corrupt")
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    with pytest.raises(RuntimeError):
        backup_mod.create_backup(db, uploads, tmp_path / "b", timestamp="t")


def test_restore_reports_integrity_ok(tmp_path):
    db = tmp_path / "data" / "egi.db"
    db.parent.mkdir(parents=True)
    _make_db(db)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    archive = backup_mod.create_backup(db, uploads, tmp_path / "b", timestamp="t")
    summary = backup_mod.restore_backup(archive, tmp_path / "r" / "egi.db", tmp_path / "ru")
    assert summary["integrity_ok"] is True


def test_prune_backups_removes_old(tmp_path):
    from datetime import datetime, timezone

    out = tmp_path / "backups"
    out.mkdir()
    old = out / "egi-backup-20200101T000000Z.tar.gz"
    new = out / "egi-backup-20991231T000000Z.tar.gz"
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    removed = backup_mod.prune_backups(out, retention_days=7, now=now)
    assert old in removed
    assert old.exists() is False
    assert new.exists() is True


def test_prune_disabled_with_zero_days(tmp_path):
    out = tmp_path / "backups"
    out.mkdir()
    old = out / "egi-backup-20200101T000000Z.tar.gz"
    old.write_bytes(b"x")
    assert backup_mod.prune_backups(out, retention_days=0) == []
    assert old.exists()


def test_encrypt_decrypt_round_trip(tmp_path):
    src = tmp_path / "egi-backup-t.tar.gz"
    src.write_bytes(b"secret backup bytes")
    try:
        enc = backup_mod.encrypt_file(src, key="correct horse battery staple")
    except RuntimeError:
        import pytest

        pytest.skip("cryptography not installed")
    assert enc.name.endswith(".enc")
    assert src.exists() is False
    dec = backup_mod.decrypt_file(enc, key="correct horse battery staple")
    assert dec.read_bytes() == b"secret backup bytes"


def test_encrypted_backup_restore_round_trip(tmp_path):
    try:
        import cryptography  # noqa: F401
    except ImportError:
        import pytest

        pytest.skip("cryptography not installed")
    db = tmp_path / "data" / "egi.db"
    db.parent.mkdir(parents=True)
    _make_db(db)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    archive = backup_mod.create_backup(db, uploads, tmp_path / "b", timestamp="t")
    enc = backup_mod.encrypt_file(archive, key="k")
    summary = backup_mod.restore_backup(
        enc, tmp_path / "r" / "egi.db", tmp_path / "ru", decrypt_key="k"
    )
    assert summary["restored_db"] is True
