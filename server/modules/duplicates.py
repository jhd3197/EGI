"""Fuzzy deduplication: surface probable-duplicate clusters for moderator review.

Exact dedup already happens at sync time (keyed on record id). This module adds
*fuzzy* clustering across distinct ids, and an explicit human-driven merge — we
NEVER auto-merge in a crisis context (see README privacy principles). A merge is
a soft operation: the duplicate's reports move to the canonical record and the
duplicate keeps a ``merged_into`` pointer (no hard delete, history preserved).

Tiers (strongest wins for a cluster's label):
  - tier1 / strong   : same cédula.
  - tier2 / probable : normalized given+family name AND age within ±2 years.
  - tier3 / possible : same normalized last-known location AND last-seen within ±24h.
"""

import hashlib
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException

import db
from models import now_iso

AGE_TOLERANCE_YEARS = 2
LOCATION_TIME_WINDOW_HOURS = 24

# Tier ranking: lower number = stronger match (used to label a cluster).
_TIER_RANK = {"tier1": 1, "tier2": 2, "tier3": 3}
_TIER_REASON = {
    "tier1": "Misma cédula",
    "tier2": "Mismo nombre y edad aproximada",
    "tier3": "Misma ubicación y ventana de tiempo",
}


def _norm(text: Optional[str]) -> str:
    """Lowercase, strip accents and collapse whitespace for loose comparison."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(no_accents.lower().split())


def _full_name(row) -> str:
    given = _norm(row["given_name"])
    family = _norm(row["family_name"])
    combined = (given + " " + family).strip()
    return combined or _norm(row["name"])


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _pair_tier(a, b) -> Optional[str]:
    """Strongest tier matching this pair, or None if they aren't candidates."""
    # Tier 1 — same cédula.
    ca, cb = _norm(a["cedula"]), _norm(b["cedula"])
    if ca and cb and ca == cb:
        return "tier1"

    # Tier 2 — same normalized name + approximate age.
    na, nb = _full_name(a), _full_name(b)
    if na and na == nb:
        aa, ab = a["age"], b["age"]
        if aa is None or ab is None or abs(int(aa) - int(ab)) <= AGE_TOLERANCE_YEARS:
            return "tier2"

    # Tier 3 — same location + last-seen within the time window.
    la = _norm(a["last_known_location"]) or _norm(a["location"])
    lb = _norm(b["last_known_location"]) or _norm(b["location"])
    if la and la == lb:
        da, dbt = _parse_dt(a["last_seen_date"]), _parse_dt(b["last_seen_date"])
        if da is not None and dbt is not None:
            if abs(da - dbt) <= timedelta(hours=LOCATION_TIME_WINDOW_HOURS):
                return "tier3"
    return None


def _cluster_id(member_ids) -> str:
    key = ",".join(sorted(member_ids))
    return "dup-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _rejected_pairs(conn) -> set:
    rows = conn.execute("SELECT id_a, id_b FROM dedup_rejections").fetchall()
    return {(r["id_a"], r["id_b"]) for r in rows}


def _pair_key(a_id: str, b_id: str) -> tuple:
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def find_clusters() -> list:
    """Build clusters of probable duplicates via union-find over candidate pairs.

    Considers only live, non-merged persons and skips pairs a moderator already
    rejected. Returns clusters (size >= 2) with their strongest tier + members.
    """
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM persons WHERE merged_into IS NULL ORDER BY created_at ASC"
        ).fetchall()
        rejected = _rejected_pairs(conn)

    by_id = {r["id"]: r for r in rows}
    parent = {r["id"]: r["id"] for r in rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    # Track the strongest tier seen for any pair within each evolving group.
    pair_tiers: dict = {}
    n = len(rows)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = rows[i], rows[j]
            if _pair_key(a["id"], b["id"]) in rejected:
                continue
            tier = _pair_tier(a, b)
            if tier is None:
                continue
            pair_tiers[_pair_key(a["id"], b["id"])] = tier
            union(a["id"], b["id"])

    groups: dict = {}
    for pid in parent:
        groups.setdefault(find(pid), []).append(pid)

    clusters = []
    for member_ids in groups.values():
        if len(member_ids) < 2:
            continue
        # Strongest tier among any matched pair inside this group.
        best = "tier3"
        for key, tier in pair_tiers.items():
            if key[0] in member_ids and key[1] in member_ids:
                if _TIER_RANK[tier] < _TIER_RANK[best]:
                    best = tier
        members = [db.row_to_dict(by_id[mid]) for mid in member_ids]
        members.sort(key=lambda m: m.get("created_at") or "")
        clusters.append({
            "cluster_id": _cluster_id(member_ids),
            "tier": best,
            "reason": _TIER_REASON[best],
            "members": members,
        })
    # Strongest clusters first, then larger ones.
    clusters.sort(key=lambda c: (_TIER_RANK[c["tier"]], -len(c["members"])))
    return clusters


def pending_clusters() -> dict:
    return {"clusters": find_clusters()}


def _cluster_by_id(cluster_id: str) -> dict:
    for cluster in find_clusters():
        if cluster["cluster_id"] == cluster_id:
            return cluster
    raise HTTPException(status_code=404, detail="cluster not found")


def merge_cluster(cluster_id: str, canonical_id: str,
                  duplicate_ids: Optional[list] = None) -> dict:
    """Merge a cluster into ``canonical_id``: move reports, set merged_into.

    Soft merge — duplicates are never hard-deleted; they keep a merged_into
    pointer so the action is auditable and reversible by hand if needed.
    """
    cluster = _cluster_by_id(cluster_id)
    member_ids = [m["id"] for m in cluster["members"]]
    if canonical_id not in member_ids:
        raise HTTPException(status_code=400, detail="canonical_id not in cluster")

    targets = duplicate_ids or [mid for mid in member_ids if mid != canonical_id]
    for dup in targets:
        if dup not in member_ids:
            raise HTTPException(status_code=400, detail=f"{dup} not in cluster")
        if dup == canonical_id:
            raise HTTPException(status_code=400, detail="cannot merge canonical into itself")

    now = now_iso()
    reports_moved = 0
    with db.get_db() as conn:
        cur = conn.cursor()
        for dup in targets:
            res = cur.execute(
                "UPDATE reports SET person_id = ?, updated_at = ? WHERE person_id = ?",
                (canonical_id, now, dup),
            )
            reports_moved += res.rowcount or 0
            cur.execute(
                "UPDATE persons SET merged_into = ?, updated_at = ? WHERE id = ?",
                (canonical_id, now, dup),
            )
        conn.commit()

    return {
        "canonical_id": canonical_id,
        "merged": targets,
        "reports_moved": reports_moved,
    }


def reject_cluster(cluster_id: str) -> dict:
    """Mark every pair in a cluster as 'not a duplicate' so it isn't suggested again."""
    cluster = _cluster_by_id(cluster_id)
    member_ids = [m["id"] for m in cluster["members"]]
    now = now_iso()
    rejected = 0
    with db.get_db() as conn:
        cur = conn.cursor()
        for i in range(len(member_ids)):
            for j in range(i + 1, len(member_ids)):
                a, b = _pair_key(member_ids[i], member_ids[j])
                cur.execute(
                    "INSERT OR IGNORE INTO dedup_rejections (id_a, id_b, created_at)"
                    " VALUES (?, ?, ?)",
                    (a, b, now),
                )
                rejected += 1
        conn.commit()
    return {"rejected_pairs": rejected}
