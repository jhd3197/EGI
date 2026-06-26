"""``egi generate-synthetic`` — generate fake person records for demos/load tests.

Implemented in Phase 4 (server/research/synthetic.py)."""

import click


@click.command(name="generate-synthetic")
@click.option("--disaster", "disaster_id", default=None, help="disaster_id to attach generated persons to.")
@click.option("--count", default=20, show_default=True, type=int, help="How many persons to generate.")
@click.option("--dry-run", is_flag=True, help="Print what would be created without writing to the DB.")
def generate_synthetic(disaster_id, count, dry_run):
    """Generate fake but consistent person records (reserved V-00…… cédulas, fake names)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    from research.synthetic import generate_persons  # noqa: E402

    result = generate_persons(disaster_id=disaster_id, count=count, dry_run=dry_run)
    if dry_run:
        click.secho(f"Dry run — would create {len(result['preview'])} persons:", fg="yellow")
        for p in result["preview"]:
            click.echo(f"  {p['id']}  {p['name']:30s}  {p['status']:8s}  {p.get('cedula','')}")
        click.secho(f"(duplicates skipped: {result['skipped']})", fg="yellow")
    else:
        click.secho(
            f"Created {result['created']} synthetic persons "
            f"(duplicates skipped: {result['skipped']}).", fg="green",
        )
