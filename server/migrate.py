"""Minimal hand-rolled migration runner (plan-15 §7.2 / §7.3).

EGI's schema is created idempotently by ``db.SCHEMA`` + the column-add helpers in
``db.init_db``. This runner sits alongside that for *versioned, ordered* changes
that need to run exactly once and be CI-enforceable — the path the plan wants
instead of ad-hoc inline ``ALTER TABLE`` statements going forward.

A migration is a ``*.sql`` file in ``server/migrations/`` named
``NNNN_description.sql`` (e.g. ``0002_add_widget.sql``). The numeric prefix is the
version and defines apply order. Applied versions are recorded in the
``schema_migrations`` table so:

  * ``apply_pending()`` runs only what hasn't run yet (idempotent; called on
    every startup from ``db.init_db``);
  * ``check()`` returns False when migrations are pending, so ``egi migrate
    --check`` can fail CI.

Migrations are authored in **portable SQL** (plan-15 §7.2): prefer
``INSERT … ON CONFLICT DO UPDATE`` over ``INSERT OR REPLACE``, ``TEXT`` over
SQLite-only ``JSON``, and keep ``LIKE``/``ILIKE`` differences out of migrations.
"""

import re
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

import timeutil

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_NAME_RE = re.compile(r"^(\d+)[_-].*\.sql$")


def _now_iso() -> str:
    """Current UTC time as ISO-8601 — delegates to ``timeutil.utc_now_iso``."""
    return timeutil.utc_now_iso()


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )


def discover() -> List[Tuple[str, Path]]:
    """Return ``(version, path)`` for every migration file, sorted by version."""
    if not MIGRATIONS_DIR.is_dir():
        return []
    found = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        m = _NAME_RE.match(path.name)
        if m:
            found.append((m.group(1), path))
    found.sort(key=lambda t: t[0])
    return found


def applied_versions(conn: sqlite3.Connection) -> set:
    _ensure_table(conn)
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}


def pending(conn: Optional[sqlite3.Connection] = None) -> List[Tuple[str, Path]]:
    """List migrations not yet applied. Opens its own connection if none given."""
    own = conn is None
    if own:
        import db

        cm = db.get_db()
        conn = cm.__enter__()
    try:
        done = applied_versions(conn)
        return [(v, p) for v, p in discover() if v not in done]
    finally:
        if own:
            cm.__exit__(None, None, None)


def apply_pending(conn: Optional[sqlite3.Connection] = None) -> List[str]:
    """Apply all pending migrations in order; return the versions applied.

    Accepts an open connection (used from ``db.init_db`` so it joins the same
    transaction) or opens its own. Each migration's SQL is executed and a row is
    written to ``schema_migrations``. Caller commits when passing a connection.
    """
    own = conn is None
    if own:
        import db

        cm = db.get_db()
        conn = cm.__enter__()
    applied: List[str] = []
    try:
        _ensure_table(conn)
        done = applied_versions(conn)
        for version, path in discover():
            if version in done:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, _now_iso()),
            )
            applied.append(version)
        if own:
            conn.commit()
    finally:
        if own:
            cm.__exit__(None, None, None)
    return applied


def check() -> bool:
    """True when no migrations are pending (for ``egi migrate --check`` / CI)."""
    return len(pending()) == 0
