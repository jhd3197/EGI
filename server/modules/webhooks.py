"""Outbound webhooks with retry (plan-12 §3).

External systems register a URL + the event types they care about; when one of
those events happens in EGI we POST a JSON payload to their URL. Each delivery is
logged per-attempt in ``webhook_deliveries`` (retries add rows), so a
failed-then-succeeded delivery is fully auditable.

Design mirrors ``providers.py`` / ``messaging.py``: **always degrade, never break
the request that triggered the event.** Emission (``emit``) is wrapped so a
webhook failure can never propagate into a sync/merge/close. HTTP uses urllib
(no new runtime deps) and ``_http_post`` is kept tiny + module-level so tests can
monkeypatch it instead of hitting the network.
"""

import hashlib
import hmac
import json
import urllib.error
import urllib.request
import uuid
from typing import Optional

from fastapi import HTTPException

import db
from models import now_iso

# Event types a subscription can listen for. A subscription's ``events`` is a
# comma-separated list of these, or '*' for all.
EVENT_TYPES = [
    "person.created",
    "person.updated",
    "person.merged",
    "operation.closed",
]

# Exponential backoff base (seconds) and cap. next_retry = base * 2**(attempt-1).
_BACKOFF_BASE_SECONDS = 60
_BACKOFF_CAP_SECONDS = 3600
# Response bodies are truncated before storage (we only need a debugging snippet).
_RESPONSE_BODY_MAX = 2000
_HTTP_TIMEOUT = 10


# ── Subscriptions CRUD ────────────────────────────────────────────────────────

def _validate_events(events: str) -> str:
    """Validate a comma-separated events string (or '*'); return it normalized."""
    value = (events or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="events is required")
    if value == "*":
        return "*"
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        raise HTTPException(status_code=400, detail="events is required")
    for p in parts:
        if p != "*" and p not in EVENT_TYPES:
            raise HTTPException(status_code=400, detail=f"unknown event type: {p}")
    return ",".join(parts)


def create_subscription(
    url: str,
    events: str,
    secret: Optional[str] = None,
    owner_user_id: Optional[str] = None,
) -> dict:
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    events = _validate_events(events)
    now = now_iso()
    wid = f"whk-{uuid.uuid4().hex[:10]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO webhook_subscriptions
            (id, owner_user_id, url, events, secret, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (wid, owner_user_id, url, events, secret, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM webhook_subscriptions WHERE id = ?", (wid,)
        ).fetchone()
    return db.row_to_dict(row)


def list_subscriptions() -> dict:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM webhook_subscriptions ORDER BY created_at DESC"
        ).fetchall()
    return {"records": [db.row_to_dict(r) for r in rows]}


def get_subscription(subscription_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM webhook_subscriptions WHERE id = ?", (subscription_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")
    return db.row_to_dict(row)


def update_subscription(subscription_id: str, **fields) -> dict:
    """Patch url/events/secret/active. Unknown/None fields are ignored."""
    get_subscription(subscription_id)  # 404 if missing
    sets, params = [], []
    for col in ("url", "events", "secret", "active"):
        if col in fields and fields[col] is not None:
            val = fields[col]
            if col == "events":
                val = _validate_events(val)
            if col == "active":
                val = int(bool(val))
            sets.append(f"{col} = ?")
            params.append(val)
    if sets:
        sets.append("updated_at = ?")
        params.append(now_iso())
        params.append(subscription_id)
        with db.get_db() as conn:
            conn.execute(
                f"UPDATE webhook_subscriptions SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            conn.commit()
    return get_subscription(subscription_id)


def delete_subscription(subscription_id: str) -> dict:
    """Hard delete. Deliveries cascade via the FK in db.py."""
    with db.get_db() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        # Explicitly clear deliveries too: WAL connections don't always enforce
        # the FK cascade unless foreign_keys is on, so be defensive.
        conn.execute(
            "DELETE FROM webhook_deliveries WHERE subscription_id = ?",
            (subscription_id,),
        )
        cur = conn.execute(
            "DELETE FROM webhook_subscriptions WHERE id = ?", (subscription_id,)
        )
        conn.commit()
    if not cur.rowcount:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")
    return {"ok": True, "deleted": subscription_id}


# ── Delivery ──────────────────────────────────────────────────────────────────

def _http_post(url: str, body_bytes: bytes, headers: dict, timeout: int) -> tuple:
    """POST raw bytes and return (status, body). Raises on network error.

    Kept tiny + module-level so tests can monkeypatch it instead of hitting the
    network. Non-2xx HTTP responses are returned (not raised) so the caller can
    record the status; only transport-level failures raise.
    """
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


def _backoff_seconds(attempt: int) -> int:
    return min(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), _BACKOFF_CAP_SECONDS)


