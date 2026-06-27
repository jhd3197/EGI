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
