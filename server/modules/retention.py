"""Data retention and anonymization (plan-07 §11).

Crisis data should not live forever. Two operator tools:

  * ``list_past_retention`` — records eligible for review: those with an explicit
    ``retained_until`` in the past, and (optionally) records older than N days
    that were never given a retention date.
  * ``anonymize_records`` — strip PII (names, cédula, contacts, free text,
    photos) from a record while keeping the aggregate-safe fields (status,
    disaster, coarse demographics) so status counts survive.

Anonymization is irreversible by design and is logged to ``record_history``.
Already-anonymized rows are marked via ``provenance`` so they aren't re-listed.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import db
from models import now_iso
from modules import audit

ANONYMIZED_MARKER = "anonymized"

# Fields wiped on anonymization. Everything identifying or free-text goes; the
# remaining columns (status, disaster_id, gender, age, source, timestamps) are
# coarse enough to keep for aggregate statistics.
_PII_FIELDS = (
    "name", "given_name", "family_name", "cedula", "contact",
    "reporter_name", "reporter_relation", "reporter_country", "reported_by",
    "notes", "clothes", "location", "last_known_location", "last_seen_date",
    "image_path", "photo_url", "ocr_text", "extracted_json",
)


def _cutoff(reference_iso: str, older_than_days: int) -> str:
    try:
        ref = datetime.fromisoformat(reference_iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        ref = datetime.now(timezone.utc)
    return (ref - timedelta(days=older_than_days)).isoformat()


def list_past_retention(
    reference_iso: Optional[str] = None,
    older_than_days: Optional[int] = None,
) -> List[dict]:
    """Records eligible for retention review.

    Always includes rows whose ``retained_until`` is set and already in the past.
    If ``older_than_days`` is given, also includes rows with no retention date
    whose ``created_at`` is older than that cutoff. Anonymized rows are excluded.
    """
    reference_iso = reference_iso or now_iso()
    clauses = ["retained_until IS NOT NULL AND retained_until < ?"]
    params: list = [reference_iso]
    if older_than_days is not None:
        clauses.append("(retained_until IS NULL AND created_at < ?)")
        params.append(_cutoff(reference_iso, older_than_days))
    where = " OR ".join(f"({c})" for c in clauses)
    sql = (
        f"SELECT * FROM persons WHERE ({where}) "
        "AND (provenance IS NULL OR provenance NOT LIKE ?) "
        "ORDER BY created_at ASC"
    )
    params.append(f"{ANONYMIZED_MARKER}%")
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [db.row_to_dict(r) for r in rows]


def anonymize_records(ids: List[str], actor: str = "retention") -> dict:
    """Strip PII from the given records, keeping aggregate-safe fields.

    Returns a summary; logs each anonymization to record_history. Records already
    marked anonymized are skipped.
    """
    now = now_iso()
    anonymized = 0
    set_clause = ", ".join(f"{f} = NULL" for f in _PII_FIELDS)
    with db.get_db() as conn:
        cur = conn.cursor()
        for rec_id in ids:
            row = cur.execute(
                "SELECT provenance FROM persons WHERE id = ?", (rec_id,)
            ).fetchone()
            if row is None:
                continue
            if row["provenance"] and row["provenance"].startswith(ANONYMIZED_MARKER):
                continue
            cur.execute(
                f"UPDATE persons SET {set_clause}, provenance = ?, updated_at = ? "
                "WHERE id = ?",
                (f"{ANONYMIZED_MARKER} {now}", now, rec_id),
            )
            anonymized += cur.rowcount or 0
        conn.commit()

    for rec_id in ids:
        audit.log_history(rec_id, "anonymize", actor=actor)
    return {"anonymized": anonymized, "requested": len(ids)}
