"""``egi seed`` — populate the local DB with clearly-marked TEST DATA.

Implemented in Phase 2 (server/seed/seed.py)."""

import click


@click.command()
@click.option("--disaster", "disaster_id", default=None, help="Restrict/seed under this disaster_id.")
@click.option("--count", default=20, show_default=True, type=int, help="Number of test persons to create.")
@click.option("--reports", "report_count", default=10, show_default=True, type=int, help="Number of test reports.")
def seed(disaster_id, count, report_count):
    """Seed events, cities, incidents, persons, and reports (all TEST DATA — NOT REAL)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    from seed.seed import seed_database  # noqa: E402

    summary = seed_database(
        disaster_id=disaster_id, person_count=count, report_count=report_count
    )
    click.secho("Seeded TEST DATA:", fg="green")
    for key, val in summary.items():
        click.echo(f"  {key}: {val}")
    click.secho("All rows tagged source='seed' — remove with `egi unseed --confirm`.", fg="yellow")
