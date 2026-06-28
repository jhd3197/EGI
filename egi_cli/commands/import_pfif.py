"""``egi import-pfif`` — import PFIF JSON/XML into the local DB for review.

Implemented in Phase 5 (server/pfif.py)."""

import sys

import click


@click.command(name="import-pfif")
@click.argument("file", type=click.Path(allow_dash=True))
@click.option("--auto-approve", is_flag=True, help="Mark imported records reviewed=1 immediately.")
@click.option("--dry-run", is_flag=True, help="Report what would be imported without writing.")
def import_pfif(file, auto_approve, dry_run):
    """Import PFIF records from FILE (use '-' for stdin). Imports as reviewed=0 by default."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import os

    import db  # noqa: E402
    from modules import provenance  # noqa: E402
    from pfif import import_text  # noqa: E402

    if file == "-":
        raw = sys.stdin.buffer.read()
    else:
        with open(file, "rb") as f:
            raw = f.read()
    text = raw.decode("utf-8")

    # Raw-source provenance (plan-24.5): create an import_batches row for the file
    # so every PFIF-imported record carries an import_batch_id linking back to the
    # original filename + SHA-256. Skipped on a dry run (nothing is written).
    batch_id = None
    if not dry_run:
        db.init_db()  # idempotent; ensures import_batches exists before we write it
        with db.get_db() as conn:
            batch_id = provenance.create_import_batch(
                conn,
                file_bytes=raw,
                source_type="pfif_import",
                extraction_method="pfif-1.4",
                original_filename=(None if file == "-" else os.path.basename(file)),
                media_type="application/pfif+xml" if text.lstrip().startswith("<") else "application/json",
                uploaded_by="cli",
            )
            conn.commit()

    result = import_text(text, auto_approve=auto_approve, dry_run=dry_run, batch_id=batch_id)

    if batch_id:
        with db.get_db() as conn:
            provenance.finalize_batch(conn, batch_id, result["persons"] + result["reports"])
            conn.commit()

    verb = "Would import" if dry_run else "Imported"
    click.secho(
        f"{verb}: persons={result['persons']} reports={result['reports']} "
        f"(duplicates skipped: {result['skipped']})",
        fg="green",
    )
