"""Operation / disaster subscriptions (plan-24 Phase 6).

A user can subscribe to a specific operation to scope what reaches them, and
``mute`` an operation to stay enrolled while silencing its notifications without
leaving. Auto-subscription happens when a user creates a report or joins an SAR
operation, so volunteers don't have to opt in by hand.

Rows live in ``operation_subscriptions`` keyed (user_id, operation_id). The
notification gate (modules/notifications.py) reads ``muted`` to decide whether an
operation's alerts reach the user. All functions are best-effort and never raise
on a missing operation — a subscription is a lightweight preference, not a FK.
"""

from typing import List, Optional

import db
from models import now_iso


def subscribe(user_id: str, operation_id: str, muted: int = 0) -> dict:
    """Subscribe a user to an operation (idempotent upsert). Preserves created_at."""
    now = now_iso()
    with db.get_db() as conn:
        existing = conn.execute(
            "SELECT created_at FROM operation_subscriptions WHERE user_id = ? AND operation_id = ?",
            (user_id, operation_id),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            "INSERT INTO operation_subscriptions (user_id, operation_id, muted, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, operation_id) DO UPDATE SET muted=excluded.muted, updated_at=excluded.updated_at",
            (user_id, operation_id, int(bool(muted)), created_at, now),
        )
        conn.commit()
    return {"user_id": user_id, "operation_id": operation_id, "muted": int(bool(muted)), "subscribed": True}


def auto_subscribe(user_id: Optional[str], operation_id: Optional[str]) -> None:
    """Subscribe a user to an operation only if they aren't already enrolled.

    Best-effort: used from report-create / SAR-join flows, so it never overrides
    an existing (possibly muted) subscription and never raises.
    """
    if not user_id or not operation_id:
        return
    try:
        with db.get_db() as conn:
            existing = conn.execute(
                "SELECT 1 FROM operation_subscriptions WHERE user_id = ? AND operation_id = ?",
                (user_id, operation_id),
            ).fetchone()
            if existing:
                return
            now = now_iso()
            conn.execute(
                "INSERT INTO operation_subscriptions (user_id, operation_id, muted, created_at, updated_at) "
                "VALUES (?, ?, 0, ?, ?)",
                (user_id, operation_id, now, now),
            )
            conn.commit()
    except Exception:
        pass


def unsubscribe(user_id: str, operation_id: str) -> dict:
    """Remove a subscription entirely (the user leaves the operation's updates)."""
    with db.get_db() as conn:
        cur = conn.execute(
            "DELETE FROM operation_subscriptions WHERE user_id = ? AND operation_id = ?",
            (user_id, operation_id),
        )
        conn.commit()
    return {"ok": True, "removed": cur.rowcount}


def set_muted(user_id: str, operation_id: str, muted: bool) -> dict:
    """Mute / unmute an operation. Subscribes first if not yet enrolled."""
    return subscribe(user_id, operation_id, muted=1 if muted else 0)


def is_subscribed(user_id: str, operation_id: str) -> bool:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM operation_subscriptions WHERE user_id = ? AND operation_id = ?",
            (user_id, operation_id),
        ).fetchone()
    return row is not None


def is_muted(user_id: str, operation_id: Optional[str]) -> bool:
    """True if the user explicitly muted this operation (kept enrolled, silenced)."""
    if not operation_id:
        return False
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT muted FROM operation_subscriptions WHERE user_id = ? AND operation_id = ?",
            (user_id, operation_id),
        ).fetchone()
    return bool(row and row["muted"])


def list_for_user(user_id: str) -> List[dict]:
    """All of a user's subscriptions, newest first."""
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM operation_subscriptions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [db.row_to_dict(r) for r in rows]
