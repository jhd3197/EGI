"""``egi unseed`` — remove seeded TEST DATA, preserving manual records.

Implemented in Phase 2 (server/seed/seed.py)."""

import click


@click.command()
@click.option("--confirm", is_flag=True, help="Required: actually delete seeded rows.")
def unseed(confirm):
    """Delete all rows created by `egi seed` (source='seed'); manual data is kept."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    from seed.seed import remove_seeded_data  # noqa: E402

    if not confirm:
        # Dry run by default so an operator never deletes by accident.
        summary = remove_seeded_data(dry_run=True)
        click.secho("Dry run — would delete:", fg="yellow")
        for key, val in summary.items():
            click.echo(f"  {key}: {val}")
        click.echo("Re-run with --confirm to actually delete.")
        return

    summary = remove_seeded_data(dry_run=False)
    click.secho("Removed seeded TEST DATA:", fg="green")
    for key, val in summary.items():
        click.echo(f"  {key}: {val}")
