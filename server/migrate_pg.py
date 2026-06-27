"""SQLite → PostgreSQL data cutover (plan-15 §7.3). EXPERIMENTAL.

A one-time copy of every table from the SQLite file into a PostgreSQL database.
The Postgres schema must already exist (apply the same ``db.SCHEMA`` / migrations
against Postgres first — see docs/POSTGRES.md). This only moves *data*, table by
table, with portable parameterized inserts and ``ON CONFLICT DO NOTHING`` so a
re-run is safe.

Kept out of the default runtime: it imports ``psycopg`` lazily and is only ever
reached through ``egi sqlite-to-postgres``, so a SQLite-only deployment never
needs the dependency.
"""

import sqlite3
from pathlib import Path
from typing import Dict


def _sqlite_tables(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def migrate_sqlite_to_postgres(sqlite_path: Path, pg_url: str, dry_run: bool = False) -> Dict:
    """Copy all rows from the SQLite DB into the Postgres target.

    Returns ``{"tables": {name: row_count, ...}}``. With ``dry_run`` it counts
    rows but writes nothing. Assumes the Postgres schema already exists.
    """
    import psycopg  # imported lazily; optional cutover-only dependency

    src = sqlite3.connect(str(sqlite_path))
    src.row_factory = sqlite3.Row
    summary: Dict[str, Dict[str, int]] = {"tables": {}}
    try:
        tables = _sqlite_tables(src)
        if dry_run:
            for t in tables:
                n = src.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                summary["tables"][t] = n
            return summary

        with psycopg.connect(pg_url) as dst:
            for t in tables:
                rows = src.execute(f"SELECT * FROM {t}").fetchall()
                if not rows:
                    summary["tables"][t] = 0
                    continue
                cols = rows[0].keys()
                collist = ", ".join(f'"{c}"' for c in cols)
                placeholders = ", ".join(["%s"] * len(cols))
                sql = (
                    f'INSERT INTO "{t}" ({collist}) VALUES ({placeholders}) '
                    f"ON CONFLICT DO NOTHING"
                )
                with dst.cursor() as cur:
                    cur.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
                dst.commit()
                summary["tables"][t] = len(rows)
        return summary
    finally:
        src.close()
