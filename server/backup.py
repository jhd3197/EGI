"""Backup and restore for an EGI server (plan-07 §10).

A backup is a single timestamped ``.tar.gz`` holding the SQLite database and the
uploads directory, so a community server can be restored in minutes. The WAL is
checkpointed into the main DB file *before* archiving so the snapshot is
consistent and self-contained (no dangling ``-wal``/``-shm`` needed).

These functions take explicit paths (not module globals) so they are unit
testable; the ``egi backup`` / ``egi restore`` CLI commands resolve the live
paths from the server config and pass them in.
"""

import base64
import hashlib
import sqlite3
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

# Arc-name prefixes inside the tarball.
_DB_ARC = "data/egi.db"
_UPLOADS_ARC = "uploads"
_ENV_ARC = "env/.env"

# Backup filename pattern: egi-backup-<YYYYMMDDTHHMMSSZ>.tar.gz[.enc]
_BACKUP_GLOB = "egi-backup-*.tar.gz*"
_TS_FMT = "%Y%m%dT%H%M%SZ"


def integrity_check(db_path: Path) -> bool:
    """Run SQLite ``PRAGMA integrity_check`` — True iff the DB reports 'ok'.

    A missing DB is treated as a (vacuous) pass so a fresh deployment can still
    snapshot its uploads. Any corruption returns False so the caller can abort
    before shipping a broken backup offsite.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return True
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
        return bool(row) and str(row[0]).lower() == "ok"
    except Exception:
        return False


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
    verify_integrity: bool = True,
    env_path: Optional[Path] = None,
) -> Path:
    """Write ``egi-backup-<timestamp>.tar.gz`` into ``output_dir``; return its path.

    ``timestamp`` is passed in (not generated here) so callers control the
    filename and tests stay deterministic. The WAL is checkpointed first so the
    DB snapshot is self-contained. When ``verify_integrity`` is set (the default)
    a corrupt database aborts the backup with ``RuntimeError`` rather than
    shipping a broken snapshot. ``env_path`` (optional) folds a config file into
    the archive — intended for use with whole-tarball encryption.
    """
    db_path = Path(db_path)
    upload_dir = Path(upload_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_wal(db_path)

    if verify_integrity and not integrity_check(db_path):
        raise RuntimeError(
            f"SQLite integrity_check failed for {db_path}; refusing to back up a "
            "corrupt database. Investigate before retrying."
        )

    archive = output_dir / f"egi-backup-{timestamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        if db_path.exists():
            tar.add(str(db_path), arcname=_DB_ARC)
        if include_uploads and upload_dir.exists() and upload_dir.is_dir():
            for item in sorted(upload_dir.rglob("*")):
                if item.is_file():
                    rel = item.relative_to(upload_dir)
                    tar.add(str(item), arcname=f"{_UPLOADS_ARC}/{rel.as_posix()}")
        if env_path is not None and Path(env_path).exists():
            tar.add(str(env_path), arcname=_ENV_ARC)
    return archive


# ---- retention -------------------------------------------------------------


def _parse_backup_timestamp(name: str) -> Optional[datetime]:
    """Extract the UTC datetime from an ``egi-backup-<ts>.tar.gz[.enc]`` name."""
    stem = name
    for suffix in (".enc", ".gz", ".tar"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    prefix = "egi-backup-"
    if not stem.startswith(prefix):
        return None
    try:
        return datetime.strptime(stem[len(prefix):], _TS_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def prune_backups(output_dir: Path, retention_days: int, now: Optional[datetime] = None) -> List[Path]:
    """Delete backups older than ``retention_days``; return the removed paths.

    ``now`` is injectable so tests stay deterministic. A non-positive
    ``retention_days`` disables pruning (keep everything).
    """
    output_dir = Path(output_dir)
    if retention_days is None or retention_days <= 0 or not output_dir.is_dir():
        return []
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)
    removed: List[Path] = []
    for path in sorted(output_dir.glob(_BACKUP_GLOB)):
        ts = _parse_backup_timestamp(path.name)
        if ts is not None and ts < cutoff:
            try:
                path.unlink()
                removed.append(path)
            except OSError:
                pass
    return removed


# ---- optional encryption (cryptography / Fernet) ---------------------------


def _fernet(key: str):
    """Build a Fernet from an arbitrary passphrase (SHA-256 -> urlsafe base64)."""
    from cryptography.fernet import Fernet  # raises ImportError if absent

    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_file(path: Path, key: str) -> Path:
    """Encrypt ``path`` with a symmetric key -> ``path + '.enc'``; remove plaintext.

    Raises ``RuntimeError`` if the ``cryptography`` package is not installed, so
    the caller can degrade gracefully (skip offsite/encryption, keep the local
    plaintext backup).
    """
    path = Path(path)
    try:
        fernet = _fernet(key)
    except ImportError as exc:  # pragma: no cover - exercised when lib absent
        raise RuntimeError(
            "encryption requested but the 'cryptography' package is not installed "
            "(pip install cryptography)"
        ) from exc
    token = fernet.encrypt(path.read_bytes())
    enc_path = path.with_name(path.name + ".enc")
    enc_path.write_bytes(token)
    path.unlink()
    return enc_path


def decrypt_file(path: Path, key: str) -> Path:
    """Decrypt a ``*.enc`` tarball -> the path without the ``.enc`` suffix."""
    path = Path(path)
    fernet = _fernet(key)
    data = fernet.decrypt(path.read_bytes())
    out = path.with_name(path.name[:-4]) if path.name.endswith(".enc") else path.with_name(
        path.name + ".dec"
    )
    out.write_bytes(data)
    return out


# ---- optional offsite upload (S3-compatible via boto3) ----------------------


def upload_s3(path: Path, endpoint: Optional[str], bucket: str, key_name: Optional[str] = None) -> str:
    """Upload ``path`` to an S3-compatible bucket; return the object key.

    Uses ``boto3`` (with standard AWS_* env credentials). ``endpoint`` targets a
    non-AWS provider (Backblaze B2, MinIO, Wasabi). Raises ``RuntimeError`` if
    boto3 is missing so the caller can skip offsite and keep the local copy.
    """
    path = Path(path)
    key_name = key_name or path.name
    try:
        import boto3  # raises ImportError if absent
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "S3 upload requested but 'boto3' is not installed (pip install boto3)"
        ) from exc
    client = boto3.client("s3", endpoint_url=endpoint or None)
    client.upload_file(str(path), bucket, key_name)
    return key_name


def _is_within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def restore_backup(
    tarball: Path,
    db_path: Path,
    upload_dir: Path,
    decrypt_key: Optional[str] = None,
) -> dict:
    """Restore a backup tarball: DB -> ``db_path``, uploads -> ``upload_dir``.

    Refuses path-traversal members (a tampered archive can't escape the targets).
    Existing files are overwritten; the caller is expected to have stopped the
    server first (documented in the deployment/backup guide). An encrypted
    ``*.enc`` tarball is decrypted first when ``decrypt_key`` is supplied. The
    restored DB is integrity-checked and the result returned in ``integrity_ok``.
    """
    tarball = Path(tarball)
    db_path = Path(db_path)
    upload_dir = Path(upload_dir)
    if not tarball.exists():
        raise FileNotFoundError(f"backup not found: {tarball}")

    # Transparently decrypt an encrypted backup before reading it.
    decrypted_tmp = None
    if tarball.name.endswith(".enc"):
        if not decrypt_key:
            raise RuntimeError(
                "encrypted backup (.enc) but no decrypt key supplied "
                "(set BACKUP_ENCRYPT_KEY)"
            )
        tarball = decrypted_tmp = decrypt_file(tarball, decrypt_key)

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

    # Clean up a transient decrypted copy.
    if decrypted_tmp is not None:
        try:
            decrypted_tmp.unlink()
        except OSError:
            pass

    return {
        "tarball": str(tarball),
        "restored_db": restored_db,
        "restored_uploads": restored_uploads,
        "integrity_ok": integrity_check(db_path) if restored_db else None,
    }
