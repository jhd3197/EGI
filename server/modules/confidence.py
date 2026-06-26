"""Confidence-based status derivation.

A person's *stored* status is whatever their record says, but their *displayed*
status should reflect the best available evidence from their reports. We rank
each report by a confidence tier and recency, and the highest-confidence latest
report with a status wins.

Confidence tiers (highest → lowest):
  - self     : the person's own check-in (most trustworthy).
  - official : hospital, rescuer, authority.
  - witness  : someone saw the person (the default for ad-hoc reports).
  - ocr      : extracted from paper, unreviewed (least trustworthy).

This is computed on the fly and exposed as a read-only ``derived_status`` field;
it never mutates the stored ``status``.
"""

from typing import Optional

import db
from models import normalize_ts

# Lower rank = higher confidence.
CONFIDENCE_RANK = {"self": 0, "official": 1, "witness": 2, "ocr": 3}
# Reports without an explicit confidence are treated as eyewitness-level.
DEFAULT_CONFIDENCE = "witness"


def _rank(confidence: Optional[str]) -> int:
    return CONFIDENCE_RANK.get(confidence or DEFAULT_CONFIDENCE, CONFIDENCE_RANK[DEFAULT_CONFIDENCE])


def derive_status(reports: list, fallback: Optional[str]) -> Optional[str]:
    """Pick the status from the highest-confidence, latest report.

    Only reports that actually assert a status participate (a plain note with no
    status doesn't change the displayed status). Ordering key, applied as a sort
    so the winner is first:
      1. confidence rank ascending (self beats official beats witness beats ocr),
      2. updated_at descending (newer wins within the same tier),
      3. id descending (deterministic tie-break when rank AND timestamp are equal).
    Falls back to the person's stored status when no report carries a status.
    """
    scored = [_as_dict(r) for r in reports if _as_dict(r).get("status")]
    if not scored:
        return fallback

    # Python's sort is stable, so successive sorts compose: the LAST sort is the
    # primary key. Apply weakest tie-breaks first, strongest last.
    scored.sort(key=lambda r: (r.get("id") or ""), reverse=True)            # id desc
    scored.sort(key=lambda r: normalize_ts(r.get("updated_at")) or "", reverse=True)  # updated_at desc
    scored.sort(key=lambda r: _rank(r.get("confidence")))                  # rank asc (primary)
    return scored[0].get("status")


def _as_dict(r) -> dict:
    return r if isinstance(r, dict) else db.row_to_dict(r)


def derived_status_for(person_id: str, fallback: Optional[str]) -> Optional[str]:
    """Derive one person's status from their reports (single-record convenience)."""
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT id, status, confidence, updated_at FROM reports WHERE person_id = ?",
            (person_id,),
        ).fetchall()
        return derive_status([db.row_to_dict(r) for r in rows], fallback)


def derived_status_map(conn, person_ids: list) -> dict:
    """Batch-derive statuses for many persons in one query (avoids N+1).

    Returns {person_id: derived_status_or_None}. Callers pass their own connection
    so this composes inside an existing search transaction.
    """
    if not person_ids:
        return {}
    placeholders = ",".join("?" * len(person_ids))
    rows = conn.execute(
        f"SELECT id, person_id, status, confidence, updated_at FROM reports"
        f" WHERE person_id IN ({placeholders})",
        person_ids,
    ).fetchall()
    grouped: dict = {pid: [] for pid in person_ids}
    for r in rows:
        grouped.setdefault(r["person_id"], []).append(db.row_to_dict(r))
    # fallback is filled in by the caller (it has the person's stored status).
    return {pid: derive_status(reps, None) for pid, reps in grouped.items()}
