"""Moderation queue for untrusted records (OCR, AI drafts, PFIF imports, and
any other not-yet-reviewed row).

Trust model via the ``reviewed`` flag:
  reviewed = 0   pending   — awaiting a human decision (default for new rows)
  reviewed = 1   approved  — trusted, visible in public search
  reviewed = -1  rejected  — soft-deleted; hidden everywhere, kept for history

We use ``reviewed = -1`` for rejection rather than a ``status='rejected'`` value
so we don't have to add a status outside the six valid ones (which would mean
touching the db.py CHECK, models.VALID_STATUSES, and ocr.py in lockstep).
"""

import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
from models import now_iso
from modules import audit

# Sources whose records are untrusted until a moderator approves them.
# SMS check-ins are included: a text from an unauthenticated number must stay
# moderator-only until approved.
UNTRUSTED_SOURCES = ("ocr", "ai_draft", "pfif_import", "csv_import", "sms", "whatsapp", "telegram")
REVIEWED_PENDING = 0
REVIEWED_APPROVED = 1
REVIEWED_REJECTED = -1


def list_pending() -> dict:
    """Records awaiting review: anything still ``reviewed = 0`` (this already
    covers every OCR/AI/PFIF import, since they all default to 0). Approved and
    rejected rows have left the queue."""
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM persons WHERE reviewed = ? ORDER BY created_at DESC",
            (REVIEWED_PENDING,),
        ).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


def _set_reviewed(
    record_id: str, value: int, operator: str = "op:anonymous", action: str = "review"
) -> dict:
    now = now_iso()
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE persons SET reviewed = ?, updated_at = ? WHERE id = ?",
            (value, now, record_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
    # Attributable operator action (audit log; best-effort, never blocks).
    audit.log_action(operator, action, "person", record_id, detail=f"reviewed={value}")
    return {"ok": True, "id": record_id, "reviewed": value}


def approve(record_id: str, operator: str = "op:anonymous") -> dict:
    """Mark a record trusted (reviewed=1); it becomes visible in public search."""
    return _set_reviewed(record_id, REVIEWED_APPROVED, operator=operator, action="approve")


def reject(record_id: str, operator: str = "op:anonymous") -> dict:
    """Soft-delete a record (reviewed=-1); hidden from search but kept for history."""
    return _set_reviewed(record_id, REVIEWED_REJECTED, operator=operator, action="reject")


# ── Moderation flags (plan-25 Phase 3) ──────────────────────────────────────
#
# A flag is a *report about* a record (a person record that's wrong/outdated, a
# shelter update that's incorrect, an inappropriate photo) — distinct from the
# ``reviewed`` trust flag, which is the moderation *decision* on a person record.
# Anyone (even offline, synced later) can flag; a remote moderator resolves it.

# Flag reasons that carry a life-safety implication and are escalated.
CRITICAL_REASONS = ("deceased",)
VALID_FLAG_STATUSES = ("open", "resolved", "dismissed")


def create_flag(
    record_type: str,
    record_id: str,
    flag_reason: Optional[str] = None,
    note: Optional[str] = None,
    flagged_by: Optional[str] = None,
    origin_device: Optional[str] = None,
) -> dict:
    """Record a flag against a record. Bumps the flagged record's origin device
    reputation when we can resolve it. ``deceased`` is marked critical."""
    if not (record_type or "").strip() or not (record_id or "").strip():
        raise HTTPException(status_code=400, detail="record_type and record_id are required")
    severity = "critical" if flag_reason in CRITICAL_REASONS else "normal"
    now = now_iso()
    flag_id = "flag-" + uuid.uuid4().hex[:12]
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO moderation_flags (id, record_type, record_id, flag_reason, note, "
            "flagged_by, origin_device, severity, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)",
            (flag_id, record_type, record_id, flag_reason, note, flagged_by,
             origin_device, severity, now, now),
        )
        conn.commit()
    # Penalize the *flagged record's* origin device (not the flagger): a record
    # that draws flags should lose reputation. Best-effort.
    try:
        from modules import device_reputation

        if record_type == "person":
            with db.get_db() as conn:
                row = conn.execute(
                    "SELECT origin_device FROM persons WHERE id = ?", (record_id,)
                ).fetchone()
            if row and row[0]:
                device_reputation.observe_flag(row[0])
    except Exception:
        pass
    audit.log_action(
        flagged_by or "anonymous", "flag_create", record_type, record_id,
        detail=f"reason={flag_reason} severity={severity}",
    )
    return {"id": flag_id, "status": "open", "severity": severity}


def list_flags(
    status: str = "open", record_type: Optional[str] = None, limit: int = 200
) -> dict:
    sql = "SELECT * FROM moderation_flags WHERE 1=1"
    params: list = []
    if status and status != "all":
        sql += " AND status = ?"
        params.append(status)
    if record_type:
        sql += " AND record_type = ?"
        params.append(record_type)
    # Critical (e.g. 'deceased') first, then newest.
    sql += " ORDER BY (severity = 'critical') DESC, created_at DESC LIMIT ?"
    params.append(limit)
    with db.get_db() as conn:
        return {"flags": [db.row_to_dict(r) for r in conn.execute(sql, params).fetchall()]}


def open_flag_counts() -> dict:
    """Map of ``record_id`` → open flag count (so the UI can mark flagged rows)."""
    with db.get_db() as conn:
        return {
            row["record_id"]: row["n"]
            for row in conn.execute(
                "SELECT record_id, COUNT(*) AS n FROM moderation_flags "
                "WHERE status = 'open' GROUP BY record_id"
            ).fetchall()
        }


def resolve_flag(
    flag_id: str,
    status: str,
    resolution: Optional[str] = None,
    reviewed_by: str = "op:anonymous",
) -> dict:
    """Resolve/dismiss a flag. When a person flag resolves to a decision that maps
    onto the reviewed trust flag (``rejected``/``approved``), apply it too."""
    if status not in ("resolved", "dismissed"):
        raise HTTPException(status_code=400, detail="status must be resolved or dismissed")
    now = now_iso()
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT record_type, record_id FROM moderation_flags WHERE id = ?", (flag_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Flag not found")
        record_type, record_id = row["record_type"], row["record_id"]
        conn.execute(
            "UPDATE moderation_flags SET status = ?, resolution = ?, reviewed_by = ?, "
            "updated_at = ? WHERE id = ?",
            (status, resolution, reviewed_by, now, flag_id),
        )
        conn.commit()
    # A resolution can carry a concrete moderation action on a person record.
    if record_type == "person" and status == "resolved":
        if resolution in ("rejected", "removed", "hide"):
            reject(record_id, operator=reviewed_by)
        elif resolution in ("approved", "confirmed"):
            approve(record_id, operator=reviewed_by)
    audit.log_action(
        reviewed_by, "flag_resolve", record_type, record_id,
        detail=f"flag={flag_id} status={status} resolution={resolution}",
    )
    return {"ok": True, "id": flag_id, "status": status, "resolution": resolution}


