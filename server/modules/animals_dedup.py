"""Deduplication for animal records (plan-28 Phase 5).

Animals are a parallel track to persons, so dedup gets its own engine that NEVER
crosses into person records — every merge here only ever touches the ``animals``
table by id. It reuses the dependency-free fuzzy primitives from
``modules/dedup.py`` (phonetic key, edit-distance name ratio) and the id-pair
helpers from ``modules/duplicates.py``, but the matching rules are animal-specific:

  * **Exact**: same microchip/tattoo id, OR the same reporter re-filing the same
    name + species (a common "I reported my dog twice" duplicate).
  * **Fuzzy**: same species (a hard gate — a dog is never a cat) plus a blend of
    name, colour, distinguishing-marks, last-seen location and a time window.

Medium-confidence pairs are surfaced for human review (``find_candidates``);
exact matches can be auto-merged by an operator (``auto_merge_exact``). The actual
merge (``merge_animals``) is a soft, audited pointer-set (``merged_into``) exactly
like the person path, so it stays reversible — and it asserts both ids are animals
so a merge can never cross registries. Rejected pairs are remembered in the shared
``dedup_rejections`` id-pair table (animal ids are a distinct ``animal-*`` namespace
so they never collide with person pairs).
"""

import re
from datetime import timedelta
from typing import Optional

from fastapi import HTTPException

import db
from models import now_iso
from modules import audit
from modules.dedup import name_ratio, phonetic_key
from modules.duplicates import _norm, _pair_key, _parse_dt, _rejected_pairs

MEDIUM_THRESHOLD = 0.55
HIGH_THRESHOLD = 0.85
TIME_WINDOW_HOURS = 48

# Blend weights for the fuzzy score (sum = 1.0). Name + colour dominate; markings,
# location and time are corroborating signals.
_W_NAME = 0.40
_W_COLOR = 0.20
_W_MARKS = 0.15
_W_LOCATION = 0.15
_W_TIME = 0.10


def normalize_microchip(value: Optional[str]) -> str:
    """Canonical microchip/tattoo key: alphanumeric only, uppercased. A 15-digit
    ISO chip arrives with spaces/dashes across reports; strip them so they match."""
    if not value:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


# ── Pair scoring ──────────────────────────────────────────────────────────────


def score_pair(a, b) -> tuple:
    """Composite duplicate confidence (0-1) + reason codes for two animal rows.

    Microchip equality short-circuits to ~certain. Species is a HARD gate: two
    rows of different species are never the same animal (returns 0). Without a
    real descriptive signal (name/colour/marks) a mere same-species + same-place
    coincidence is damped so it can't masquerade as a match.
    """
    ma, mb = normalize_microchip(_get(a, "microchip")), normalize_microchip(_get(b, "microchip"))
    if ma and mb and ma == mb:
        return 0.99, ["same_microchip"]

    sa, sb = _norm(_get(a, "species")), _norm(_get(b, "species"))
    # Different known species → definitely not the same animal.
    if sa and sb and sa != sb:
        return 0.0, []
    species_match = bool(sa) and sa == sb
    if not species_match:
        # No reliable species on at least one side: too weak to cluster animals.
        return 0.0, []

    reasons: list = ["same_species"]

    na, nb = _norm(_get(a, "name")), _norm(_get(b, "name"))
    ra, rb = _get(a, "reporter_id"), _get(b, "reporter_id")
    # Same owner re-filing the same pet (name + species + reporter) — near certain.
    if ra and rb and ra == rb and na and nb and na == nb:
        return 0.97, ["same_reporter_name_species"]

    name_score = 0.0
    if na and nb:
        nr = name_ratio(na, nb)
        phon = phonetic_key(_get(a, "name")) == phonetic_key(_get(b, "name"))
        if nr >= 0.95:
            name_score = 1.0
            reasons.append("same_name")
        elif phon or nr >= 0.82:
            name_score = 0.7
            reasons.append("similar_name")

    color_score = 0.0
    ca, cb = _norm(_get(a, "color")), _norm(_get(b, "color"))
    if ca and cb and ca == cb:
        color_score = 1.0
        reasons.append("same_color")

    marks_score = 0.0
    ka, kb = _norm(_get(a, "distinguishing_marks")), _norm(_get(b, "distinguishing_marks"))
    if ka and kb and name_ratio(ka, kb) >= 0.7:
        marks_score = 1.0
        reasons.append("similar_marks")

    loc_score = 0.0
    la, lb = _norm(_get(a, "last_seen_location")), _norm(_get(b, "last_seen_location"))
    if la and lb and la == lb:
        loc_score = 1.0
        reasons.append("same_location")

    time_score = 0.0
    da, dbt = _parse_dt(_get(a, "last_seen_at")), _parse_dt(_get(b, "last_seen_at"))
    if da is not None and dbt is not None and abs(da - dbt) <= timedelta(hours=TIME_WINDOW_HOURS):
        time_score = 1.0
        reasons.append("same_time_window")

    confidence = (
        name_score * _W_NAME
        + color_score * _W_COLOR
        + marks_score * _W_MARKS
        + loc_score * _W_LOCATION
        + time_score * _W_TIME
    )
    # Collision guard: same-species + same-place with no name/colour/marks is a
    # weak coincidence, not a duplicate. Damp it below the review threshold.
    if name_score == 0 and color_score == 0 and marks_score == 0:
        confidence *= 0.4
    return round(confidence, 3), reasons


