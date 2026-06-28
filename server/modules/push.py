"""Push notifications (plan-11): Web Push (VAPID) for the PWA + FCM for Android.

A device subscribes with its Web-Push endpoint (or FCM token) and an optional
``topic`` = the operation id it wants alerts for (NULL = global). Alerts fan out
to every active subscription for an operation (its topic + the global ones).

Actual delivery is delegated to ``modules/providers.send_push`` which degrades to
the ``log`` driver when no VAPID/FCM credentials are present, so subscribe /
unsubscribe and the fan-out bookkeeping work end-to-end with zero credentials.
"""

import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
from models import VALID_PUSH_KINDS, now_iso


def vapid_public_key() -> Optional[str]:
    from modules import providers

    return providers.vapid_public_key()


def subscribe(data, user_id: Optional[str] = None) -> dict:
    """Register (or refresh) a push subscription, keyed on its unique endpoint."""
    kind = (data.kind or "webpush").lower()
    if kind not in VALID_PUSH_KINDS:
        raise HTTPException(status_code=400, detail=f"invalid kind: {kind}")
    if not data.endpoint:
        raise HTTPException(status_code=400, detail="endpoint required")
    now = now_iso()
    with db.get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM push_subscriptions WHERE endpoint = ?", (data.endpoint,)
        ).fetchone()
        sub_id = existing["id"] if existing else f"push-{uuid.uuid4().hex[:10]}"
        created = existing is None
        conn.execute(
            """
            INSERT OR REPLACE INTO push_subscriptions
            (id, kind, endpoint, p256dh, auth, topic, user_id, locale, active,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (sub_id, kind, data.endpoint, data.p256dh, data.auth, data.topic,
             user_id, data.locale, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM push_subscriptions WHERE id = ?", (sub_id,)
        ).fetchone()
    out = db.row_to_dict(row)
    out["created"] = created
    return out


def unsubscribe(endpoint: str) -> dict:
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint required")
    with db.get_db() as conn:
        cur = conn.execute(
            "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        )
        conn.commit()
    return {"ok": True, "removed": cur.rowcount}


def list_subscriptions(topic: Optional[str] = None, active_only: bool = True) -> dict:
    sql = "SELECT * FROM push_subscriptions WHERE 1=1"
    params: list = []
    if active_only:
        sql += " AND active = 1"
    if topic is not None:
        sql += " AND topic = ?"
        params.append(topic)
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"records": [db.row_to_dict(r) for r in rows]}


def _subscriptions_for_operation(operation_id: Optional[str]) -> List[dict]:
    """Active subs for an operation's topic plus global (topic IS NULL) subs."""
    with db.get_db() as conn:
        if operation_id:
            rows = conn.execute(
                "SELECT * FROM push_subscriptions "
                "WHERE active = 1 AND (topic = ? OR topic IS NULL)",
                (operation_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM push_subscriptions WHERE active = 1"
            ).fetchall()
    return [db.row_to_dict(r) for r in rows]


def send_to_operation(
    operation_id: Optional[str],
    title: str,
    body: str,
    alert_id: Optional[str] = None,
    actor: str = "system",
    category: str = "broadcasts",
    force: bool = False,
) -> dict:
    """Fan an alert out to every subscription watching an operation (+ globals).

    Records one ``messages`` row per subscription so delivery is trackable.
    Returns ``{recipients, sent, failed, skipped}``.

    Each subscription is filtered through the recipient's notification
    preferences (plan-24 Phase 4): a user who muted ``category`` or this
    operation, or set quiet hours / a near-me radius, is skipped — unless
    ``force`` is set (life-safety) or the subscription is anonymous. ``skipped``
    counts recipients dropped by the preference gate.
    """
    from modules import messaging, notifications, providers

    all_subs = _subscriptions_for_operation(operation_id)
    subs = notifications.filter_push_subscriptions(
        all_subs, category, operation_id=operation_id, force=force
    )
    skipped = len(all_subs) - len(subs)
    cfg = messaging.get_provider_config("push")
    sent, failed = 0, 0
    for sub in subs:
        result = providers.send_push(sub, title, body, cfg)
        messaging.record_message(
            channel="push",
            direction="outbound",
            to_address=sub.get("endpoint"),
            subject=title,
            body=body,
            status=result["status"],
            error=result.get("error"),
            external_id=result.get("external_id"),
            operation_id=operation_id,
            alert_id=alert_id,
            locale=sub.get("locale"),
        )
        if result["status"] == "sent":
            sent += 1
        else:
            failed += 1
    return {"recipients": len(subs), "sent": sent, "failed": failed, "skipped": skipped}
