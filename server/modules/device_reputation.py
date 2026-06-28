"""Device reputation (plan-25 Phase 1 + Phase 5).

One row per mesh device fingerprint (``persons.origin_device``). Tracks how many
records a device created, how many were flagged or rejected, and derives a coarse
0-100 ``reputation_score`` + ``trust_tier`` bucket. Phase 5 adds the ``banned``
blocklist flag; a banned device's records are hidden server-side and the ban can
ride the mesh blocklist bundle to offline peers.

All writes are best-effort: reputation is a recomputable hint, never authoritative,
so a failure here must never break a sync or a moderation action.
"""

from typing import List, Optional

import db
from models import now_iso


def _tier_for_score(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _recompute_score(report_count: int, flag_count: int, rejected_count: int) -> int:
    """A simple bounded score: start at 50, reward sustained clean reporting,
    penalize flags and (more heavily) rejections. Clamped to 0-100."""
    score = 50
    score += min(report_count, 20)            # up to +20 for a track record
    score -= flag_count * 5                    # each flag stings
    score -= rejected_count * 15               # a rejection hurts a lot
    return max(0, min(100, score))


def get(device_id: str) -> Optional[dict]:
    if not device_id:
        return None
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM device_reputation WHERE device_id = ?", (device_id,)
        ).fetchone()
        return db.row_to_dict(row) if row else None


def list_devices(banned: Optional[bool] = None, limit: int = 200) -> List[dict]:
    sql = "SELECT * FROM device_reputation"
    params: list = []
    if banned is not None:
        sql += " WHERE banned = ?"
        params.append(1 if banned else 0)
    sql += " ORDER BY last_seen DESC LIMIT ?"
    params.append(limit)
    with db.get_db() as conn:
        return [db.row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def _ensure_row(conn, device_id: str, now: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO device_reputation "
        "(device_id, trust_tier, reputation_score, first_seen, last_seen, updated_at) "
        "VALUES (?, 'low', 50, ?, ?, ?)",
        (device_id, now, now, now),
    )


def _refresh(conn, device_id: str, now: str) -> None:
    row = conn.execute(
        "SELECT report_count, flag_count, rejected_count, banned "
        "FROM device_reputation WHERE device_id = ?",
        (device_id,),
    ).fetchone()
    if not row:
        return
    score = _recompute_score(row[0] or 0, row[1] or 0, row[2] or 0)
    # A banned device is pinned to the low tier regardless of score.
    tier = "low" if row[3] else _tier_for_score(score)
    conn.execute(
        "UPDATE device_reputation SET reputation_score = ?, trust_tier = ?, updated_at = ? "
        "WHERE device_id = ?",
        (score, tier, now, device_id),
    )


def observe_report(device_id: Optional[str], conn=None) -> None:
    """Record that ``device_id`` created/updated a record. Best-effort."""
    if not device_id:
        return
    now = now_iso()
    try:
        if conn is not None:
            _ensure_row(conn, device_id, now)
            conn.execute(
                "UPDATE device_reputation SET report_count = report_count + 1, last_seen = ? "
                "WHERE device_id = ?",
                (now, device_id),
            )
            _refresh(conn, device_id, now)
            return
        with db.get_db() as c:
            _ensure_row(c, device_id, now)
            c.execute(
                "UPDATE device_reputation SET report_count = report_count + 1, last_seen = ? "
                "WHERE device_id = ?",
                (now, device_id),
            )
            _refresh(c, device_id, now)
            c.commit()
    except Exception:
        pass


def observe_flag(device_id: Optional[str]) -> None:
    """Record that one of ``device_id``'s records was flagged. Best-effort."""
    _bump(device_id, "flag_count")


def observe_rejection(device_id: Optional[str]) -> None:
    """Record that one of ``device_id``'s records was rejected. Best-effort."""
    _bump(device_id, "rejected_count")


def _bump(device_id: Optional[str], column: str) -> None:
    if not device_id or column not in ("flag_count", "rejected_count"):
        return
    now = now_iso()
    try:
        with db.get_db() as c:
            _ensure_row(c, device_id, now)
            c.execute(
                f"UPDATE device_reputation SET {column} = {column} + 1, last_seen = ? "
                "WHERE device_id = ?",
                (now, device_id),
            )
            _refresh(c, device_id, now)
            c.commit()
    except Exception:
        pass


def is_banned(device_id: Optional[str]) -> bool:
    if not device_id:
        return False
    try:
        with db.get_db() as c:
            row = c.execute(
                "SELECT banned FROM device_reputation WHERE device_id = ?", (device_id,)
            ).fetchone()
            return bool(row and row[0])
    except Exception:
        return False


def set_banned(device_id: str, banned: bool, reason: Optional[str] = None) -> dict:
    """Ban / unban a device (plan-25 Phase 5). Idempotent; creates the row if new."""
    now = now_iso()
    with db.get_db() as c:
        _ensure_row(c, device_id, now)
        c.execute(
            "UPDATE device_reputation SET banned = ?, ban_reason = ?, updated_at = ? "
            "WHERE device_id = ?",
            (1 if banned else 0, reason if banned else None, now, device_id),
        )
        _refresh(c, device_id, now)
        c.commit()
    return get(device_id) or {"device_id": device_id, "banned": banned}


def banned_device_ids() -> List[str]:
    """The blocklist: device ids to reject/deprioritize. Used by the mesh bundle."""
    try:
        with db.get_db() as c:
            return [
                r[0]
                for r in c.execute(
                    "SELECT device_id FROM device_reputation WHERE banned = 1"
                ).fetchall()
            ]
    except Exception:
        return []
