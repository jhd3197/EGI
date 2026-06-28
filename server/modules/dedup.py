"""Fuzzy matching engine + conflict resolution (plan-27 Phases 2 & 4).

Where ``modules/duplicates.py`` does coarse tier-based clustering for the live
review queue, this module adds:

  * **Phonetic + edit-distance name matching** tuned for Spanish/Portuguese
    (``phonetic_key`` — a hand-rolled, dependency-free key so "González" /
    "Gonzales" / "Gonzáles" collapse, like the rest of EGI avoids new runtime
    deps).
  * **Composite confidence scoring** (``score_pair``) blending name, age,
    location and time-window signals into a 0-1 score plus machine-readable
    reason codes (``same_cedula``, ``similar_name``, ``same_age``, …).
  * **Persisted merge candidates** (``generate_candidates``) in the
    ``merge_candidates`` table so the review queue is stable across recomputes and
    a reviewer's decision sticks.
  * **Conflict resolution** (``resolve_conflicts`` / ``can_override_status``):
    when two sources disagree on a field, pick the value from the higher-trust
    source (newer wins on a tie) and keep the losing values so nothing is silently
    overwritten. Life-critical statuses (``found``/``deceased``) cannot be set by
    low-trust data.

Nothing here ever auto-merges: the actual merge still flows through
``duplicates.merge_cluster`` (soft, audited, webhook-emitting). This module only
*scores* and *surfaces*.
"""

import hashlib
import json
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

import db
from models import now_iso
from modules.duplicates import (
    _full_name,
    _norm,
    _pair_key,
    _parse_dt,
    _rejected_pairs,
    normalize_cedula,
    normalize_phone,
)

# Confidence bands. A pair scoring below MEDIUM is not worth a moderator's time;
# at/above HIGH it's a near-certain match (still human-reviewed in a crisis).
MEDIUM_THRESHOLD = 0.55
HIGH_THRESHOLD = 0.85

AGE_TOLERANCE_YEARS = 2
LOCATION_TIME_WINDOW_HOURS = 24

# Sub-score blend weights for the composite confidence (sum = 1.0). Name
# dominates: two records with the same name + age are far likelier the same
# person than two that merely share a city.
_W_NAME = 0.55
_W_AGE = 0.20
_W_LOCATION = 0.15
_W_TIME = 0.10


# ── Spanish/Portuguese phonetic key ──────────────────────────────────────────

def _strip(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return no_accents.upper()


def phonetic_key(name: Optional[str]) -> str:
    """A phonetic key for a (Spanish/Portuguese) name.

    Folds the spelling variants that sound identical in Spanish so homophones
    match: B↔V, Z/soft-C↔S, silent H, LL↔Y, QU↔K, GE/GI↔J, double letters, etc.
    Not a full Double Metaphone — deliberately small and dependency-free, tuned
    for the names EGI actually sees. Returns a space-joined per-word key.
    """
    if not name:
        return ""
    words = _strip(name).split()
    keys = []
    for w in words:
        chars = [c for c in w if c.isalpha()]
        out = []
        i = 0
        n = len(chars)
        while i < n:
            c = chars[i]
            nxt = chars[i + 1] if i + 1 < n else ""
            if c == "H":              # silent
                i += 1
                continue
            if c == "L" and nxt == "L":   # LL → Y
                out.append("Y")
                i += 2
                continue
            if c == "C" and nxt == "H":   # CH (kept distinct)
                out.append("X")
                i += 2
                continue
            if c == "Q":                  # QU → K (U silent)
                out.append("K")
                i += 2 if nxt == "U" else 1
                continue
            if c == "G" and nxt == "U" and (chars[i + 2] if i + 2 < n else "") in ("E", "I"):
                out.append("G")          # GUE/GUI → hard G, U silent
                i += 2
                continue
            if c == "C":
                out.append("S" if nxt in ("E", "I") else "K")
                i += 1
                continue
            if c == "G":
                out.append("J" if nxt in ("E", "I") else "G")
                i += 1
                continue
            if c == "Z":
                out.append("S")
                i += 1
                continue
            if c in ("V", "W"):
                out.append("B")
                i += 1
                continue
            if c == "Y":
                # Treat as a vowel I when alone/at end, else consonant Y.
                out.append("I" if (i == n - 1 or not nxt) else "Y")
                i += 1
                continue
            out.append(c)
            i += 1
        # Collapse consecutive duplicates (gonzaalez → gonzalez sound).
        collapsed = []
        for ch in out:
            if not collapsed or collapsed[-1] != ch:
                collapsed.append(ch)
        keys.append("".join(collapsed))
    return " ".join(k for k in keys if k)


# ── Edit distance ─────────────────────────────────────────────────────────────

def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(
                prev[j] + 1,
                cur[j - 1] + 1,
                prev[j - 1] + (0 if ca == cb else 1),
            ))
        prev = cur
    return prev[-1]


