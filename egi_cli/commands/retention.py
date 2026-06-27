"""``egi retention-review`` / ``egi anonymize`` — data retention tools (§11).

``retention-review`` lists records past their retention window so an operator
can decide what to keep. ``anonymize`` strips PII from those records (or specific
ids) while preserving status counts. Anonymize defaults to a dry run.
"""

import click


@click.command(name="retention-review")
@click.option("--older-than", "older_than", type=int, default=None,
              help="Also include records with no retention date older than N days.")
def retention_review(older_than):
    """List records eligible for retention review (past retained_until)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402
    from modules.retention import list_past_retention  # noqa: E402

    db.init_db()  # idempotent: ensure schema exists even before first server boot
    records = list_past_retention(older_than_days=older_than)
    if not records:
        click.secho("No records past retention.", fg="green")
        return
    click.secho(f"{len(records)} record(s) past retention:", fg="yellow")
    for r in records:
        when = r.get("retained_until") or f"created {r.get('created_at')}"
        click.echo(f"  {r['id']}  status={r.get('status')}  {when}")
    click.echo("Anonymize with: egi anonymize --older-than N --confirm")


@click.command()
@click.option("--older-than", "older_than", type=int, default=None,
              help="Anonymize records with no retention date older than N days.")
@click.option("--id", "ids", multiple=True, help="Specific record id(s) to anonymize.")
@click.option("--confirm", is_flag=True, help="Required: actually anonymize (irreversible).")
def anonymize(older_than, ids, confirm):
    """Strip PII from records past retention (or given ids), keeping status counts."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402
    from modules.retention import anonymize_records, list_past_retention  # noqa: E402

    db.init_db()  # idempotent: ensure schema exists
    target_ids = list(ids)
    if not target_ids:
        target_ids = [r["id"] for r in list_past_retention(older_than_days=older_than)]

    if not target_ids:
        click.secho("Nothing to anonymize.", fg="green")
        return

    if not confirm:
        click.secho(f"Dry run — would anonymize {len(target_ids)} record(s):", fg="yellow")
        for rid in target_ids:
            click.echo(f"  {rid}")
        click.echo("This is IRREVERSIBLE. Re-run with --confirm to proceed.")
        return

    summary = anonymize_records(target_ids, actor="cli:anonymize")
    click.secho(
        f"Anonymized {summary['anonymized']}/{summary['requested']} record(s).",
        fg="green",
    )
