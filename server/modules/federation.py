"""Server-to-server federation between trusted EGI nodes (plan-12 §4).

Two community-run EGI hubs that trust each other can exchange person/report
records directly, without a device in the middle. This is just ``/sync`` pointed
at a peer: ``pull_from_peer`` GETs ``/sync?since=`` from the peer and feeds the
result through ``modules.sync.sync_upload`` so the existing timestamp-guarded
last-write-wins + duplicate guard resolve every conflict — re-pulling the same
payload therefore adds no duplicates. ``push_to_peer`` is the mirror: it POSTs
our locally-changed records to the peer's ``/sync``.

Trust model (trust-on-first-use): a peer's ``public_key`` is *pinned* at add
time. Once pinned, changing it to a different value is rejected (409) — a swapped
key means a different operator and must be re-added deliberately. NOTE: actual
cryptographic verification of payload signatures over ``/sync`` is future work;
the pin here is the stored-key guard, not yet a wire-level signature check.

Design mirrors ``webhooks.py`` / ``providers.py``: HTTP uses urllib (no new
runtime deps) and ``_http_get`` / ``_http_post`` are kept tiny + module-level so
tests can monkeypatch them instead of hitting the network. Network calls degrade
to ``{"error": ...}`` rather than raising, so a dead peer can't break an operator
flow; only an unknown peer id raises (404).
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Optional

from fastapi import HTTPException

import db
from models import PersonRecord, ReportRecord, SyncPayload, now_iso

# Per-request timeout for a peer pull/push (env-tunable, optional).
_HTTP_TIMEOUT = int(os.environ.get("FEDERATION_TIMEOUT", "30"))


def _normalize_base_url(base_url: str) -> str:
    return (base_url or "").strip().rstrip("/")


# ── Peers CRUD ──────────────────────────────────────────────────────────────

def add_peer(
    name: str,
    base_url: str,
    public_key: Optional[str] = None,
    token: Optional[str] = None,
) -> dict:
    """Register a trusted peer. ``base_url`` is normalized (no trailing slash).

    If a peer with the same ``base_url`` already exists, this acts as an update
    that re-pins the key: changing an already-set ``public_key`` to a different
    value is rejected (409, trust-on-first-use).
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise HTTPException(status_code=400, detail="base_url is required")

    with db.get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM trusted_peers WHERE base_url = ?", (base_url,)
        ).fetchone()
    if existing:
        return update_peer(
            existing["id"], name=name, public_key=public_key, token=token
        )

    now = now_iso()
    pid = f"peer-{uuid.uuid4().hex[:10]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO trusted_peers
            (id, name, base_url, public_key, token, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (pid, name, base_url, public_key, token, now, now),
        )
        conn.commit()
    return get_peer(pid)


def list_peers() -> dict:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM trusted_peers ORDER BY created_at DESC"
        ).fetchall()
    return {"records": [db.row_to_dict(r) for r in rows]}


def get_peer(peer_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM trusted_peers WHERE id = ?", (peer_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Trusted peer not found")
    return db.row_to_dict(row)


def pin_or_verify_key(peer_id: str, presented_key: Optional[str]) -> None:
    """Trust-on-first-use key guard.

    If the peer has no stored key, the presented key is accepted (and will be
    pinned by the caller). If a key is already pinned, a *different* non-empty
    presented key is rejected (409). Presenting the same key — or no key — is a
    no-op. Raises 404 for an unknown peer.
    """
    peer = get_peer(peer_id)
    if presented_key is None:
        return
    stored = peer.get("public_key")
    if stored and presented_key != stored:
        raise HTTPException(
            status_code=409, detail="peer key change rejected — pinned"
        )