def name_ratio(a: str, b: str) -> float:
    """Normalized similarity 0-1 of two strings (1 = identical)."""
    if not a or not b:
        return 0.0
    longest = max(len(a), len(b))
    return 1.0 - _levenshtein(a, b) / longest if longest else 0.0


# ── Composite pair scoring ────────────────────────────────────────────────────

def _age(row) -> Optional[int]:
    v = row["age"] if _has(row, "age") else None
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _has(row, key) -> bool:
    try:
        return key in row.keys()
    except AttributeError:
        return key in row


def _get(row, key):
    try:
        return row[key] if key in row.keys() else None
    except AttributeError:
        return row.get(key)


def score_pair(a, b) -> tuple:
    """Composite duplicate confidence (0-1) + reason codes for two person rows.

    The score blends name (phonetic + edit-distance), age proximity, location
    equality and last-seen time window. A shared cédula short-circuits to ~certain.
    Pairs with no real name signal are damped to avoid age/city collisions
    (plan-27 §5.4 — same-city-only must NOT look like a match).
    """
    reasons: list = []

    ca, cb = normalize_cedula(_get(a, "cedula")), normalize_cedula(_get(b, "cedula"))
    if ca and cb and ca == cb:
        return 0.99, ["same_cedula"]

    na, nb = _full_name(a), _full_name(b)
    nr = name_ratio(na, nb) if na and nb else 0.0
    pa, pb = phonetic_key(na), phonetic_key(nb)
    phonetic = bool(pa) and pa == pb

    name_score = 0.0
    if na and nb:
        if nr >= 0.95:
            name_score = 1.0
            reasons.append("same_name")
        elif phonetic or nr >= 0.82:
            name_score = 0.78
            reasons.append("similar_name")
        elif nr >= 0.6:
            name_score = 0.4

    pha, phb = normalize_phone(_get(a, "contact")), normalize_phone(_get(b, "contact"))
    if pha and phb and pha == phb:
        reasons.append("same_phone")
        name_score = max(name_score, 0.85)

    age_score = 0.0
    aa, ab = _age(a), _age(b)
    if aa is not None and ab is not None:
        d = abs(aa - ab)
        if d == 0:
            age_score, _ = 1.0, reasons.append("same_age")
        elif d <= AGE_TOLERANCE_YEARS:
            age_score, _ = 0.7, reasons.append("similar_age")
        elif d <= 5:
            age_score = 0.3

    loc_score = 0.0
    la = _norm(_get(a, "last_known_location")) or _norm(_get(a, "location"))
    lb = _norm(_get(b, "last_known_location")) or _norm(_get(b, "location"))
    if la and lb and la == lb:
        loc_score, _ = 1.0, reasons.append("same_location")

    time_score = 0.0
    da, dbt = _parse_dt(_get(a, "last_seen_date")), _parse_dt(_get(b, "last_seen_date"))
    if da is not None and dbt is not None and abs(da - dbt) <= timedelta(
        hours=LOCATION_TIME_WINDOW_HOURS
    ):
        time_score, _ = 1.0, reasons.append("same_time_window")

    confidence = (
        name_score * _W_NAME
        + age_score * _W_AGE
        + loc_score * _W_LOCATION
        + time_score * _W_TIME
    )
    # Collision guard (plan-27 §5.4): without a real name OR phone signal, a high
    # age+location score is a weak coincidence, not a duplicate. Damp it.
    if name_score < 0.4 and "same_phone" not in reasons:
        confidence *= 0.5
    return round(confidence, 3), reasons


def _tier_for(confidence: float, reasons: list) -> str:
    if "same_cedula" in reasons or confidence >= 0.95:
        return "exact"
    if confidence >= HIGH_THRESHOLD:
        return "strong"
    return "fuzzy"


# ── Candidate persistence ─────────────────────────────────────────────────────

def _candidate_id(a_id: str, b_id: str) -> str:
    a, b = _pair_key(a_id, b_id)
    digest = hashlib.sha1(f"{a},{b}".encode("utf-8"), usedforsecurity=False)
    return "mc-" + digest.hexdigest()[:12]


