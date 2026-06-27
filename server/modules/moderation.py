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