def _get(row, key):
    try:
        return row[key] if key in row.keys() else None
    except AttributeError:
        return row.get(key)


def _tier_for(confidence: float, reasons: list) -> str:
    if "same_microchip" in reasons or "same_reporter_name_species" in reasons or confidence >= 0.95:
        return "exact"
    if confidence >= HIGH_THRESHOLD:
        return "strong"
    return "fuzzy"


# ── Review queue (on-the-fly, like duplicates.py for persons) ────────────────


def find_candidates(disaster_id: Optional[str] = None,
                    min_confidence: float = MEDIUM_THRESHOLD,
                    limit: int = 200) -> dict:
    """Score every live animal pair and return those above ``min_confidence`` for
    human review. Skips moderator-rejected pairs. Highest confidence first."""
    sql = "SELECT * FROM animals WHERE merged_into IS NULL AND reviewed != -1"
    params: list = []
    if disaster_id:
        sql += " AND disaster_id = ?"
        params.append(disaster_id)
    sql += " ORDER BY created_at ASC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        rejected = _rejected_pairs(conn)
    out = []
    n = len(rows)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = rows[i], rows[j]
            if _pair_key(a["id"], b["id"]) in rejected:
                continue
            confidence, reasons = score_pair(a, b)
            if confidence < min_confidence:
                continue
            out.append({
                "confidence": confidence,
                "tier": _tier_for(confidence, reasons),
                "reasons": reasons,
                "animal_a": db.row_to_dict(a),
                "animal_b": db.row_to_dict(b),
            })
    out.sort(key=lambda c: c["confidence"], reverse=True)
    return {"candidates": out[: max(1, min(limit, 1000))], "count": len(out)}


def reject_pair(a_id: str, b_id: str, operator: str = "op:anonymous") -> dict:
    """Record a moderator decision that two animals are NOT duplicates so the pair
    is never re-suggested. Uses the shared id-pair rejection table."""
    a, b = _pair_key(a_id, b_id)
    now = now_iso()
    with db.get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO dedup_rejections (id_a, id_b, created_at) VALUES (?, ?, ?)",
            (a, b, now),
        )
        conn.commit()
    audit.log_action(operator, "animal_reject_candidate", "animal", a, detail=f"not_duplicate={b}")
    return {"ok": True, "rejected": [a, b]}


# ── Merge (animal-only, soft + audited + reversible) ─────────────────────────


def merge_animals(canonical_id: str, duplicate_id: str, operator: str = "op:anonymous") -> dict:
    """Soft-merge one animal into another (sets ``merged_into`` on the duplicate,
    bumps ``updated_at`` so the merge wins LWW and propagates over the mesh).

    Asserts BOTH ids are animal records, so a merge can never cross into a person
    record. Reversible: the duplicate row is kept, just pointed at the canonical."""
    if canonical_id == duplicate_id:
        raise HTTPException(status_code=400, detail="cannot merge an animal into itself")
    now = now_iso()
    with db.get_db() as conn:
        for x in (canonical_id, duplicate_id):
            if not conn.execute("SELECT 1 FROM animals WHERE id = ?", (x,)).fetchone():
                raise HTTPException(status_code=404, detail=f"animal not found: {x}")
        conn.execute(
            "UPDATE animals SET merged_into = ?, updated_at = ? WHERE id = ?",
            (canonical_id, now, duplicate_id),
        )
        conn.commit()
    audit.log_action(
        operator, "animal_merge", "animal", canonical_id,
        detail=f"merged={duplicate_id}",
    )
    return {"ok": True, "canonical_id": canonical_id, "merged": [duplicate_id]}


def auto_merge_exact(disaster_id: Optional[str] = None,
                     operator: str = "op:anonymous") -> dict:
    """Auto-merge only the EXACT animal duplicates: same microchip, or same
    reporter+name+species. The earliest-created row in each group is the canonical;
    the rest are soft-merged into it. Fuzzy matches are left for human review."""
    sql = "SELECT * FROM animals WHERE merged_into IS NULL AND reviewed != -1"
    params: list = []
    if disaster_id:
        sql += " AND disaster_id = ?"
        params.append(disaster_id)
    sql += " ORDER BY created_at ASC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    # Group by an exact key: microchip wins, else reporter+name+species.
    groups: dict = {}
    for r in rows:
        chip = normalize_microchip(r["microchip"])
        if chip:
            key = f"chip:{chip}"
        elif r["reporter_id"] and _norm(r["name"]) and _norm(r["species"]):
            key = f"rns:{r['reporter_id']}|{_norm(r['name'])}|{_norm(r['species'])}"
        else:
            continue
        groups.setdefault(key, []).append(r)

    merged = 0
    canonicals = 0
    for key, members in groups.items():
        if len(members) < 2:
            continue
        canonical = members[0]["id"]  # earliest created (rows sorted ASC)
        canonicals += 1
        for dup in members[1:]:
            merge_animals(canonical, dup["id"], operator=operator)
            merged += 1
    return {"merged": merged, "groups": canonicals}
