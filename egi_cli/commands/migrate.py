"""``egi migrate`` / ``egi sqlite-to-postgres`` — schema migration tools (plan-15 §7).

``egi migrate`` applies pending versioned migrations from ``server/migrations/``;
``--check`` exits non-zero when migrations are pending so CI can gate on it.
``egi sqlite-to-postgres`` is the one-time cutover helper: it dumps the SQLite DB
and loads it into a PostgreSQL target (``DATABASE_URL``). PostgreSQL support is
EXPERIMENTAL (see docs/POSTGRES.md) — SQLite remains the default and is unaffected.

Touches the same DB as a running ``egi backend`` (paths pinned to server/).
"""

import click


@click.command()
@click.option("--check", "check_only", is_flag=True,
              help="Exit non-zero if migrations are pending (for CI); apply nothing.")
def migrate(check_only):
    """Apply pending database migrations (or --check that none are pending)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402
    import migrate as runner  # noqa: E402

    db.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if check_only:
        pending = runner.pending()
        if pending:
            click.secho(f"{len(pending)} migration(s) pending:", fg="red")
            for version, path in pending:
                click.echo(f"  {version}  {path.name}")
            raise SystemExit(1)
        click.secho("Schema up to date — no pending migrations.", fg="green")
        return

    applied = runner.apply_pending()
    if not applied:
        click.secho("No pending migrations.", fg="green")
        return
    click.secho(f"Applied {len(applied)} migration(s):", fg="green")
    for version in applied:
        click.echo(f"  {version}")


@click.command(name="sqlite-to-postgres")
@click.option("--dry-run", is_flag=True, help="Report what would be migrated; write nothing.")
def sqlite_to_postgres(dry_run):
    """Export the SQLite DB and import it into the PostgreSQL target (DATABASE_URL).

    EXPERIMENTAL cutover helper (plan-15 §7.3). Requires DATABASE_URL to point at
    a PostgreSQL server and the ``psycopg`` package; degrades with a clear message
    if either is missing so a SQLite-only deployment is never disrupted.
    """
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402

    url = db.database_url()
    if not db.is_postgres():
        raise click.ClickException(
            "DATABASE_URL is not a postgresql:// URL. Set it to your Postgres "
            "target before running the cutover (see docs/POSTGRES.md)."
        )

    try:
        import psycopg  # noqa: F401
    except ImportError:
        raise click.ClickException(
            "psycopg is not installed. `pip install 'psycopg[binary]'` to run the "
            "SQLite→Postgres cutover (it is an optional, cutover-only dependency)."
        )

    from migrate_pg import migrate_sqlite_to_postgres  # noqa: E402

    click.secho(f"Source SQLite: {db.DB_PATH}", fg="cyan")
    click.secho(f"Target Postgres: {url.split('@')[-1]}", fg="cyan")
    summary = migrate_sqlite_to_postgres(db.DB_PATH, url, dry_run=dry_run)
    verb = "Would migrate" if dry_run else "Migrated"
    for table, n in summary["tables"].items():
        click.echo(f"  {verb} {n} row(s) -> {table}")
    click.secho("Done." if not dry_run else "Dry run complete.", fg="green")
