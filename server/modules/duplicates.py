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
from modules import audit

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


def normalize_cedula(value: Optional[str]) -> str:
    """Canonical cédula key: uppercase prefix letter + digits, no separators.

    Venezuelan/Colombian national IDs arrive as ``V-12.345.678``, ``v12345678``,
    ``12345678`` … all of which should match. We keep an optional leading letter
    (V/E/J/G/P nationality prefix) and the digits, dropping dots/dashes/spaces so
    the same person isn't split across formatting variants. Returns "" when no
    digits are present (so a blank/garbage cédula never matches another blank).
    """
    if not value:
        return ""
    raw = unicodedata.normalize("NFKD", value).upper()
    letter = ""
    digits = []
    for ch in raw:
        if ch.isdigit():
            digits.append(ch)
        elif ch in "VEJGP" and not digits and not letter:
            letter = ch
    if not digits:
        return ""
    # Drop a leading nationality letter from the comparison key when the same
    # number appears with and without it — match on the digits, prefix optional.
    return letter + "".join(digits)


def normalize_phone(value: Optional[str]) -> str:
    """Canonical phone key: digits only (last 10) for loose cross-format matching.

    Strips spaces, dashes, parens and a leading ``+``/country code so
    ``+58 412-555-1234`` and ``0412 5551234`` collapse to the same key. Returns ""
    for anything with fewer than 7 digits (too short to be a real number)."""
    if not value:
        return ""
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) < 7:
        return ""
    # Compare on the national significant number (last 10 digits) so a number
    # written with vs. without the country code still matches.
    return digits[-10:]


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
    # Tier 1 — same cédula (canonicalized: V-12.345.678 == v12345678).
    ca, cb = normalize_cedula(a["cedula"]), normalize_cedula(b["cedula"])
    if ca and cb and ca == cb:
        return "tier1"

    # Tier 1 — same phone number + exact name (plan-27 §5.1). A shared contact
    # number with the same normalized name is as strong as a shared cédula.
    pa, pb = normalize_phone(a["contact"]), normalize_phone(b["contact"])
    if pa and pb and pa == pb:
        na, nb = _full_name(a), _full_name(b)
        if na and na == nb:
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
    # Non-security digest: just a stable id for a duplicate cluster, not a
    # cryptographic guarantee (usedforsecurity=False keeps static analysis quiet).
    digest = hashlib.sha1(key.encode("utf-8"), usedforsecurity=False)
    return "dup-" + digest.hexdigest()[:12]


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


def _exact_key(row) -> Optional[tuple]:
    """The strongest *exact* dedup key for a row, or None.

    Exact keys are high-confidence (plan-27 §5.1): a canonical cédula, or a
    canonical phone paired with the exact normalized name. Cédula wins when both
    are present. Returns a ``(kind, value)`` tuple so cédula and phone keys never
    collide.
    """
    ced = normalize_cedula(row["cedula"])
    if ced:
        return ("cedula", ced)
    phone = normalize_phone(row["contact"])
    name = _full_name(row)
    if phone and name:
        return ("phone_name", phone + "|" + name)
    return None


def exact_clusters() -> list:
    """Groups of live persons that share an *exact* high-confidence key.

    O(n) bucketing by ``_exact_key`` (no pairwise scan). Skips pairs a moderator
    already rejected: a group is only returned if at least one un-rejected pair
    remains. Returns clusters (size >= 2) shaped like ``find_clusters`` so the
    same review/merge UI can consume them.
    """
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM persons WHERE merged_into IS NULL ORDER BY created_at ASC"
        ).fetchall()
        rejected = _rejected_pairs(conn)

    buckets: dict = {}
    for r in rows:
        key = _exact_key(r)
        if key is None:
            continue
        buckets.setdefault(key, []).append(r)

    clusters = []
    for (kind, _val), members in buckets.items():
        if len(members) < 2:
            continue
        ids = [m["id"] for m in members]
        # Drop a group whose every pair a moderator already rejected.
        if all(
            _pair_key(ids[i], ids[j]) in rejected
            for i in range(len(ids)) for j in range(i + 1, len(ids))
        ):
            continue
        reason = "Misma cédula" if kind == "cedula" else "Mismo teléfono y nombre"
        member_dicts = [db.row_to_dict(m) for m in members]
        member_dicts.sort(key=lambda m: m.get("created_at") or "")
        clusters.append({
            "cluster_id": _cluster_id(ids),
            "tier": "tier1",
            "match": kind,
            "reason": reason,
            "members": member_dicts,
        })
    clusters.sort(key=lambda c: -len(c["members"]))
    return clusters


