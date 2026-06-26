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
    from pfif import import_text  # noqa: E402

    if file == "-":
        text = sys.stdin.read()
    else:
        with open(file, "r", encoding="utf-8") as f:
            text = f.read()

    result = import_text(text, auto_approve=auto_approve, dry_run=dry_run)
    verb = "Would import" if dry_run else "Imported"
    click.secho(
        f"{verb}: persons={result['persons']} reports={result['reports']} "
        f"(duplicates skipped: {result['skipped']})",
        fg="green",
    )
