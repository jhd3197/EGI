"""Operation alerts (plan-11 §3): broadcast one message to every channel.

A commander posts an alert to an operation; it fans out to all subscribed
channels — push (every device on the operation's topic), SMS (every contact
number on the operation), and email (every contact email on the operation).

Each delivery is recorded in ``messages`` with a shared ``alert_id`` so the whole
broadcast is one trackable unit and per-message delivery status is queryable.
"""

import re
import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
from models import now_iso
from modules import messaging, providers, push, sms, templates

ALL_CHANNELS = ("push", "sms", "email")


def _operation(op_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (op_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Operation not found")
    return db.row_to_dict(row)


def _operation_emails(op_id: str) -> List[str]:
    """Distinct contact addresses for the operation that look like emails."""
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT contact FROM persons "
            "WHERE disaster_id = ? AND contact LIKE '%@%' AND merged_into IS NULL",
            (op_id,),
        ).fetchall()
    out, seen = [], set()
    for row in rows:
        addr = (row["contact"] or "").strip()
        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr) and addr.lower() not in seen:
            seen.add(addr.lower())
            out.append(addr)
    return out


def create_alert(op_id: str, data, actor: str = "system") -> dict:
    """Broadcast an alert across the requested channels for an operation."""
    op = _operation(op_id)
    op_name = op.get("name") or op_id
    alert_id = f"alert-{uuid.uuid4().hex[:10]}"
    channels = [c for c in (data.channels or ALL_CHANNELS) if c in ALL_CHANNELS]
    if not channels:
        raise HTTPException(status_code=400, detail="no valid channels")

    template_name = data.template_name or "alert"
    if not templates.template_exists(template_name):
        raise HTTPException(status_code=400, detail=f"unknown template: {template_name}")
    variables = {
        "title": data.title or "",
        "body": data.body or "",
        "operation_name": op_name,
    }
    if data.variables:
        variables.update(data.variables)
    rendered = templates.render(template_name, variables, data.locale)
    locale = rendered.get("locale", data.locale)
    title = data.title or rendered.get("subject") or op_name
    body = rendered.get("body") or ""
    if not body and not data.title:
        raise HTTPException(status_code=400, detail="empty alert (need title/body or template)")

    results = {}

    if "push" in channels:
        # An operation alert is the 'broadcasts' category. `life_safety` lets a
        # commander override recipients' notification preferences (plan-24 §8).
        results["push"] = push.send_to_operation(
            op_id, title, body, alert_id=alert_id, actor=actor,
            category="broadcasts", force=bool(getattr(data, "life_safety", False)),
        )

    if "sms" in channels:
        results["sms"] = _broadcast_channel(
            "sms", sms._operation_phones(op_id), op_id, alert_id, body, None, None,
            template_name, locale,
        )

    if "email" in channels:
        results["email"] = _broadcast_channel(
            "email", _operation_emails(op_id), op_id, alert_id, body,
            rendered.get("subject") or title, rendered.get("html"),
            template_name, locale,
        )

    total_sent = sum(r.get("sent", 0) for r in results.values())
    total_recipients = sum(r.get("recipients", 0) for r in results.values())
    _audit(actor, "alert_create", alert_id,
           f"op={op_id} channels={','.join(channels)} sent={total_sent}")
    return {
        "alert_id": alert_id,
        "operation_id": op_id,
        "title": title,
        "channels": results,
        "recipients": total_recipients,
        "sent": total_sent,
        "created_at": now_iso(),
    }


def _broadcast_channel(
    channel: str, recipients: List[str], op_id: str, alert_id: str,
    body: str, subject: Optional[str], html: Optional[str],
    template_name: str, locale: Optional[str],
) -> dict:
    """Send `body` to every recipient on one channel, recording each message."""
    cfg = messaging.get_provider_config(channel)
    sent, failed = 0, 0
    for to in recipients:
        if channel == "sms":
            result = providers.send_sms(to, body, cfg)
        else:  # email
            result = providers.send_email(to, subject or "EGI", body, html, cfg)
        messaging.record_message(
            channel=channel,
            direction="outbound",
            to_address=to,
            subject=subject,
            body=body,
            template_name=template_name,
            status=result["status"],
            error=result.get("error"),
            external_id=result.get("external_id"),
            operation_id=op_id,
            alert_id=alert_id,
            locale=locale,
        )
        if result["status"] == "sent":
            sent += 1
        else:
            failed += 1
    return {"recipients": len(recipients), "sent": sent, "failed": failed}


def list_alerts(op_id: str) -> dict:
    """Summarize past alerts for an operation (grouped by alert_id)."""
    with db.get_db() as conn:
        rows = conn.execute(
            """
            SELECT alert_id,
                   MIN(created_at) AS created_at,
                   MAX(subject)    AS subject,
                   COUNT(*)        AS total,
                   SUM(CASE WHEN status IN ('sent','delivered') THEN 1 ELSE 0 END) AS sent,
                   GROUP_CONCAT(DISTINCT channel) AS channels
            FROM messages
            WHERE operation_id = ? AND alert_id IS NOT NULL
            GROUP BY alert_id
            ORDER BY created_at DESC
            """,
            (op_id,),
        ).fetchall()
    records = []
    for r in rows:
        d = db.row_to_dict(r)
        d["channels"] = (d.get("channels") or "").split(",") if d.get("channels") else []
        records.append(d)
    return {"records": records}


def _audit(actor: str, action: str, target_id: Optional[str], detail: str = "") -> None:
    from modules import audit

    audit.log_action(actor, action, "alert", target_id, detail=detail)
