"""Per-record data-quality scoring (plan-13 §4 — Data quality).

Under crisis pressure, records arrive half-filled, unverified, and stale. This
module turns that into an actionable 0-100 score per person, broken into three
sub-scores plus a list of machine-readable issue codes a commander can triage:

  * completeness — how many of the fields that matter for reunification are filled
    (name, contact, location, age, last-seen date, …), weighted.
  * confidence   — trust in the record: its source tier + review status. Rejected
    rows score 0; approved trusted-source rows score full.
  * freshness    — recency of the last update; decays linearly to 0 over
    ``STALE_DAYS`` so a record nobody has touched in a month flags as stale.

Scores are cached in ``data_quality_scores`` (recomputable, never authoritative)
so the dashboard over 10k records doesn't recompute on every request. The
``possible_duplicate`` issue is filled by ``recalculate_all`` which knows the
fuzzy-duplicate cluster membership; a single-record score can be passed the set
explicitly.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

import db
import timeutil
from models import now_iso

# Days of no-update after which a record is considered stale (freshness → 0).
STALE_DAYS = 30

# Sub-score blend weights (sum = 1.0). Completeness dominates because a record
# missing a name/contact is operationally useless regardless of how fresh it is.
_W_COMPLETENESS = 0.5
_W_CONFIDENCE = 0.3
_W_FRESHNESS = 0.2

# Completeness field weights. A name and a way to reach the reporter matter most.
_FIELD_WEIGHTS = {
    "name": 3,            # any of name / given_name+family_name
    "contact": 3,
    "location": 2,        # any of location / last_known_location
    "age": 1,
    "sex": 1,             # any of sex / gender
    "last_seen_date": 1,
    "status": 1,
}

# Source trust tiers for the confidence sub-score. Higher = more trustworthy.
_SOURCE_CONFIDENCE = {
    "self": 100,
    "web": 80,
    "seed": 80,
    "official": 100,
    "witness": 60,
    "csv_import": 50,
    "pfif_import": 50,
    "sms": 40,
    "ai_draft": 30,
    "ocr": 30,
    "synthetic": 50,
}


def _has(row, *keys) -> bool:
    for k in keys:
        v = row[k] if k in row.keys() else None
        if v not in (None, ""):
            return True
    return False


def _completeness(row) -> tuple:
    """Return (score 0-100, list of missing-field issue codes)."""
    earned = 0
    total = sum(_FIELD_WEIGHTS.values())
    issues = []
    checks = {
        "name": ("name", "given_name", "family_name"),
        "contact": ("contact",),
        "location": ("location", "last_known_location"),
        "age": ("age",),
        "sex": ("sex", "gender"),
        "last_seen_date": ("last_seen_date",),
        "status": ("status",),
    }
    for field, keys in checks.items():
        if _has(row, *keys):
            earned += _FIELD_WEIGHTS[field]
        elif field in ("name", "contact", "location"):
            issues.append(f"missing_{field}")
    return round(earned * 100 / total), issues


def _confidence(row) -> tuple:
    """Return (score 0-100, list of issue codes) from source + review status."""
    reviewed = row["reviewed"] if "reviewed" in row.keys() else 0
    if reviewed == -1:
        return 0, ["rejected"]
    base = _SOURCE_CONFIDENCE.get((row["source"] or "web"), 50)
    issues = []
    if reviewed == 1:
        base = min(100, base + 10)
    elif (row["source"] or "web") in ("ocr", "ai_draft", "sms", "csv_import", "pfif_import"):
        issues.append("unreviewed")
    return base, issues


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO-8601 to a tz-aware UTC datetime — delegates to ``timeutil.parse_iso``."""
    dt = timeutil.parse_iso(value)
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _freshness(row, now: Optional[datetime] = None) -> tuple:
    """Return (score 0-100, issue codes) decaying linearly over STALE_DAYS."""
    now = now or datetime.now(timezone.utc)
    updated = _parse_dt(row["updated_at"] if "updated_at" in row.keys() else None)
    if updated is None:
        return 50, []
    age_days = max(0.0, (now - updated).total_seconds() / 86400.0)
    score = max(0, round(100 * (1 - age_days / STALE_DAYS)))
    issues = ["stale"] if age_days >= STALE_DAYS else []
    return score, issues


def score_row(row, duplicate_ids: Optional[set] = None,
              now: Optional[datetime] = None) -> dict:
    """Compute a quality score dict for a single person row (sqlite Row or dict)."""
    comp, comp_issues = _completeness(row)
    conf, conf_issues = _confidence(row)
    fresh, fresh_issues = _freshness(row, now=now)
    issues = comp_issues + conf_issues + fresh_issues
    if duplicate_ids and row["id"] in duplicate_ids:
        issues.append("possible_duplicate")
    overall = round(
        comp * _W_COMPLETENESS + conf * _W_CONFIDENCE + fresh * _W_FRESHNESS
    )
    return {
        "person_id": row["id"],
        "score": overall,
        "completeness": comp,
        "confidence": conf,
        "freshness": fresh,
        "issues": issues,
    }


