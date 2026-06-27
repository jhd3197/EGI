# PostgreSQL Migration Path (EXPERIMENTAL)

Plan-15 Phase 4. EGI ships on **SQLite by default** — it is the right choice for
the vast majority of community deployments and needs zero setup. PostgreSQL is an
opt-in path for deployments that outgrow a single file (roughly when
`egi_db_size_bytes` passes ~5 GB, or when you need concurrent multi-process
writers behind several uvicorn workers).

> **Status:** the migration *runner*, schema-version tracking, the
> `egi sqlite-to-postgres` cutover helper, and portable-SQL guidance are shipped
> and tested. Running the full request path against PostgreSQL is **experimental**:
> a handful of modules still use SQLite-specific SQL (`INSERT OR REPLACE`,
> `PRAGMA`). Treat Postgres as a forward-looking path, not a finished GA feature.
> Track remaining work in the roadmap (Plan 15).

## Configuration

PostgreSQL is selected purely by environment:

```bash
DATABASE_URL=postgresql://egi:secret@localhost:5432/egi
```

When `DATABASE_URL` is empty (the default), EGI uses the SQLite file at `DB_PATH`.
`db.is_postgres()` / `db.database_url()` expose this to the rest of the code.

## Migration runner

Versioned schema changes live in `server/migrations/` as `NNNN_description.sql`
files (portable SQL). Applied versions are tracked in the `schema_migrations`
table so the runner is idempotent.

```bash
egi migrate            # apply pending migrations
egi migrate --check    # exit non-zero if any are pending (used by CI)
```

`egi migrate --check` is wired into CI so a PR that adds a migration file without
a matching apply path fails fast. `db.init_db()` also applies pending migrations
on every startup, so a fresh SQLite deployment is always current.

### Authoring a migration

1. Create `server/migrations/0002_my_change.sql`.
2. Write **portable SQL** (plan-15 §7.2):
   - `INSERT … ON CONFLICT (key) DO UPDATE` instead of `INSERT OR REPLACE`.
   - `TEXT` columns holding JSON instead of a SQLite-only `JSON` type.
   - Keep `LIKE` (SQLite) vs `ILIKE` (Postgres) differences in app code, not
     migrations.
3. Run `egi migrate`. The new version is recorded in `schema_migrations`.

Going forward, prefer a migration file over editing `db.SCHEMA` for schema
changes, so the change is versioned and CI-checkable.

## Cutover: SQLite → PostgreSQL

1. Stand up a PostgreSQL database and set `DATABASE_URL`.
2. Create the schema in Postgres (apply `db.SCHEMA` + migrations against it).
3. Install the optional driver: `pip install 'psycopg[binary]'`.
4. Dry run, then cut over:

   ```bash
   egi sqlite-to-postgres --dry-run    # report row counts, write nothing
   egi sqlite-to-postgres              # copy all tables (ON CONFLICT DO NOTHING)
   ```

5. Verify `/health` and `/stats/global` against the Postgres-backed server.

The cutover copies data table-by-table with parameterized inserts; it does not
create the schema. `psycopg` is a cutover-only optional dependency — a SQLite
deployment never needs it.

## Remaining work for full Postgres GA

- Replace `INSERT OR REPLACE` (e.g. `modules/sync.py`) with
  `INSERT … ON CONFLICT DO UPDATE`.
- Abstract `PRAGMA`/WAL calls behind a dialect check (`db.is_postgres()`).
- A connection layer in `db.get_db()` that returns a psycopg connection when
  `DATABASE_URL` is set, with a `?`/`%s` placeholder shim.
- CI job that boots the suite against a Postgres service container.
