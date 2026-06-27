"""Hand-rolled Prometheus metrics (plan-15 §4.3).

We expose a scrapeable ``GET /metrics`` in the Prometheus text exposition format
*without* taking a ``prometheus-client`` dependency — the same reasoning as
``ratelimit.py``: a community server may run on a Raspberry Pi, so we keep the
runtime lean and the format is trivial to emit by hand.

Two kinds of series:

  * **Counters / histograms** fed live by the request middleware
    (``observe_request``) and by code paths that increment domain counters
    (``inc_sync``). These live in process memory, so they are per-worker and
    reset on restart — which is exactly how Prometheus counters are expected to
    behave (``rate()`` handles resets).
  * **Gauges** sampled from the database at *render time*
    (``_db_gauges``): DB size, moderation/duplicate backlog, sync volume. These
    are point-in-time truths that survive a restart because they come from the DB.

PRIVACY (plan-15 §14): labels are limited to HTTP method, the *route template*
(never the concrete path, so no cédula/name/id leaks), and status code. No record
content is ever exposed.
"""

import os
import threading
import time
from typing import Dict, Tuple

# Request-duration histogram buckets in seconds (Prometheus convention).
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class _Hist:
    __slots__ = ("buckets", "sum", "count")

    def __init__(self):
        self.buckets = [0] * len(_BUCKETS)
        self.sum = 0.0
        self.count = 0

    def observe(self, value: float) -> None:
        self.count += 1
        self.sum += value
        for i, edge in enumerate(_BUCKETS):
            if value <= edge:
                self.buckets[i] += 1


