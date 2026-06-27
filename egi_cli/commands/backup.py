"""``egi backup`` / ``egi restore`` — create and restore a server snapshot.

A backup is a single timestamped ``.tar.gz`` of the SQLite DB (WAL checkpointed
first) plus the uploads directory. Restore unpacks it back over the live paths.
Both resolve the same DB/upload locations as a running ``egi backend`` via
``ensure_server_importable()`` (which pins DB_PATH/UPLOAD_DIR under ``server/``).
"""

from datetime import datetime, timezone

import click


@click.command()
@click.option("--output", "output_dir", default=None,
              help="Directory to write the backup into (default: server/backups).")
@click.option("--no-uploads", is_flag=True, help="Skip the uploads/ directory.")
def backup(output_dir, no_uploads):
    """Create a timestamped tar.gz backup of the database and uploads."""
    from pathlib import Path

    from ..paths import ensure_server_importable, SERVER_DIR

    ensure_server_importable()
    import db  # noqa: E402
    import main  # noqa: E402
    from backup import create_backup  # noqa: E402

    out = Path(output_dir) if output_dir else (SERVER_DIR / "backups")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = create_backup(
        db_path=db.DB_PATH,
        upload_dir=main.UPLOAD_DIR,
        output_dir=out,
        timestamp=timestamp,
        include_uploads=not no_uploads,
    )
    size_kb = archive.stat().st_size / 1024
    click.secho(f"Backup created: {archive}", fg="green")
    click.echo(f"  size: {size_kb:.1f} KB")
    click.secho("Store it securely and OFF the server (see docs/DEPLOYMENT.md).", fg="yellow")


@click.command()
@click.argument("tarball")
@click.option("--confirm", is_flag=True, help="Required: overwrite the live DB/uploads.")
def restore(tarball, confirm):
    """Restore the database and uploads from a backup TARBALL (overwrites!)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402
    import main  # noqa: E402
    from backup import restore_backup  # noqa: E402

    if not confirm:
        click.secho("This OVERWRITES the live database and uploads.", fg="red")
        click.echo(f"  db:      {db.DB_PATH}")
        click.echo(f"  uploads: {main.UPLOAD_DIR}")
        click.echo("Stop the server first, then re-run with --confirm.")
        return

    summary = restore_backup(tarball, db_path=db.DB_PATH, upload_dir=main.UPLOAD_DIR)
    click.secho("Restore complete:", fg="green")
    click.echo(f"  database restored: {summary['restored_db']}")
    click.echo(f"  uploads restored:  {summary['restored_uploads']} file(s)")
