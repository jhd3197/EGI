"""``egi export-pfif`` — export persons + reports to PFIF-aligned JSON/XML.

Implemented in Phase 5 (server/pfif.py)."""

import click


@click.command(name="export-pfif")
@click.option("--since", default=None, help="Only records with updated_at > this ISO-8601 timestamp.")
@click.option("--disaster", "disaster_id", default=None, help="Filter by disaster_id.")
@click.option("--event", "event_id", default=None, help="Filter by event_id (via disaster_id).")
@click.option("--reviewed", default=None, type=int, help="Filter by reviewed flag (0/1).")
@click.option("--format", "fmt", type=click.Choice(["json", "xml"]), default="json", show_default=True)
@click.option("--out", "out_path", default=None, help="Output file. Defaults to stdout.")
def export_pfif(since, disaster_id, event_id, reviewed, fmt, out_path):
    """Export persons + reports as PFIF-aligned JSON (matches /sync) or PFIF 1.4 XML."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    from pfif import export_records  # noqa: E402

    text, counts = export_records(
        since=since, disaster_id=disaster_id, event_id=event_id,
        reviewed=reviewed, fmt=fmt,
    )
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        click.secho(
            f"Exported {counts['records']} persons + {counts['reports']} reports "
            f"-> {out_path}", fg="green",
        )
    else:
        click.echo(text)