def generate_candidates(min_confidence: float = MEDIUM_THRESHOLD) -> dict:
    """Score every live person pair and upsert those above ``min_confidence``.

    Skips moderator-rejected pairs. Re-running updates the score/reasons of an
    existing *pending* candidate but never resurrects one a reviewer already
    resolved (merged / not_match / needs_info). Entry point for the nightly job.
    """
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM persons WHERE merged_into IS NULL ORDER BY created_at ASC"
        ).fetchall()
        rejected = _rejected_pairs(conn)

    now = now_iso()
    created = updated = 0
    n = len(rows)
    with db.get_db() as conn:
        cur = conn.cursor()
        for i in range(n):
            for j in range(i + 1, n):
                a, b = rows[i], rows[j]
                pair = _pair_key(a["id"], b["id"])
                if pair in rejected:
                    continue
                confidence, reasons = score_pair(a, b)
                if confidence < min_confidence:
                    continue
                cid = _candidate_id(a["id"], b["id"])
                tier = _tier_for(confidence, reasons)
                existing = cur.execute(
                    "SELECT status FROM merge_candidates WHERE id = ?", (cid,)
                ).fetchone()
                if existing is None:
                    cur.execute(
                        "INSERT INTO merge_candidates "
                        "(id, person_a_id, person_b_id, confidence, tier, reasons, "
                        " status, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                        (cid, pair[0], pair[1], confidence, tier,
                         json.dumps(reasons), now, now),
                    )
                    created += 1
                elif existing["status"] == "pending":
                    cur.execute(
                        "UPDATE merge_candidates SET confidence = ?, tier = ?, "
                        "reasons = ?, updated_at = ? WHERE id = ?",
                        (confidence, tier, json.dumps(reasons), now, cid),
                    )
                    updated += 1
        conn.commit()
    return {"created": created, "updated": updated, "scanned_pairs": n * (n - 1) // 2}


def generate_candidates_for(person_id: str,
                            min_confidence: float = MEDIUM_THRESHOLD) -> dict:
    """Score one person against all other live persons; upsert matches.

    Used right after an OCR/SMS record is created (plan-27 Phase 5) so a new
    untrusted record is matched against the registry before a moderator sees it.
    Best-effort and cheap (one row vs. N), never auto-merges.
    """
    with db.get_db() as conn:
        target = conn.execute(
            "SELECT * FROM persons WHERE id = ? AND merged_into IS NULL", (person_id,)
        ).fetchone()
        if target is None:
            return {"created": 0, "updated": 0}
        others = conn.execute(
            "SELECT * FROM persons WHERE merged_into IS NULL AND id != ?", (person_id,)
        ).fetchall()
        rejected = _rejected_pairs(conn)

    now = now_iso()
    created = updated = 0
    with db.get_db() as conn:
        cur = conn.cursor()
        for other in others:
            pair = _pair_key(person_id, other["id"])
            if pair in rejected:
                continue
            confidence, reasons = score_pair(target, other)
            if confidence < min_confidence:
                continue
            cid = _candidate_id(person_id, other["id"])
            tier = _tier_for(confidence, reasons)
            existing = cur.execute(
                "SELECT status FROM merge_candidates WHERE id = ?", (cid,)
            ).fetchone()
            if existing is None:
                cur.execute(
                    "INSERT INTO merge_candidates "
                    "(id, person_a_id, person_b_id, confidence, tier, reasons, "
                    " status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                    (cid, pair[0], pair[1], confidence, tier,
                     json.dumps(reasons), now, now),
                )
                created += 1
            elif existing["status"] == "pending":
                cur.execute(
                    "UPDATE merge_candidates SET confidence = ?, tier = ?, "
                    "reasons = ?, updated_at = ? WHERE id = ?",
                    (confidence, tier, json.dumps(reasons), now, cid),
                )
                updated += 1
        conn.commit()
    return {"created": created, "updated": updated}


def _candidate_to_dict(row) -> dict:
    rec = db.row_to_dict(row)
    rec["reasons"] = json.loads(rec.get("reasons") or "[]")
    return rec


