"""``egi backup`` / ``egi restore`` / ``egi schedule-backup`` (plan-07 §10, plan-15 §6).

A backup is a single timestamped ``.tar.gz`` of the SQLite DB (WAL checkpointed
+ integrity-checked first) plus the uploads directory. ``--retention-days`` prunes
old local backups; an optional symmetric key encrypts the tarball, and an
S3-compatible endpoint ships it offsite. ``restore`` unpacks it back over the live
paths (decrypting first if needed). ``schedule-backup`` prints a ready-to-install
systemd timer or cron line so a community operator gets automated backups.

All resolve the same DB/upload locations as a running ``egi backend`` via
``ensure_server_importable()`` (which pins DB_PATH/UPLOAD_DIR under ``server/``).
"""

import os
from datetime import datetime, timezone

import click


@click.command()
@click.option("--output", "output_dir", default=None,
              help="Directory to write the backup into (default: server/backups).")
@click.option("--no-uploads", is_flag=True, help="Skip the uploads/ directory.")
@click.option("--include-env", is_flag=True,
              help="Fold server/.env into the archive (use with --encrypt).")
@click.option("--retention-days", type=int, default=None,
              help="Delete local backups older than N days (default: BACKUP_RETENTION_DAYS).")
@click.option("--encrypt", is_flag=True,
              help="Encrypt the tarball with BACKUP_ENCRYPT_KEY before it leaves the box.")
@click.option("--s3-endpoint", default=None,
              help="S3-compatible endpoint URL for offsite upload (B2/MinIO/Wasabi/AWS).")
@click.option("--s3-bucket", default=None, help="Target bucket for offsite upload.")
def backup(output_dir, no_uploads, include_env, retention_days, encrypt, s3_endpoint, s3_bucket):
    """Create a timestamped tar.gz backup of the database and uploads."""
    from pathlib import Path

    from ..paths import ensure_server_importable, SERVER_DIR

    ensure_server_importable()
    import db  # noqa: E402
    import main  # noqa: E402
    import backup as backup_mod  # noqa: E402

    out = Path(output_dir) if output_dir else (SERVER_DIR / "backups")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    env_path = (SERVER_DIR / ".env") if include_env else None

    try:
        archive = backup_mod.create_backup(
            db_path=db.DB_PATH,
            upload_dir=main.UPLOAD_DIR,
            output_dir=out,
            timestamp=timestamp,
            include_uploads=not no_uploads,
            env_path=env_path,
        )
    except RuntimeError as exc:  # integrity check failed
        raise click.ClickException(str(exc))

    size_kb = archive.stat().st_size / 1024
    click.secho(f"Backup created: {archive}", fg="green")
    click.echo(f"  size: {size_kb:.1f} KB")

    # Optional encryption.
    enc_key = os.environ.get("BACKUP_ENCRYPT_KEY", "").strip()
    if encrypt or enc_key:
        if not enc_key:
            click.secho("--encrypt set but BACKUP_ENCRYPT_KEY is empty; skipping.", fg="yellow")
        else:
            try:
                archive = backup_mod.encrypt_file(archive, enc_key)
                click.secho(f"Encrypted: {archive}", fg="green")
            except RuntimeError as exc:
                click.secho(f"Encryption skipped: {exc}", fg="yellow")

    # Optional offsite upload.
    endpoint = s3_endpoint or os.environ.get("BACKUP_S3_ENDPOINT", "").strip() or None
    bucket = s3_bucket or os.environ.get("BACKUP_S3_BUCKET", "").strip() or None
    if bucket:
        try:
            key_name = backup_mod.upload_s3(archive, endpoint, bucket)
            click.secho(f"Uploaded offsite: s3://{bucket}/{key_name}", fg="green")
        except RuntimeError as exc:
            click.secho(f"Offsite upload skipped: {exc}", fg="yellow")
        except Exception as exc:  # noqa: BLE001 - surface provider errors, keep local copy
            click.secho(f"Offsite upload failed (local copy kept): {exc}", fg="red")

    # Retention pruning.
    days = retention_days
    if days is None:
        try:
            days = int(os.environ.get("BACKUP_RETENTION_DAYS", "").strip() or 0)
        except ValueError:
            days = 0
    if days and days > 0:
        removed = backup_mod.prune_backups(out, days)
        if removed:
            click.echo(f"  pruned {len(removed)} backup(s) older than {days} day(s).")

    click.secho("Store it securely and OFF the server (see docs/OPERATIONS.md).", fg="yellow")


@click.command()
@click.argument("tarball")
@click.option("--confirm", is_flag=True, help="Required: overwrite the live DB/uploads.")
def restore(tarball, confirm):
    """Restore the database and uploads from a backup TARBALL (overwrites!)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402
    import main  # noqa: E402
    import backup as backup_mod  # noqa: E402

    if not confirm:
        click.secho("This OVERWRITES the live database and uploads.", fg="red")
        click.echo(f"  db:      {db.DB_PATH}")
        click.echo(f"  uploads: {main.UPLOAD_DIR}")
        click.echo("Stop the server first, then re-run with --confirm.")
        return

    decrypt_key = os.environ.get("BACKUP_ENCRYPT_KEY", "").strip() or None
    try:
        summary = backup_mod.restore_backup(
            tarball, db_path=db.DB_PATH, upload_dir=main.UPLOAD_DIR, decrypt_key=decrypt_key
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    click.secho("Restore complete:", fg="green")
    click.echo(f"  database restored: {summary['restored_db']}")
    click.echo(f"  uploads restored:  {summary['restored_uploads']} file(s)")
    integ = summary.get("integrity_ok")
    if integ is False:
        click.secho("  WARNING: integrity_check FAILED on the restored DB!", fg="red")
    elif integ:
        click.echo("  integrity_check:   ok")
    click.secho("Next: start the server (egi backend) and verify /health.", fg="yellow")


@click.command(name="schedule-backup")
@click.option("--time", "at_time", default="03:30",
              help="Daily run time HH:MM (server local time). Default 03:30.")
@click.option("--mode", type=click.Choice(["systemd", "cron"]), default="systemd",
              show_default=True, help="Which scheduler snippet to print.")
def schedule_backup(at_time, mode):
    """Print a ready-to-install systemd timer (or cron line) for nightly backups."""
    from ..paths import ensure_server_importable, SERVER_DIR

    ensure_server_importable()
    import sys

    egi = sys.executable.replace("python.exe", "egi").replace("python", "egi")
    hh, _, mm = at_time.partition(":")
    if mode == "cron":
        click.echo("# Add to crontab (crontab -e):")
        click.echo(f"{int(mm)} {int(hh)} * * *  cd {SERVER_DIR} && {egi} backup "
                   f"--retention-days 7 >> {SERVER_DIR}/backups/backup.log 2>&1")
        return

    click.echo("# /etc/systemd/system/egi-backup.service")
    click.echo("[Unit]\nDescription=EGI nightly backup\n")
    click.echo("[Service]\nType=oneshot")
    click.echo(f"WorkingDirectory={SERVER_DIR}")
    click.echo(f"ExecStart={egi} backup --retention-days 7\n")
    click.echo("# /etc/systemd/system/egi-backup.timer")
    click.echo("[Unit]\nDescription=Run EGI backup daily\n")
    click.echo("[Timer]")
    click.echo(f"OnCalendar=*-*-* {at_time}:00")
    click.echo("Persistent=true\n")
    click.echo("[Install]\nWantedBy=timers.target")
    click.echo("\n# Then: sudo systemctl enable --now egi-backup.timer")