def _next_retry_at(attempt: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (
        datetime.now(timezone.utc) + timedelta(seconds=_backoff_seconds(attempt))
    ).isoformat()


def _sign(secret: str, body_bytes: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def deliver(subscription: dict, event_type: str, payload_dict: dict,
            attempt: int = 1) -> dict:
    """Deliver one event to one subscription, recording a delivery row.

    Never raises: on transport failure or non-2xx it records ``success=0`` and a
    ``next_retry_at`` (exponential backoff) for ``retry_pending`` to pick up.
    """
    delivery_id = f"whd-{uuid.uuid4().hex[:10]}"
    body_bytes = json.dumps(payload_dict, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "EGI-Webhook",
        "X-EGI-Event": event_type,
        "X-EGI-Delivery": delivery_id,
    }
    secret = subscription.get("secret")
    if secret:
        headers["X-EGI-Signature"] = _sign(secret, body_bytes)

    status: Optional[int] = None
    resp_body = ""
    error = None
    try:
        status, resp_body = _http_post(
            subscription["url"], body_bytes, headers, _HTTP_TIMEOUT
        )
    except Exception as e:  # transport-level failure
        error = str(e)

    success = 1 if (status is not None and 200 <= status < 300) else 0
    next_retry = None if success else _next_retry_at(attempt)
    stored_body = (resp_body or error or "")[:_RESPONSE_BODY_MAX]

    try:
        with db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO webhook_deliveries
                (id, subscription_id, event_type, payload, response_status,
                 response_body, attempt, attempted_at, next_retry_at, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery_id, subscription["id"], event_type,
                    body_bytes.decode("utf-8", "replace"), status, stored_body,
                    attempt, now_iso(), next_retry, success,
                ),
            )
            conn.commit()
    except Exception:
        # Bookkeeping must never break delivery flow.
        pass

    return {
        "delivery_id": delivery_id,
        "subscription_id": subscription["id"],
        "event_type": event_type,
        "attempt": attempt,
        "response_status": status,
        "success": bool(success),
        "next_retry_at": next_retry,
    }


def _matches(events: str, event_type: str) -> bool:
    if not events:
        return False
    if events.strip() == "*":
        return True
    parts = {p.strip() for p in events.split(",")}
    return "*" in parts or event_type in parts


def emit(event_type: str, payload_dict: dict) -> None:
    """Fan out an event to every active matching subscription. Never raises.

    Best-effort by design: a webhook failure (network, bad URL, even a DB error)
    must never break the sync/merge/close that triggered the event.
    """
    try:
        with db.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM webhook_subscriptions WHERE active = 1"
            ).fetchall()
        for row in rows:
            sub = db.row_to_dict(row)
            if _matches(sub.get("events", ""), event_type):
                deliver(sub, event_type, payload_dict, attempt=1)
    except Exception:
        pass


def retry_pending(max_attempts: int = 5, limit: int = 100) -> dict:
    """Re-attempt failed deliveries whose backoff window has elapsed.

    Picks ``success=0`` rows with a due ``next_retry_at`` and ``attempt`` below
    the cap, dedupes to the latest attempt per (subscription, event, payload), and
    re-delivers with ``attempt+1``.
    """
    now = now_iso()
    retried = 0
    succeeded = 0
    try:
        with db.get_db() as conn:
            rows = conn.execute(
                """
                SELECT d.* FROM webhook_deliveries d
                JOIN (
                    SELECT subscription_id, event_type, payload, MAX(attempt) AS max_attempt
                    FROM webhook_deliveries
                    GROUP BY subscription_id, event_type, payload
                ) latest
                ON d.subscription_id = latest.subscription_id
                   AND d.event_type IS latest.event_type
                   AND d.payload IS latest.payload
                   AND d.attempt = latest.max_attempt
                WHERE d.success = 0
                  AND d.next_retry_at IS NOT NULL
                  AND d.next_retry_at <= ?
                  AND d.attempt < ?
                ORDER BY d.next_retry_at ASC
                LIMIT ?
                """,
                (now, int(max_attempts), int(limit)),
            ).fetchall()
            candidates = [db.row_to_dict(r) for r in rows]
            subs = {}
            for c in candidates:
                sub_row = conn.execute(
                    "SELECT * FROM webhook_subscriptions WHERE id = ? AND active = 1",
                    (c["subscription_id"],),
                ).fetchone()
                if sub_row:
                    subs[c["id"]] = db.row_to_dict(sub_row)
        for c in candidates:
            sub = subs.get(c["id"])
            if not sub:
                continue
            try:
                payload = json.loads(c["payload"]) if c.get("payload") else {}
            except (ValueError, TypeError):
                payload = {}
            result = deliver(sub, c["event_type"], payload, attempt=c["attempt"] + 1)
            retried += 1
            if result["success"]:
                succeeded += 1
    except Exception:
        pass
    return {"retried": retried, "succeeded": succeeded}


def list_deliveries(subscription_id: Optional[str] = None, limit: int = 100) -> dict:
    sql = "SELECT * FROM webhook_deliveries"
    params: list = []
    if subscription_id:
        sql += " WHERE subscription_id = ?"
        params.append(subscription_id)
    sql += " ORDER BY attempted_at DESC LIMIT ?"
    params.append(int(limit))
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"records": [db.row_to_dict(r) for r in rows]}
