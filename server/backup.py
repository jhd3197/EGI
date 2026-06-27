"""Backup and restore for an EGI server (plan-07 §10).

A backup is a single timestamped ``.tar.gz`` holding the SQLite database and the
uploads directory, so a community server can be restored in minutes. The WAL is
checkpointed into the main DB file *before* archiving so the snapshot is
consistent and self-contained (no dangling ``-wal``/``-shm`` needed).

These functions take explicit paths (not module globals) so they are unit
testable; the ``egi backup`` / ``egi restore`` CLI commands resolve the live
paths from the server config and pass them in.
"""

import sqlite3
import tarfile
from pathlib import Path
from typing import Optional

# Arc-name prefixes inside the tarball.
_DB_ARC = "data/egi.db"
_UPLOADS_ARC = "uploads"


def checkpoint_wal(db_path: Path) -> None:
    """Fold the WAL back into the main DB file so the snapshot is consistent.

    Best-effort: a missing DB or a locked checkpoint must not abort a backup.
    """
    if not Path(db_path).exists():
        return
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def create_backup(
    db_path: Path,
    upload_dir: Path,
    output_dir: Path,
    timestamp: str,
    include_uploads: bool = True,
) -> Path:
    """Write ``egi-backup-<timestamp>.tar.gz`` into ``output_dir``; return its path.

    ``timestamp`` is passed in (not generated here) so callers control the
    filename and tests stay deterministic.
    """
    db_path = Path(db_path)
    upload_dir = Path(upload_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_wal(db_path)

    archive = output_dir / f"egi-backup-{timestamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        if db_path.exists():
            tar.add(str(db_path), arcname=_DB_ARC)
        if include_uploads and upload_dir.exists() and upload_dir.is_dir():
            for item in sorted(upload_dir.rglob("*")):
                if item.is_file():
                    rel = item.relative_to(upload_dir)
                    tar.add(str(item), arcname=f"{_UPLOADS_ARC}/{rel.as_posix()}")
    return archive


def _is_within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def restore_backup(tarball: Path, db_path: Path, upload_dir: Path) -> dict:
    """Restore a backup tarball: DB -> ``db_path``, uploads -> ``upload_dir``.

    Refuses path-traversal members (a tampered archive can't escape the targets).
    Existing files are overwritten; the caller is expected to have stopped the
    server first (documented in the deployment/backup guide).
    """
    tarball = Path(tarball)
    db_path = Path(db_path)
    upload_dir = Path(upload_dir)
    if not tarball.exists():
        raise FileNotFoundError(f"backup not found: {tarball}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    restored_db = False
    restored_uploads = 0
    with tarfile.open(tarball, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name
            if name == _DB_ARC:
                src = tar.extractfile(member)
                if src is not None:
                    db_path.write_bytes(src.read())
                    restored_db = True
            elif name.startswith(_UPLOADS_ARC + "/"):
                rel = name[len(_UPLOADS_ARC) + 1:]
                dest = upload_dir / rel
                if not _is_within(upload_dir, dest):
                    continue  # skip traversal attempts
                dest.parent.mkdir(parents=True, exist_ok=True)
                src = tar.extractfile(member)
                if src is not None:
                    dest.write_bytes(src.read())
                    restored_uploads += 1

    return {
        "tarball": str(tarball),
        "restored_db": restored_db,
        "restored_uploads": restored_uploads,
    }