def list_candidates(status: str = "pending", limit: int = 200) -> dict:
    """List persisted merge candidates with both person records inlined.

    Highest confidence first so a reviewer triages the near-certain pairs before
    the borderline ones. Skips candidates whose member records were since merged.
    """
    limit = max(1, min(int(limit), 1000))
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM merge_candidates WHERE status = ? "
            "ORDER BY confidence DESC, created_at ASC LIMIT ?",
            (status, limit),
        ).fetchall()
        out = []
        for r in rows:
            rec = _candidate_to_dict(r)
            a = conn.execute(
                "SELECT * FROM persons WHERE id = ?", (rec["person_a_id"],)
            ).fetchone()
            b = conn.execute(
                "SELECT * FROM persons WHERE id = ?", (rec["person_b_id"],)
            ).fetchone()
            # Drop stale candidates whose records were removed or already merged.
            if not a or not b or a["merged_into"] or b["merged_into"]:
                continue
            rec["person_a"] = db.row_to_dict(a)
            rec["person_b"] = db.row_to_dict(b)
            rec["conflicts"] = resolve_conflicts([rec["person_a"], rec["person_b"]])
            out.append(rec)
    return {"candidates": out, "count": len(out), "status": status}


def get_candidate(candidate_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM merge_candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="candidate not found")
        rec = _candidate_to_dict(row)
        a = conn.execute("SELECT * FROM persons WHERE id = ?", (rec["person_a_id"],)).fetchone()
        b = conn.execute("SELECT * FROM persons WHERE id = ?", (rec["person_b_id"],)).fetchone()
    rec["person_a"] = db.row_to_dict(a) if a else None
    rec["person_b"] = db.row_to_dict(b) if b else None
    if rec["person_a"] and rec["person_b"]:
        rec["conflicts"] = resolve_conflicts([rec["person_a"], rec["person_b"]])
    return rec


def resolve_candidate(candidate_id: str, decision: str, canonical_id: str = None,
                      note: str = None, operator: str = "op:anonymous") -> dict:
    """Apply a reviewer decision to a candidate (plan-27 Phase 3).

    ``decision``:
      * ``merge``      — soft-merge via duplicates.merge_cluster (needs canonical_id).
      * ``not_match``  — record a dedup_rejection so the pair is never re-suggested.
      * ``needs_info`` — park the candidate for field verification.
    """
    from modules import audit

    cand = get_candidate(candidate_id)
    a_id, b_id = cand["person_a_id"], cand["person_b_id"]
    now = now_iso()

    if decision == "merge":
        canonical = canonical_id or a_id
        if canonical not in (a_id, b_id):
            raise HTTPException(status_code=400, detail="canonical_id not in candidate")
        dup = b_id if canonical == a_id else a_id
        # The fuzzy clusterer may no longer surface this exact pair, so merge the
        # pair directly via the same soft-merge primitive (audited + reversible).
        result = _merge_pair(canonical, dup, operator)
        _set_status(candidate_id, "merged", operator,
                    resolution=f"canonical={canonical}", now=now)
        audit.log_action(operator, "merge_candidate", "person", canonical,
                         detail=f"candidate={candidate_id} merged={dup}")
        return {"ok": True, "decision": "merge", **result}

    if decision == "not_match":
        a, b = _pair_key(a_id, b_id)
        with db.get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO dedup_rejections (id_a, id_b, created_at) "
                "VALUES (?, ?, ?)", (a, b, now))
            conn.commit()
        _set_status(candidate_id, "not_match", operator, resolution=note, now=now)
        audit.log_action(operator, "reject_candidate", "merge_candidate",
                         candidate_id, detail="not_a_duplicate")
        return {"ok": True, "decision": "not_match"}

    if decision == "needs_info":
        _set_status(candidate_id, "needs_info", operator, resolution=note, now=now)
        audit.log_action(operator, "flag_candidate", "merge_candidate",
                         candidate_id, detail=note or "needs_info")
        return {"ok": True, "decision": "needs_info"}

    raise HTTPException(status_code=400, detail=f"unknown decision: {decision}")


def _merge_pair(canonical_id: str, dup_id: str, operator: str) -> dict:
    """Soft-merge one duplicate into a canonical record (reports move, pointer set).

    Mirrors duplicates.merge_cluster but for an explicit pair (a candidate may no
    longer be in a live fuzzy cluster). Audited + webhook-emitting + reversible.
    """
    from modules import audit

    now = now_iso()
    with db.get_db() as conn:
        cur = conn.cursor()
        res = cur.execute(
            "UPDATE reports SET person_id = ?, updated_at = ? WHERE person_id = ?",
            (canonical_id, now, dup_id),
        )
        reports_moved = res.rowcount or 0
        cur.execute(
            "UPDATE persons SET merged_into = ?, updated_at = ? WHERE id = ?",
            (canonical_id, now, dup_id),
        )
        conn.commit()
    audit.log_history(dup_id, "merge", actor=operator, detail=f"merged_into={canonical_id}")
    try:
        from modules import webhooks
        webhooks.emit("person.merged", {"id": dup_id, "merged_into": canonical_id})
    except Exception:
        pass
    return {"canonical_id": canonical_id, "merged": [dup_id], "reports_moved": reports_moved}