def update_peer(peer_id: str, **fields) -> dict:
    """Patch name/base_url/public_key/token/active. Unknown/None fields ignored.

    Changing an already-pinned ``public_key`` to a different value is rejected
    (409) per the trust-on-first-use model.
    """
    if "public_key" in fields and fields["public_key"] is not None:
        pin_or_verify_key(peer_id, fields["public_key"])
    else:
        get_peer(peer_id)  # 404 if missing

    sets, params = [], []
    for col in (
        "name", "base_url", "public_key", "token", "active",
        "last_sync_at", "last_push_at",
    ):
        if col in fields and fields[col] is not None:
            val = fields[col]
            if col == "base_url":
                val = _normalize_base_url(val)
            if col == "active":
                val = int(bool(val))
            sets.append(f"{col} = ?")
            params.append(val)
    if sets:
        sets.append("updated_at = ?")
        params.append(now_iso())
        params.append(peer_id)
        with db.get_db() as conn:
            conn.execute(
                f"UPDATE trusted_peers SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
    return get_peer(peer_id)


def remove_peer(peer_id: str) -> dict:
    """Hard delete a peer."""
    with db.get_db() as conn:
        cur = conn.execute("DELETE FROM trusted_peers WHERE id = ?", (peer_id,))
        conn.commit()
    if not cur.rowcount:
        raise HTTPException(status_code=404, detail="Trusted peer not found")
    return {"ok": True, "deleted": peer_id}


# ── HTTP (tiny + module-level so tests monkeypatch instead of hitting network) ──

def _http_get(url: str, headers: dict, timeout: int) -> tuple:
    """GET ``url`` and return (status, body). Raises on transport failure.

    Non-2xx HTTP responses are returned (not raised) so the caller can record
    the status; only transport-level failures propagate.
    """
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:  # pragma: no cover - exercised via monkeypatch
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        return e.code, body


def _http_post(url: str, body_bytes: bytes, headers: dict, timeout: int) -> tuple:
    """POST raw bytes and return (status, body). Raises on transport failure."""
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:  # pragma: no cover - exercised via monkeypatch
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        return e.code, body


def _auth_headers(peer: dict) -> dict:
    headers = {"User-Agent": "EGI-Federation", "Accept": "application/json"}
    if peer.get("token"):
        headers["Authorization"] = f"Bearer {peer['token']}"
    return headers


def _to_sync_shape(row: dict) -> dict:
    """Rename created_at/updated_at -> createdAt/updatedAt for the /sync schema.

    Replicated from pfif._to_sync_shape so federation does not depend on the
    PFIF module's import/export surface.
    """
    out = dict(row)
    if "created_at" in out:
        out["createdAt"] = out.pop("created_at")
    if "updated_at" in out:
        out["updatedAt"] = out.pop("updated_at")
    return out


# ── Pull / push / sync ────────────────────────────────────────────────────────

def pull_from_peer(peer_id: str) -> dict:
    """Pull records from a peer's ``/sync`` and apply them via ``sync_upload``.

    GETs ``{base_url}/sync?since={last_sync_at or ''}`` and feeds the returned
    persons/reports through the shared last-write-wins upload, so conflicts and
    duplicates are resolved exactly like a normal device sync (a second pull of
    the same payload is fully skipped). Best-effort: a network/parse failure
    returns ``{"error": ...}`` rather than raising. Unknown peer raises 404.
    """
    from modules.sync import sync_upload

    peer = get_peer(peer_id)
    since = peer.get("last_sync_at") or ""
    url = f"{peer['base_url']}/sync?since={urllib.parse.quote(since)}"

    try:
        status, text = _http_get(url, _auth_headers(peer), _HTTP_TIMEOUT)
    except Exception as e:  # transport-level failure
        return {"error": f"pull request failed: {e}"}
    if not (200 <= (status or 0) < 300):
        return {"error": f"peer returned HTTP {status}"}
    try:
        data = json.loads(text or "{}")
    except (ValueError, TypeError) as e:
        return {"error": f"invalid peer response: {e}"}

    records = data.get("records") or []
    reports = data.get("reports") or []
    payload = SyncPayload(
        records=[PersonRecord(**r) for r in records],
        reports=[ReportRecord(**r) for r in reports],
    )
    result = sync_upload(payload)

    update_peer(peer_id, last_sync_at=now_iso())
    return {
        "pulled": len(records),
        "saved": result.get("saved", 0),
        "skipped": result.get("skipped", 0),
        "reports": result.get("reports", 0),
    }


def push_to_peer(peer_id: str) -> dict:
    """Push locally-changed persons + reports to a peer's ``/sync``.

    Gathers rows with ``updated_at > last_push_at`` (or all rows when never
    pushed), shapes them to the camelCase ``/sync`` envelope, and POSTs. Updates
    ``last_push_at`` on success. Best-effort: returns ``{"error": ...}`` on a
    network/HTTP failure rather than raising. Unknown peer raises 404.
    """
    peer = get_peer(peer_id)
    since = peer.get("last_push_at")

    with db.get_db() as conn:
        if since:
            person_rows = conn.execute(
                "SELECT * FROM persons WHERE updated_at > ? ORDER BY updated_at ASC",
                (since,),
            ).fetchall()
            report_rows = conn.execute(
                "SELECT * FROM reports WHERE updated_at > ? ORDER BY updated_at ASC",
                (since,),
            ).fetchall()
        else:
            person_rows = conn.execute(
                "SELECT * FROM persons ORDER BY updated_at ASC"
            ).fetchall()
            report_rows = conn.execute(
                "SELECT * FROM reports ORDER BY updated_at ASC"
            ).fetchall()

    envelope = {
        "records": [_to_sync_shape(db.row_to_dict(r)) for r in person_rows],
        "reports": [_to_sync_shape(db.row_to_dict(r)) for r in report_rows],
    }
    body_bytes = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    headers = _auth_headers(peer)
    headers["Content-Type"] = "application/json"
    url = f"{peer['base_url']}/sync"

    try:
        status, text = _http_post(url, body_bytes, headers, _HTTP_TIMEOUT)
    except Exception as e:  # transport-level failure
        return {"error": f"push request failed: {e}"}
    if not (200 <= (status or 0) < 300):
        return {"error": f"peer returned HTTP {status}"}

    update_peer(peer_id, last_push_at=now_iso())
    result = {"pushed": len(envelope["records"]), "reports": len(envelope["reports"])}
    try:
        peer_result = json.loads(text or "{}")
        if isinstance(peer_result, dict):
            result["peer"] = peer_result
    except (ValueError, TypeError):
        pass
    return result


def sync_peer(peer_id: str) -> dict:
    """Full bidirectional sync with a peer: pull then push."""
    get_peer(peer_id)  # 404 early if unknown
    pull = pull_from_peer(peer_id)
    push = push_to_peer(peer_id)
    return {"pull": pull, "push": push}