class Metrics:
    """Process-global metric registry. Thread-safe for uvicorn worker threads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._requests: Dict[Tuple[str, str, str], int] = {}
        self._durations: Dict[Tuple[str, str], _Hist] = {}
        self._sync_records: Dict[str, int] = {"in": 0, "out": 0}

    def reset(self) -> None:
        """Clear in-memory counters (used by the test suite)."""
        with self._lock:
            self._requests.clear()
            self._durations.clear()
            self._sync_records = {"in": 0, "out": 0}

    def observe_request(self, method: str, route: str, status: int, duration_s: float) -> None:
        with self._lock:
            key = (method, route, str(status))
            self._requests[key] = self._requests.get(key, 0) + 1
            hist = self._durations.get((method, route))
            if hist is None:
                hist = _Hist()
                self._durations[(method, route)] = hist
            hist.observe(duration_s)

    def inc_sync(self, direction: str, n: int = 1) -> None:
        """Count records crossing /sync (direction: 'in' or 'out')."""
        if direction not in ("in", "out"):
            return
        with self._lock:
            self._sync_records[direction] = self._sync_records.get(direction, 0) + int(n)

    # ---- rendering --------------------------------------------------------

    def render(self) -> str:
        lines = []
        with self._lock:
            requests = dict(self._requests)
            durations = {k: (list(v.buckets), v.sum, v.count) for k, v in self._durations.items()}
            sync = dict(self._sync_records)

        # build_info
        try:
            from version import __version__ as ver
        except Exception:  # pragma: no cover
            ver = "unknown"
        lines.append("# HELP egi_build_info EGI server build information.")
        lines.append("# TYPE egi_build_info gauge")
        lines.append(f'egi_build_info{{version="{_esc(ver)}"}} 1')

        # http requests total
        lines.append("# HELP egi_http_requests_total Total HTTP requests.")
        lines.append("# TYPE egi_http_requests_total counter")
        for (method, route, status), n in sorted(requests.items()):
            lines.append(
                f'egi_http_requests_total{{method="{_esc(method)}",'
                f'route="{_esc(route)}",status="{_esc(status)}"}} {n}'
            )

        # http request duration histogram
        lines.append("# HELP egi_http_request_duration_seconds HTTP request latency.")
        lines.append("# TYPE egi_http_request_duration_seconds histogram")
        for (method, route), (buckets, total, count) in sorted(durations.items()):
            cumulative = 0
            for edge, b in zip(_BUCKETS, buckets):
                cumulative += b
                lines.append(
                    f'egi_http_request_duration_seconds_bucket{{method="{_esc(method)}",'
                    f'route="{_esc(route)}",le="{edge}"}} {cumulative}'
                )
            lines.append(
                f'egi_http_request_duration_seconds_bucket{{method="{_esc(method)}",'
                f'route="{_esc(route)}",le="+Inf"}} {count}'
            )
            lines.append(
                f'egi_http_request_duration_seconds_sum{{method="{_esc(method)}",'
                f'route="{_esc(route)}"}} {total}'
            )
            lines.append(
                f'egi_http_request_duration_seconds_count{{method="{_esc(method)}",'
                f'route="{_esc(route)}"}} {count}'
            )

        # sync records (in-memory counters)
        lines.append("# HELP egi_sync_records_total Records crossing /sync by direction.")
        lines.append("# TYPE egi_sync_records_total counter")
        for direction in ("in", "out"):
            lines.append(
                f'egi_sync_records_total{{direction="{direction}"}} {sync.get(direction, 0)}'
            )

        # DB-derived gauges
        lines.extend(self._db_gauges())

        return "\n".join(lines) + "\n"

    def _db_gauges(self) -> list:
        """Sample point-in-time gauges from the DB. Each guarded independently."""
        out = []

        def gauge(name, help_text, value):
            out.append(f"# HELP {name} {help_text}")
            out.append(f"# TYPE {name} gauge")
            out.append(f"{name} {value}")

        # DB size (main file + WAL + SHM if present).
        try:
            import db as _db

            total = 0
            base = _db.DB_PATH
            for suffix in ("", "-wal", "-shm"):
                p = base.parent / (base.name + suffix)
                if p.exists():
                    total += p.stat().st_size
            gauge("egi_db_size_bytes", "Size of the SQLite database files in bytes.", total)
        except Exception:
            pass

        # Moderation + duplicate + merged backlog from a single connection.
        try:
            import db as _db
            from modules.moderation import UNTRUSTED_SOURCES

            placeholders = ",".join("?" * len(UNTRUSTED_SOURCES))
            with _db.get_db() as conn:
                pending_mod = conn.execute(
                    f"SELECT COUNT(*) AS n FROM persons "
                    f"WHERE reviewed = 0 AND source IN ({placeholders})",
                    tuple(UNTRUSTED_SOURCES),
                ).fetchone()["n"]
                pending_msgs = conn.execute(
                    "SELECT channel, COUNT(*) AS n FROM messages "
                    "WHERE status = 'pending' GROUP BY channel"
                ).fetchall()
                sync_rows = conn.execute(
                    "SELECT direction, COALESCE(SUM(record_count), 0) AS n "
                    "FROM sync_log GROUP BY direction"
                ).fetchall()
            gauge(
                "egi_pending_moderation_total",
                "Untrusted-source records awaiting moderation.",
                pending_mod,
            )
            out.append("# HELP egi_messages_pending_total Pending outbound messages per channel.")
            out.append("# TYPE egi_messages_pending_total gauge")
            if pending_msgs:
                for row in pending_msgs:
                    ch = row["channel"] or "unknown"
                    out.append(f'egi_messages_pending_total{{channel="{_esc(ch)}"}} {row["n"]}')
            else:
                out.append('egi_messages_pending_total{channel="none"} 0')
            # Persisted sync volume from sync_log (survives restarts), exposed as a
            # separate gauge so it complements the in-memory counter above.
            out.append("# HELP egi_sync_log_records_total Records logged in sync_log by direction.")
            out.append("# TYPE egi_sync_log_records_total gauge")
            seen = {r["direction"] or "unknown": r["n"] for r in sync_rows}
            for direction in ("in", "out"):
                out.append(
                    f'egi_sync_log_records_total{{direction="{direction}"}} '
                    f'{seen.get(direction, 0)}'
                )
        except Exception:
            pass

        # Duplicate clusters (best-effort; can be O(n) on large DBs, so guarded).
        try:
            from modules import duplicates

            gauge(
                "egi_pending_duplicates_total",
                "Pending fuzzy-duplicate clusters awaiting review.",
                len(duplicates.find_clusters()),
            )
        except Exception:
            pass

        # Last successful backup timestamp (newest backup file mtime).
        try:
            ts = _last_backup_timestamp()
            if ts is not None:
                gauge(
                    "egi_backup_last_success_timestamp",
                    "Unix time of the most recent backup file.",
                    int(ts),
                )
        except Exception:
            pass

        return out


def _last_backup_timestamp():
    """Newest mtime among egi-backup-*.tar.gz files, or None if no backups."""
    candidates = []
    for d in _backup_dirs():
        if d.is_dir():
            candidates.extend(d.glob("egi-backup-*.tar.gz*"))
    if not candidates:
        return None
    return max(p.stat().st_mtime for p in candidates)


def _backup_dirs():
    from pathlib import Path

    dirs = []
    env = os.environ.get("BACKUP_DIR", "").strip()
    if env:
        dirs.append(Path(env))
    try:
        import db as _db

        dirs.append(_db.DB_PATH.parent.parent / "backups")
    except Exception:
        pass
    return dirs


def _esc(value) -> str:
    """Escape a Prometheus label value."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# Module-level singleton shared by the middleware and any counter call sites.
metrics = Metrics()


def route_template(request) -> str:
    """Best-effort route template for a request (bounded-cardinality label).

    Uses the matched Starlette route's ``path_format`` (e.g. ``/persons/{id}``)
    so the concrete id never becomes a label value. Unmatched requests collapse
    to ``"unmatched"`` so a flood of random paths can't explode cardinality.
    """
    route = request.scope.get("route")
    if route is not None:
        path = getattr(route, "path_format", None) or getattr(route, "path", None)
        if path:
            return path
    return "unmatched"