def _set_status(candidate_id: str, status: str, operator: str,
                resolution: str = None, now: str = None) -> None:
    now = now or now_iso()
    with db.get_db() as conn:
        conn.execute(
            "UPDATE merge_candidates SET status = ?, reviewed_by = ?, "
            "resolution = ?, updated_at = ? WHERE id = ?",
            (status, operator, resolution, now, candidate_id),
        )
        conn.commit()


def pending_count() -> int:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM merge_candidates WHERE status = 'pending'"
        ).fetchone()
    return row["n"] or 0


# ── Conflict resolution (plan-27 Phase 4) ─────────────────────────────────────

# Field-level source priority (higher = more authoritative). Official/hospital
# sources win over family reports, which win over witness/SMS/OCR. A reviewed
# (approved) record gets a bonus so a vetted web report outranks a raw import.
_SOURCE_PRIORITY = {
    "official": 100,
    "self": 90,
    "seed": 70,
    "web": 60,
    "witness": 50,
    "csv_import": 40,
    "pfif_import": 40,
    "sms": 30,
    "ai_draft": 20,
    "ocr": 20,
    "synthetic": 10,
}

# Fields that carry a conflict-resolvable value (everything a family cares about).
_RESOLVABLE_FIELDS = (
    "name", "given_name", "family_name", "status", "age", "sex", "gender",
    "cedula", "contact", "location", "last_known_location", "last_seen_date",
    "clothes", "notes",
)

# Statuses that must not be set from low-trust data (plan-27 §6.2). Asserting
# someone is found or deceased requires a verified/official source.
_PROTECTED_STATUSES = ("found", "deceased")
_VERIFIED_SOURCES = ("official", "self", "web", "seed")


def _priority(record: dict) -> int:
    base = _SOURCE_PRIORITY.get((record.get("source") or "web"), 50)
    if record.get("reviewed") == 1:
        base += 15
    elif record.get("reviewed") == -1:
        base -= 50
    return base


def can_override_status(current: Optional[str], new: Optional[str],
                        new_source: Optional[str], new_reviewed: Optional[int]) -> bool:
    """May a record set the merged status to ``new``? (plan-27 §6.2).

    ``found``/``deceased`` are life-critical claims: only a verified/approved
    source may assert them. Any source may report ``missing``/``safe``/etc.
    """
    if new in _PROTECTED_STATUSES:
        return (new_source in _VERIFIED_SOURCES) or (new_reviewed == 1)
    return True


def resolve_conflicts(records: list) -> dict:
    """Resolve field-level conflicts across duplicate records.

    For each field, the value from the highest-priority source wins; ties break on
    the newest ``updated_at``. Losing values are kept under ``conflicts`` so a
    merge never silently discards a source (plan-27 §6.3). Protected statuses from
    low-trust sources are filtered before the vote. Returns
    ``{field: {value, source, person_id, conflicts: [...]}}`` for fields where the
    records actually differ.
    """
    out: dict = {}
    if len(records) < 2:
        return out

    def ts(r):
        return str(r.get("updated_at") or "")

    for field in _RESOLVABLE_FIELDS:
        # Collect distinct non-empty values with their source record.
        entries = []
        for r in records:
            v = r.get(field)
            if v in (None, ""):
                continue
            if field == "status" and not can_override_status(
                None, v, r.get("source"), r.get("reviewed")
            ):
                continue
            entries.append(r)
        # Only a conflict if 2+ records carry *different* values.
        values = {str(r.get(field)) for r in entries}
        if len(values) < 2:
            continue
        ranked = sorted(entries, key=lambda r: (_priority(r), ts(r)), reverse=True)
        winner = ranked[0]
        losers = []
        seen = {str(winner.get(field))}
        for r in ranked[1:]:
            val = str(r.get(field))
            if val in seen:
                continue
            seen.add(val)
            losers.append({
                "value": r.get(field),
                "source": r.get("source"),
                "person_id": r.get("id"),
            })
        out[field] = {
            "value": winner.get(field),
            "source": winner.get("source"),
            "person_id": winner.get("id"),
            "conflicts": losers,
        }
    return out
