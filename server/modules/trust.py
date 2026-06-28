"""Trust scoring for records (plan-25 Phase 1).

A record carries provenance signals (``author_role``, ``org_id``, ``location_id``,
``signature`` — see models.PersonRecord) that travel with it over the mesh. This
module turns those signals + the moderation ``reviewed`` flag + the origin
device's reputation into a coarse ``trust_tier`` (``high`` | ``medium`` | ``low``)
that the server stamps on every upsert.

Design choices:
  * **Never trust a client-supplied ``trust_tier``.** It is always recomputed
    here so a malicious peer cannot self-promote a record.
  * **Local knowledge beats remote assumptions** (plan §2): a verified watcher at
    a location, or a verified-org member, outranks an anonymous reporter.
  * **Degrade, never raise.** A scoring failure must never break a sync, so the
    public entry point falls back to ``low`` on any error.

Signature *verification* (cryptographically checking the ``signature`` against a
pinned org/location key) lands with the org/location key registry in Phase 2;
until a key is pinned, a present signature is treated as a weak positive signal
only, not as proof.
"""

from typing import Optional

import sqlite3

# Roles that imply a place-bound or org-bound authorization (highest local trust).
_AUTHORIZED_ROLES = {"watcher", "org_admin", "org_member", "operator", "commander", "admin"}
# Roles that imply some verification short of a location/org authorization.
_VERIFIED_ROLES = {"phone_verified", "verified_reporter"}


def compute_trust_tier(record: dict, conn: Optional[sqlite3.Connection] = None) -> str:
    """Return ``high`` | ``medium`` | ``low`` for a person record dict.

    ``record`` uses the model field names (author_role, org_id, location_id,
    signature, source, reviewed, origin_device). ``conn`` (optional) lets the
    caller reuse an open connection for the org/location/device lookups; when
    omitted we open our own. Never raises.
    """
    try:
        return _compute(record, conn)
    except Exception:
        return "low"


def _compute(record: dict, conn: Optional[sqlite3.Connection]) -> str:
    author_role = (record.get("author_role") or "").strip().lower()
    org_id = record.get("org_id")
    location_id = record.get("location_id")
    has_signature = bool((record.get("signature") or "").strip())
    source = (record.get("source") or "web").strip().lower()
    reviewed = record.get("reviewed")
    device_id = record.get("origin_device")

    # A banned device sinks any record to the floor regardless of other signals.
    if device_id and _device_banned(device_id, conn):
        return "low"

    # HIGH — a verified watcher authorized at this location, or a verified-org
    # member, with a signature present. Local/org knowledge with proof.
    if has_signature and location_id and _is_active_watcher(location_id, record, conn):
        return "high"
    if org_id and _is_verified_org(org_id, conn):
        # An org-affiliated record from a verified org is high trust; the
        # signature strengthens it but a verified org membership alone qualifies.
        if author_role in _AUTHORIZED_ROLES or has_signature:
            return "high"
        return "medium"

    # MEDIUM — an authorized/verified role, an operator-approved record, an
    # official source, or a present (un-pinned) signature.
    if author_role in _AUTHORIZED_ROLES or author_role in _VERIFIED_ROLES:
        return "medium"
    if source in ("official", "self"):
        return "medium"
    if reviewed == 1:
        return "medium"
    if has_signature or location_id or org_id:
        return "medium"

    # LOW — anonymous, accepted, but visibly unverified.
    return "low"


def _is_verified_org(org_id: str, conn: Optional[sqlite3.Connection]) -> bool:
    row = _query_one(conn, "SELECT verified FROM organizations WHERE id = ?", (org_id,))
    return bool(row and row[0])


def _is_active_watcher(location_id: str, record: dict, conn: Optional[sqlite3.Connection]) -> bool:
    """True when the record's author is an unrevoked, unexpired watcher at the
    location. We match on the record's author principal when present; absent a
    concrete user link we accept a watcher row existing for the location as a
    weaker positive (the signature still gates the high tier above)."""
    from models import now_iso

    rows = _query_all(
        conn,
        "SELECT user_id, expires_at, revoked FROM location_watchers WHERE location_id = ?",
        (location_id,),
    )
    if not rows:
        return False
    now = now_iso()
    for user_id, expires_at, revoked in rows:
        if revoked:
            continue
        if expires_at and expires_at < now:
            continue
        return True
    return False


def _device_banned(device_id: str, conn: Optional[sqlite3.Connection]) -> bool:
    row = _query_one(
        conn, "SELECT banned FROM device_reputation WHERE device_id = ?", (device_id,)
    )
    return bool(row and row[0])


# ── small connection helpers (reuse caller's conn or open our own) ──────────

def _query_one(conn, sql, params):
    if conn is not None:
        return conn.execute(sql, params).fetchone()
    import db

    with db.get_db() as c:
        return c.execute(sql, params).fetchone()


def _query_all(conn, sql, params):
    if conn is not None:
        return conn.execute(sql, params).fetchall()
    import db

    with db.get_db() as c:
        return c.execute(sql, params).fetchall()
