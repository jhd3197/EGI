"""Dashboard statistics for commanders and administrators (plan-13 §3).

Aggregations over the existing tables — no new state is stored here. Two surfaces:

  * ``operation_stats(op_id)`` — one operation's situational picture: persons by
    status, a daily new-report time series, active action-plan task counts, and
    geospatial roll-ups.
  * ``global_stats()`` — cross-operation totals plus the two review queues a
    moderator cares about (moderation queue size, duplicate cluster count).

Everything is a plain ``GROUP BY`` over indexed columns so the commander
dashboard stays fast on a 10k-record DB (plan-13 success criteria). Merged
duplicates (``merged_into IS NOT NULL``) and rejected rows (``reviewed = -1``)
are excluded from the operational counts so the picture reflects live records.
"""

import os
import threading
import time
from typing import Callable, Optional

from fastapi import HTTPException

import db
from models import VALID_STATUSES

# Tiny in-process TTL cache for the expensive dashboard aggregates (plan-15 §8.3).
# global_stats() runs an O(n) duplicate-cluster pass, so a commander dashboard
# polling every few seconds shouldn't recompute it each time. Short TTL keeps the
# numbers fresh; reset in the test suite so fixtures don't see stale values.
_cache: dict = {}
_cache_lock = threading.Lock()


def _cache_ttl() -> int:
    try:
        return int(os.environ.get("STATS_CACHE_TTL", "30").strip() or 30)
    except ValueError:
        return 30