def exact_pending() -> dict:
    return {"clusters": exact_clusters()}


def _pick_canonical(members) -> str:
    """Choose the canonical record for an auto-merge: most trustworthy, else oldest.

    Prefers a reviewed (reviewed=1) record, then a trusted web/seed/official/self
    source over an untrusted import, then the earliest created_at. Deterministic so
    a dry-run matches the real run.
    """
    trusted = {"web", "seed", "official", "self"}

    def rank(m):
        return (
            0 if (m.get("reviewed") or 0) == 1 else 1,
            0 if (m.get("source") or "web") in trusted else 1,
            m.get("created_at") or "",
        )

    return sorted(members, key=rank)[0]["id"]


def auto_merge_exact(operator: str = "op:system", dry_run: bool = False) -> dict:
    """Auto-merge exact-match clusters (same cédula / phone+name).

    Exact identity matches are the one case the plan sanctions for automatic
    merging (plan-27 §5.1/Phase 1). It is still a *soft* merge — duplicates keep a
    ``merged_into`` pointer and full history, so it stays auditable and reversible.
    ``dry_run`` reports what would merge without writing. Fuzzy/medium-confidence
    clusters are NEVER auto-merged; they go to the human review queue.
    """
    clusters = exact_clusters()
    merges = []
    for cluster in clusters:
        canonical = _pick_canonical(cluster["members"])
        dups = [m["id"] for m in cluster["members"] if m["id"] != canonical]
        if not dups:
            continue
        plan = {
            "cluster_id": cluster["cluster_id"],
            "canonical_id": canonical,
            "merged": dups,
            "match": cluster.get("match"),
        }
        if not dry_run:
            result = merge_cluster(
                cluster["cluster_id"], canonical, dups,
                operator=operator,
            )
            plan["reports_moved"] = result.get("reports_moved", 0)
        merges.append(plan)
    return {
        "merged_clusters": len(merges),
        "merged_records": sum(len(m["merged"]) for m in merges),
        "dry_run": dry_run,
        "merges": merges,
    }


def _cluster_by_id(cluster_id: str) -> dict:
    for cluster in find_clusters():
        if cluster["cluster_id"] == cluster_id:
            return cluster
    raise HTTPException(status_code=404, detail="cluster not found")


def merge_cluster(cluster_id: str, canonical_id: str,
                  duplicate_ids: Optional[list] = None,
                  operator: str = "op:anonymous") -> dict:
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

    # Attributable merge: one audit row + a history entry on each merged record.
    audit.log_action(
        operator, "merge", "person", canonical_id,
        detail=f"merged={','.join(targets)} reports_moved={reports_moved}",
    )
    for dup in targets:
        audit.log_history(dup, "merge", actor=operator, detail=f"merged_into={canonical_id}")

    # Outbound webhooks (plan-12, best-effort, post-commit). Lazy import; emit()
    # never raises so a webhook failure can't break the merge.
    from modules import webhooks

    for dup in targets:
        webhooks.emit("person.merged", {"id": dup, "merged_into": canonical_id})

    return {
        "canonical_id": canonical_id,
        "merged": targets,
        "reports_moved": reports_moved,
    }


def reject_cluster(cluster_id: str, operator: str = "op:anonymous") -> dict:
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
    audit.log_action(
        operator, "reject_duplicate", "cluster", cluster_id,
        detail=f"rejected_pairs={rejected}",
    )
    return {"rejected_pairs": rejected}
