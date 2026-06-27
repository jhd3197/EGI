# EGI Performance & Load Testing

Plan-15 Phase 5. This document defines EGI's service-level objectives (SLOs) and
how to verify them. The goal is modest and honest: prove EGI handles a realistic
community deployment (10k–100k records on a 1–2 vCPU VPS) without falling over.

## Service-level objectives (SLOs)

Measured on a single 1 vCPU / 1 GB server with a 10,000-record SQLite database:

| Surface | SLO |
| --- | --- |
| `GET /persons` search | p95 < **500 ms** |
| `POST /sync` (batch of 1,000 records) | < **5 s** |
| Dashboard (`/stats/global`, `/stats/operations/{id}`) | < **2 s** |
| PWA initial bundle | < **500 KB** gzipped |

These are targets for the *default* SQLite deployment. Past ~5 GB of database
(`egi_db_size_bytes` metric) move to PostgreSQL — see
[OPERATIONS.md](OPERATIONS.md) and plan-15 Phase 4.

## Server load testing (locust)

Locust is **optional tooling**, not a runtime dependency. Install it only to run
a load test:

```bash
pip install locust

# 1. Seed a realistic dataset (fake TEST DATA, removable with `egi unseed`).
egi generate-synthetic --count 10000

# 2. Boot the server in one shell.
egi backend                      # serves on :3000

# 3. Run the load test in another shell (headless, p95 CSV report).
locust -f server/tests/load/locustfile.py --host http://localhost:3000 \
    --headless -u 50 -r 10 -t 1m --csv egi-load
```

`egi-load_stats.csv` reports per-endpoint p50/p95/p99 and RPS. Compare the
`GET /persons?q=` and `POST /sync` p95 columns against the SLOs above.

The scenarios (`server/tests/load/locustfile.py`): search (weight 3), sync upload
(weight 2), moderation queue (weight 1), health (weight 1) — roughly the mix a
real deployment sees. Set `EGI_LOAD_TOKEN` if the target enforces auth.

### CI (optional, non-blocking)

A load run is **not** part of the blocking CI gate (it needs a seeded DB and a
running server). To wire an optional nightly/dispatch job, start the server, run
the headless locust command above, and publish `egi-load_stats.csv` as an
artifact. Treat regressions as advisory, not a merge blocker (plan-15 §8.4).

## Frontend performance (Lighthouse CI)

Bundle size and runtime performance are checked with Lighthouse CI. Config lives
in `frontend/tests/perf/lighthouserc.js`.

```bash
cd frontend
npm run build
npx @lhci/cli autorun        # builds, serves dist/, runs Lighthouse, asserts budgets
```

The budget asserts the initial JS bundle stays under the 500 KB gzipped SLO and
flags performance/accessibility regressions. Lighthouse CI is optional tooling;
install `@lhci/cli` only when running it.

## Query optimization notes

- **Indexes:** the hot search/sort columns are indexed in `db.py`
  (`idx_persons_name`, `idx_persons_status`, `idx_persons_cedula`,
  `idx_persons_updated_at`, `idx_persons_disaster`, plus message/sync indexes).
  Review a slow query with `EXPLAIN QUERY PLAN` before adding more.
- **Pagination:** `GET /persons` is cursor-paginated; `GET /audit/log` and
  `GET /messages` take `limit`/`offset`. Never return an unbounded result set.
- **Caching:** `GET /stats/global` runs an O(n) duplicate-cluster pass, so it is
  TTL-cached in-process (`STATS_CACHE_TTL`, default 30s). The per-record quality
  scores are cached in `data_quality_scores` and recomputed by `egi quality-scan`.
