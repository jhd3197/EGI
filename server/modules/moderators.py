"""Remote moderators & diaspora onboarding (plan-25 Phase 4).

A moderator is a (usually diaspora) volunteer who signs up to review flagged
content from anywhere with internet. Onboarding records the languages and
regions they cover so their queue can be scoped; ``trained`` flips once they've
seen the training example. The queue is the open flags + pending untrusted
records they should look at.

Signup is bound to a real user account (require_user). An optional ``invite_token``
is accepted for invite-gated deployments; it is recorded for audit but not
required, so a community server can run open moderation.
"""

import json
from typing import List, Optional

from fastapi import HTTPException

import db
from models import now_iso


def _json_list(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _decode(row: dict) -> dict:
    for key in ("languages", "regions"):
        raw = row.get(key)
        if isinstance(raw, str):
            try:
                row[key] = json.loads(raw)
            except (ValueError, TypeError):
                row[key] = []
        elif raw is None:
            row[key] = []
    return row


def signup(
    user_id: str,
    display_name: Optional[str] = None,
    languages: Optional[List[str]] = None,
    regions: Optional[List[str]] = None,
) -> dict:
    now = now_iso()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO moderators (user_id, display_name, languages, regions, "
            "trained, active, created_at, updated_at) VALUES (?, ?, ?, ?, 0, 1, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET display_name = excluded.display_name, "
            "languages = excluded.languages, regions = excluded.regions, "
            "active = 1, updated_at = excluded.updated_at",
            (user_id, display_name, _json_list(languages), _json_list(regions), now, now),
        )
        conn.commit()
    return get(user_id)


def get(user_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM moderators WHERE user_id = ?", (user_id,)
        ).fetchone()
        return _decode(db.row_to_dict(row)) if row else None


def list_moderators(active_only: bool = True) -> List[dict]:
    sql = "SELECT * FROM moderators"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        return [_decode(db.row_to_dict(r)) for r in conn.execute(sql).fetchall()]


def mark_trained(user_id: str) -> dict:
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE moderators SET trained = 1, updated_at = ? WHERE user_id = ?",
            (now_iso(), user_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not a moderator")
        conn.commit()
    return get(user_id)


def queue(user_id: str, limit: int = 50) -> dict:
    """The work a moderator should review: open flags (critical first) + a slice
    of pending untrusted records. Scoped by the moderator's regions when set."""
    from modules import moderation

    mod = get(user_id)
    regions = (mod or {}).get("regions") or []
    flags = moderation.list_flags(status="open", limit=limit)["flags"]
    pending = moderation.list_pending()["records"]
    # Region scoping: a moderator who picked regions only sees pending records in
    # those disasters; an unscoped moderator sees everything.
    if regions:
        pending = [r for r in pending if r.get("disaster_id") in regions]
    return {
        "flags": flags,
        "pending": pending[:limit],
        "counts": {"flags": len(flags), "pending": len(pending)},
    }


def digest() -> dict:
    """Queue-size snapshot for the moderator digest (plan-25 Phase 4). The
    delivery (email/push) is driven by the CLI/cron; this returns the numbers."""
    from modules import moderation

    fstats = moderation.flag_stats()
    pstats = moderation.stats()
    return {
        "open_flags": fstats.get("open", 0),
        "critical_flags": fstats.get("critical_open", 0),
        "pending_records": pstats.get("pending", 0),
        "moderators": len(list_moderators(active_only=True)),
    }
