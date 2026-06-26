"""``egi ocr-review`` — list pending OCR/AI/PFIF imports awaiting moderation."""

import click


@click.command(name="ocr-review")
@click.option("--all", "show_all", is_flag=True, help="Include already-reviewed records too.")
def ocr_review(show_all):
    """List records pending review (source in ocr/ai_draft/pfif_import, reviewed=0)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402

    db.init_db()  # idempotent; ensures the table exists when run on a fresh repo

    sql ="SELECT id, source, name, status, location, reviewed, created_at FROM persons"
    if not show_all:
        sql += " WHERE reviewed = 0 AND source IN ('ocr','ai_draft','pfif_import')"
    sql += " ORDER BY created_at DESC"

    with db.get_db() as conn:
        rows = conn.execute(sql).fetchall()

    if not rows:
        click.secho("No pending imports to review.", fg="green")
        return

    click.secho(f"{len(rows)} record(s):", fg="cyan")
    for r in rows:
        flag = "✓" if r["reviewed"] else "·"
        name = r["name"] or "(no name)"
        click.echo(
            f"  {flag} [{r['source']:>11}] {r['id']}  {name:28s}  "
            f"{r['status'] or '-':8s}  {r['location'] or ''}"
        )
    click.echo(
        "\nReview via the API: GET /import/paper/<id> then "
        "POST /import/paper/<id>/review, or the moderation endpoints."
    )