def cached(key: str, producer: Callable[[], dict], ttl: Optional[int] = None) -> dict:
    """Return a cached value for ``key``, recomputing via ``producer`` if stale."""
    ttl = _cache_ttl() if ttl is None else ttl
    if ttl <= 0:
        return producer()
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and (now - hit[0]) < ttl:
            return hit[1]
    value = producer()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _require_operation(conn, op_id: str) -> dict:
    row = conn.execute("SELECT * FROM events WHERE id = ?", (op_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Operation not found")
    return db.row_to_dict(row)


def _status_breakdown(rows) -> dict:
    """Normalize a (status, n) result set into a dict over all valid statuses."""
    counts = {s: 0 for s in sorted(VALID_STATUSES)}
    for r in rows:
        key = r["status"] or "unknown"
        counts[key] = counts.get(key, 0) + r["n"]
    return counts


def operation_stats(op_id: str) -> dict:
    """Situational stats for a single operation.

    persons_by_status + total, a daily new-record time series (last ``days`` days
    by default via ``records_per_day``), active/total action-plan task counts, and
    a geolocated-person count for the map view.
    """
    with db.get_db() as conn:
        op = _require_operation(conn, op_id)

        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM persons "
            "WHERE disaster_id = ? AND merged_into IS NULL AND reviewed >= 0 "
            "GROUP BY status",
            (op_id,),
        ).fetchall()
        by_status = _status_breakdown(status_rows)

        # New records per day (UTC date prefix of created_at), most recent first.
        day_rows = conn.execute(
            "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n FROM persons "
            "WHERE disaster_id = ? AND merged_into IS NULL "
            "GROUP BY day ORDER BY day DESC",
            (op_id,),
        ).fetchall()
        records_per_day = [{"day": r["day"], "count": r["n"]} for r in day_rows]

        # Active action-plan tasks: tasks on this operation's plans that are not
        # done/cancelled. Joined through action_plans -> events.
        task_row = conn.execute(
            """
            SELECT
              SUM(CASE WHEN t.state IN ('pending','in_progress') THEN 1 ELSE 0 END) AS active,
              COUNT(*) AS total
            FROM action_plan_tasks t
            JOIN action_plans p ON t.action_plan_id = p.id
            WHERE p.event_id = ? AND COALESCE(p.deleted, 0) = 0
            """,
            (op_id,),
        ).fetchone()
        tasks = {
            "active": task_row["active"] or 0,
            "total": task_row["total"] or 0,
        }

        geo_row = conn.execute(
            "SELECT COUNT(*) AS n FROM persons "
            "WHERE disaster_id = ? AND merged_into IS NULL "
            "AND lat IS NOT NULL AND lon IS NOT NULL",
            (op_id,),
        ).fetchone()

        pending_row = conn.execute(
            "SELECT COUNT(*) AS n FROM persons "
            "WHERE disaster_id = ? AND reviewed = 0",
            (op_id,),
        ).fetchone()

    persons_total = sum(by_status.values())
    return {
        "operation_id": op_id,
        "name": op.get("name"),
        "status": op.get("status"),
        "persons_total": persons_total,
        "persons_by_status": by_status,
        "records_per_day": records_per_day,
        "tasks": tasks,
        "geolocated_persons": geo_row["n"],
        "pending_review": pending_row["n"],
    }


def operation_timeseries(op_id: str, days: int = 30) -> dict:
    """New persons and reports per day for an operation, last ``days`` days.

    Two parallel daily series (new reports and status-changed/updated records) so
    the dashboard can chart intake vs. activity. ``days`` is clamped to [1, 365].
    """
    days = max(1, min(int(days or 30), 365))
    with db.get_db() as conn:
        _require_operation(conn, op_id)
        new_rows = conn.execute(
            "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n FROM persons "
            "WHERE disaster_id = ? AND merged_into IS NULL "
            "GROUP BY day ORDER BY day DESC LIMIT ?",
            (op_id, days),
        ).fetchall()
        # Reports linked to this operation's persons, by report creation day.
        report_rows = conn.execute(
            "SELECT substr(r.created_at, 1, 10) AS day, COUNT(*) AS n FROM reports r "
            "JOIN persons p ON r.person_id = p.id "
            "WHERE p.disaster_id = ? AND p.merged_into IS NULL "
            "GROUP BY day ORDER BY day DESC LIMIT ?",
            (op_id, days),
        ).fetchall()
        # Resolved cases per day: records whose status left 'missing'/'sighted'.
        resolved_rows = conn.execute(
            "SELECT substr(updated_at, 1, 10) AS day, COUNT(*) AS n FROM persons "
            "WHERE disaster_id = ? AND merged_into IS NULL "
            "AND status IN ('found','safe','deceased') "
            "GROUP BY day ORDER BY day DESC LIMIT ?",
            (op_id, days),
        ).fetchall()
    return {
        "operation_id": op_id,
        "days": days,
        "new_reports": [{"day": r["day"], "count": r["n"]} for r in new_rows],
        "new_notes": [{"day": r["day"], "count": r["n"]} for r in report_rows],
        "resolved": [{"day": r["day"], "count": r["n"]} for r in resolved_rows],
    }


def global_stats() -> dict:
    """Cross-operation totals plus the moderation and duplicate queue sizes."""
    with db.get_db() as conn:
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM persons "
            "WHERE merged_into IS NULL AND reviewed >= 0 GROUP BY status"
        ).fetchall()
        by_status = _status_breakdown(status_rows)

        persons_total = conn.execute(
            "SELECT COUNT(*) AS n FROM persons WHERE merged_into IS NULL AND reviewed >= 0"
        ).fetchone()["n"]

        op_rows = conn.execute(
            "SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS n "
            "FROM events GROUP BY status"
        ).fetchall()
        operations_by_status = {r["status"]: r["n"] for r in op_rows}
        operations_total = sum(operations_by_status.values())

        # Genuinely-pending moderation: untrusted-source rows still reviewed=0.
        # Trusted web rows also sit at reviewed=0 but stay visible (search trust
        # gate), so counting all reviewed=0 would overstate the actionable queue.
        from modules.moderation import UNTRUSTED_SOURCES

        placeholders = ",".join("?" * len(UNTRUSTED_SOURCES))
        moderation_queue = conn.execute(
            f"SELECT COUNT(*) AS n FROM persons "
            f"WHERE reviewed = 0 AND source IN ({placeholders})",
            tuple(UNTRUSTED_SOURCES),
        ).fetchone()["n"]

        merged_total = conn.execute(
            "SELECT COUNT(*) AS n FROM persons WHERE merged_into IS NOT NULL"
        ).fetchone()["n"]

    # Duplicate queue size is the count of pending fuzzy clusters. Lazy import to
    # avoid a module import cycle and keep stats cheap when not needed.
    from modules import duplicates

    duplicate_clusters = len(duplicates.find_clusters())

    return {
        "persons_total": persons_total,
        "persons_by_status": by_status,
        "operations_total": operations_total,
        "operations_by_status": operations_by_status,
        "moderation_queue": moderation_queue,
        "duplicate_clusters": duplicate_clusters,
        "merged_total": merged_total,
    }