def flag_stats() -> dict:
    with db.get_db() as conn:
        by_status = {
            row["status"]: row["n"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS n FROM moderation_flags GROUP BY status"
            ).fetchall()
        }
        by_reason = {
            (row["flag_reason"] or "unknown"): row["n"]
            for row in conn.execute(
                "SELECT flag_reason, COUNT(*) AS n FROM moderation_flags GROUP BY flag_reason"
            ).fetchall()
        }
        critical_open = conn.execute(
            "SELECT COUNT(*) FROM moderation_flags WHERE status = 'open' AND severity = 'critical'"
        ).fetchone()[0]
    return {
        "by_status": by_status,
        "by_reason": by_reason,
        "open": by_status.get("open", 0),
        "critical_open": critical_open,
    }


def stats() -> dict:
    """Counts by source and by status, plus pending/approved/rejected totals."""
    with db.get_db() as conn:
        by_source = {
            row["source"] or "unknown": row["n"]
            for row in conn.execute(
                "SELECT source, COUNT(*) AS n FROM persons GROUP BY source"
            ).fetchall()
        }
        by_status = {
            (row["status"] or "unknown"): row["n"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS n FROM persons GROUP BY status"
            ).fetchall()
        }
        review_counts = {
            row["reviewed"]: row["n"]
            for row in conn.execute(
                "SELECT reviewed, COUNT(*) AS n FROM persons GROUP BY reviewed"
            ).fetchall()
        }
    return {
        "by_source": by_source,
        "by_status": by_status,
        "pending": review_counts.get(REVIEWED_PENDING, 0),
        "approved": review_counts.get(REVIEWED_APPROVED, 0),
        "rejected": review_counts.get(REVIEWED_REJECTED, 0),
    }