def _persist(conn, score: dict, now: str) -> None:
    conn.execute(
        "INSERT INTO data_quality_scores "
        "(person_id, score, completeness, confidence, freshness, issues, calculated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(person_id) DO UPDATE SET "
        "score=excluded.score, completeness=excluded.completeness, "
        "confidence=excluded.confidence, freshness=excluded.freshness, "
        "issues=excluded.issues, calculated_at=excluded.calculated_at",
        (
            score["person_id"], score["score"], score["completeness"],
            score["confidence"], score["freshness"], json.dumps(score["issues"]),
            now,
        ),
    )


def score_person(person_id: str) -> dict:
    """Compute, cache and return the quality score for one person (404 if absent)."""
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Person not found")
        dup_ids = _duplicate_member_ids()
        score = score_row(row, duplicate_ids=dup_ids)
        _persist(conn, score, now_iso())
        conn.commit()
    return score


def _duplicate_member_ids() -> set:
    """Ids of every person that appears in a pending fuzzy-duplicate cluster."""
    from modules import duplicates

    ids = set()
    for cluster in duplicates.find_clusters():
        for member in cluster["members"]:
            ids.add(member["id"])
    return ids


def recalculate_all() -> dict:
    """Recompute and cache scores for every live person. Nightly-job entry point.

    Excludes merged duplicates (they are soft-deleted). Computes the fuzzy
    duplicate membership once and reuses it for the ``possible_duplicate`` flag.
    Returns a small summary the CLI / route can report.
    """
    now = now_iso()
    dup_ids = _duplicate_member_ids()
    scored = 0
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM persons WHERE merged_into IS NULL"
        ).fetchall()
        for row in rows:
            _persist(conn, score_row(row, duplicate_ids=dup_ids), now)
            scored += 1
        conn.commit()
    return {"scored": scored, "calculated_at": now, "duplicates_flagged": len(dup_ids)}


def get_score(person_id: str) -> Optional[dict]:
    """Return the cached score for a person, or None if never calculated."""
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM data_quality_scores WHERE person_id = ?", (person_id,)
        ).fetchone()
    if not row:
        return None
    rec = db.row_to_dict(row)
    rec["issues"] = json.loads(rec["issues"] or "[]")
    return rec


def low_quality(threshold: int = 50, limit: int = 100) -> dict:
    """List cached scores at or below ``threshold``, worst first (for triage)."""
    threshold = max(0, min(int(threshold), 100))
    limit = max(1, min(int(limit), 1000))
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT q.*, p.name, p.status, p.source FROM data_quality_scores q "
            "JOIN persons p ON q.person_id = p.id "
            "WHERE q.score <= ? AND p.merged_into IS NULL "
            "ORDER BY q.score ASC LIMIT ?",
            (threshold, limit),
        ).fetchall()
    records = []
    for r in rows:
        rec = db.row_to_dict(r)
        rec["issues"] = json.loads(rec["issues"] or "[]")
        records.append(rec)
    return {"records": records, "count": len(records), "threshold": threshold}


def stale_records(days: int = STALE_DAYS, limit: int = 200) -> dict:
    """Live persons with no update in ``days`` days, flagged for commander review.

    Computed directly from ``persons.updated_at`` (independent of cached scores),
    so it works even before a recalculation has run.
    """
    days = max(1, int(days))
    limit = max(1, min(int(limit), 1000))
    cutoff = _iso_days_ago(days)
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, status, source, disaster_id, updated_at FROM persons "
            "WHERE merged_into IS NULL AND reviewed >= 0 AND updated_at < ? "
            "ORDER BY updated_at ASC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
    return {
        "records": [db.row_to_dict(r) for r in rows],
        "count": len(rows),
        "days": days,
    }


def _iso_days_ago(days: int) -> str:
    from datetime import timedelta

    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace(
        "+00:00", "Z"
    )


def summary() -> dict:
    """Aggregate quality picture for the dashboard: averages + issue histogram."""
    with db.get_db() as conn:
        agg = conn.execute(
            "SELECT COUNT(*) AS n, AVG(score) AS avg_score, "
            "AVG(completeness) AS avg_completeness, AVG(confidence) AS avg_confidence, "
            "AVG(freshness) AS avg_freshness FROM data_quality_scores"
        ).fetchone()
        issue_rows = conn.execute("SELECT issues FROM data_quality_scores").fetchall()
    histogram: dict = {}
    for r in issue_rows:
        for code in json.loads(r["issues"] or "[]"):
            histogram[code] = histogram.get(code, 0) + 1
    return {
        "scored": agg["n"] or 0,
        "avg_score": round(agg["avg_score"], 1) if agg["avg_score"] is not None else None,
        "avg_completeness": round(agg["avg_completeness"], 1) if agg["avg_completeness"] is not None else None,
        "avg_confidence": round(agg["avg_confidence"], 1) if agg["avg_confidence"] is not None else None,
        "avg_freshness": round(agg["avg_freshness"], 1) if agg["avg_freshness"] is not None else None,
        "issues": histogram,
    }
