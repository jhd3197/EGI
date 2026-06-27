"""``egi run-reports`` / ``egi sitrep`` — SITREP reporting tools (plan-13 §3).

``run-reports`` is the cron entry point: it runs every active, due scheduled
report (generate + deliver to recipients). ``sitrep`` prints/saves an on-demand
SITREP for one operation in json/html/pdf.

    egi run-reports                         # run all due scheduled reports
    egi sitrep <op-id> --format html -o report.html

Touches the same DB as a running ``egi backend`` (paths pinned to server/).
"""

import click


@click.command(name="run-reports")
@click.option("--force", is_flag=True, help="Run all active reports regardless of schedule.")
def run_reports(force):
    """Run due (or all active, with --force) scheduled SITREP reports."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402
    from modules import scheduled_reports  # noqa: E402

    db.init_db()  # idempotent
    if force:
        reports = scheduled_reports.list_reports(active_only=True)["reports"]
        results = [scheduled_reports.run_report(r) for r in reports]
        summary = {"ran": len(results), "results": results}
    else:
        summary = scheduled_reports.run_due()

    if not summary["ran"]:
        click.secho("No reports due.", fg="green")
        return
    click.secho(f"Ran {summary['ran']} report(s):", fg="green")
    for r in summary["results"]:
        detail = f"sent={r.get('sent', 0)} failed={r.get('failed', 0)}"
        if r.get("skipped"):
            detail = f"skipped ({r['skipped']})"
        elif r.get("error"):
            detail = f"error ({r['error']})"
        click.echo(f"  {r['report_id']}: {detail}")


@click.command()
@click.argument("op_id")
@click.option("--format", "fmt", type=click.Choice(["json", "html", "pdf"]),
              default="html", show_default=True)
@click.option("-o", "--out", "out_path", type=click.Path(), default=None,
              help="Write to a file instead of stdout (required for pdf).")
def sitrep(op_id, fmt, out_path):
    """Generate an on-demand SITREP for an operation."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import json as _json

    import db  # noqa: E402
    from modules import sitrep as sitrep_mod  # noqa: E402

    db.init_db()  # idempotent
    try:
        result = sitrep_mod.generate(op_id, fmt)
    except RuntimeError as exc:  # missing reportlab for pdf
        raise click.ClickException(str(exc))
    from fastapi import HTTPException  # noqa: E402
    # generate() raises HTTPException(404) for unknown operations.

    if fmt == "pdf":
        if not out_path:
            raise click.ClickException("--out is required for pdf output")
        with open(out_path, "wb") as fh:
            fh.write(result)
        click.secho(f"Wrote {out_path} ({len(result)} bytes).", fg="green")
        return

    text = _json.dumps(result, ensure_ascii=False, indent=2) if fmt == "json" else result
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        click.secho(f"Wrote {out_path}.", fg="green")
    else:
        click.echo(text)
