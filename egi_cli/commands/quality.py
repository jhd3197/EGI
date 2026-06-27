"""``egi quality-scan`` — recompute data-quality scores + surface review work.

The nightly-job entry point for plan-13 §4 (Data quality). Recalculates the
cached per-record quality scores, then reports the fuzzy-duplicate clusters and
stale records a commander/moderator should review. Run from cron:

    egi quality-scan            # recompute + summary
    egi quality-scan --stale-days 14

Touches the same DB as a running ``egi backend`` (paths are pinned to server/).
"""

import click


@click.command(name="quality-scan")
@click.option("--stale-days", "stale_days", type=int, default=None,
              help="Days of no-update to flag a record as stale (default: module STALE_DAYS).")
@click.option("--limit", type=int, default=20, show_default=True,
              help="Max stale/duplicate rows to list.")
def quality_scan(stale_days, limit):
    """Recompute quality scores and list duplicates + stale records to review."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402
    from modules import duplicates, quality  # noqa: E402

    db.init_db()  # idempotent: ensure schema exists even before first server boot

    result = quality.recalculate_all()
    click.secho(
        f"Scored {result['scored']} record(s); "
        f"{result['duplicates_flagged']} flagged as possible duplicates.",
        fg="green",
    )

    summary = quality.summary()
    if summary.get("avg_score") is not None:
        click.echo(f"  avg score: {summary['avg_score']}  "
                   f"(completeness {summary['avg_completeness']}, "
                   f"confidence {summary['avg_confidence']}, "
                   f"freshness {summary['avg_freshness']})")
    if summary.get("issues"):
        issues = ", ".join(f"{k}={v}" for k, v in sorted(summary["issues"].items()))
        click.echo(f"  issues: {issues}")

    clusters = duplicates.find_clusters()
    if clusters:
        click.secho(f"\n{len(clusters)} duplicate cluster(s) to review:", fg="yellow")
        for c in clusters[:limit]:
            ids = ", ".join(m["id"] for m in c["members"])
            click.echo(f"  [{c['tier']}] {c['reason']}: {ids}")
    else:
        click.secho("\nNo duplicate clusters pending.", fg="green")

    days = stale_days if stale_days is not None else quality.STALE_DAYS
    stale = quality.stale_records(days=days, limit=limit)
    if stale["count"]:
        click.secho(f"\n{stale['count']} stale record(s) (no update in {days}d):", fg="yellow")
        for r in stale["records"]:
            click.echo(f"  {r['id']}  status={r.get('status')}  updated={r.get('updated_at')}")
    else:
        click.secho(f"\nNo records stale beyond {days} days.", fg="green")
