"""Communications-hub core (plan-11): persist + dispatch + track every message.

This is the channel-agnostic layer. It:
  * renders a template (or takes a raw body),
  * picks the configured provider for the channel,
  * calls the right ``providers.send_*`` driver,
  * writes a row to ``messages`` with the resulting delivery status,
  * and exposes status updates (for provider callbacks) + listing.

SMS-reply parsing lives in ``modules/sms.py``; push fan-out lives in
``modules/push.py``; alerts orchestrate all three in ``modules/alerts.py``. They
all funnel their persistence through ``record_message`` / ``update_status`` here
so a commander sees one unified message log.
"""

import json
import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
from models import (
    VALID_CHANNELS, now_iso, validate_message_status,
)
from modules import providers, templates


# ── Provider config (message_providers) ──────────────────────────────────────

def _provider_to_dict(row) -> dict:
    d = db.row_to_dict(row)
    try:
        d["config"] = json.loads(d.get("config_json") or "{}")
    except (ValueError, TypeError):
        d["config"] = {}
    return d


def list_providers(channel: Optional[str] = None) -> dict:
    sql = "SELECT * FROM message_providers"
    params: list = []
    if channel:
        sql += " WHERE channel = ?"
        params.append(channel)
    sql += " ORDER BY channel, is_default DESC, created_at"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"records": [_provider_to_dict(r) for r in rows]}


def create_provider(data, actor: str = "system") -> dict:
    if data.channel not in VALID_CHANNELS:
        raise HTTPException(status_code=400, detail=f"invalid channel: {data.channel}")
    now = now_iso()
    pid = data.id or f"prov-{uuid.uuid4().hex[:8]}"
    config_json = json.dumps(data.config or {})
    with db.get_db() as conn:
        if data.is_default:
            conn.execute(
                "UPDATE message_providers SET is_default = 0 WHERE channel = ?",
                (data.channel,),
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO message_providers
            (id, channel, name, config_json, is_default, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pid, data.channel, data.name, config_json,
             int(data.is_default or 0), int(data.active if data.active is not None else 1),
             now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM message_providers WHERE id = ?", (pid,)).fetchone()
    _audit(actor, "provider_create", pid, f"channel={data.channel}")
    return _provider_to_dict(row)


def delete_provider(provider_id: str, actor: str = "system") -> dict:
    with db.get_db() as conn:
        cur = conn.execute("DELETE FROM message_providers WHERE id = ?", (provider_id,))
        conn.commit()
    if not cur.rowcount:
        raise HTTPException(status_code=404, detail="Provider not found")
    _audit(actor, "provider_delete", provider_id)
    return {"ok": True, "deleted": provider_id}


def get_provider_config(channel: str) -> Optional[dict]:
    """Return the active default provider's parsed config for a channel, or None.

    None means "fall back to env defaults" (i.e. the ``log`` driver) — the hub
    works with zero configured providers.
    """
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM message_providers "
            "WHERE channel = ? AND active = 1 ORDER BY is_default DESC, created_at LIMIT 1",
            (channel,),
        ).fetchone()
    if not row:
        return None
    return _provider_to_dict(row).get("config") or {}


# ── Message persistence ──────────────────────────────────────────────────────

def record_message(
    *,
    channel: str,
    direction: str,
    to_address: Optional[str] = None,
    from_address: Optional[str] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    template_name: Optional[str] = None,
    status: str = "pending",
    error: Optional[str] = None,
    external_id: Optional[str] = None,
    provider_id: Optional[str] = None,
    person_id: Optional[str] = None,
    operation_id: Optional[str] = None,
    alert_id: Optional[str] = None,
    locale: Optional[str] = None,
    message_id: Optional[str] = None,
) -> dict:
    """Insert one message row and return it as a dict."""
    now = now_iso()
    mid = message_id or f"msg-{uuid.uuid4().hex[:10]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, operation_id, person_id, channel, direction, to_address, from_address,
             subject, body, template_name, status, error, external_id, provider_id,
             alert_id, locale, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (mid, operation_id, person_id, channel, direction, to_address, from_address,
             subject, body, template_name, status, error, external_id, provider_id,
             alert_id, locale, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
    return db.row_to_dict(row)


def update_status(
    message_id: str,
    status: str,
    external_id: Optional[str] = None,
    error: Optional[str] = None,
    by_external: bool = False,
    actor: str = "system",
) -> dict:
    """Update a message's delivery status (used by provider status callbacks)."""
    if not validate_message_status(status):
        raise HTTPException(status_code=400, detail=f"invalid status: {status}")
    col = "external_id" if by_external else "id"
    sets = ["status = ?", "updated_at = ?"]
    params: list = [status, now_iso()]
    if external_id is not None:
        sets.append("external_id = ?")
        params.append(external_id)
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    params.append(message_id)
    with db.get_db() as conn:
        cur = conn.execute(
            f"UPDATE messages SET {', '.join(sets)} WHERE {col} = ?", params
        )
        conn.commit()
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="Message not found")
        row = conn.execute(
            f"SELECT * FROM messages WHERE {col} = ? ORDER BY updated_at DESC LIMIT 1",
            (message_id,),
        ).fetchone()
    _audit(actor, "message_status", message_id, f"status={status}")
    return db.row_to_dict(row)


def list_messages(
    operation_id: Optional[str] = None,
    person_id: Optional[str] = None,
    channel: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    alert_id: Optional[str] = None,
    limit: int = 200,
) -> dict:
    sql = "SELECT * FROM messages WHERE 1=1"
    params: list = []
    for col, val in (
        ("operation_id", operation_id), ("person_id", person_id),
        ("channel", channel), ("direction", direction), ("status", status),
        ("alert_id", alert_id),
    ):
        if val:
            sql += f" AND {col} = ?"
            params.append(val)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"records": [db.row_to_dict(r) for r in rows]}


# ── Outbound dispatch ────────────────────────────────────────────────────────

def _render(template_name: Optional[str], body: Optional[str], subject: Optional[str],
            variables: Optional[dict], locale: Optional[str]) -> dict:
    """Resolve subject/body/html/locale from a template or raw fields."""
    if template_name:
        if not templates.template_exists(template_name):
            raise HTTPException(status_code=400, detail=f"unknown template: {template_name}")
        rendered = templates.render(template_name, variables or {}, locale)
        return {
            "subject": subject or rendered.get("subject"),
            "body": body or rendered.get("body"),
            "html": rendered.get("html"),
            "locale": rendered.get("locale", locale),
        }
    return {"subject": subject, "body": body, "html": None, "locale": locale}


def send_message(req, actor: str = "system") -> dict:
    """Render (if templated), dispatch via the channel provider, and persist.

    Supports sms + email here. Push is sent per-subscription via modules/push.py
    (it needs the subscription key material), and alerts orchestrate all three.
    """
    channel = req.channel
    if channel not in ("sms", "email"):
        raise HTTPException(status_code=400, detail=f"send_message supports sms|email (got {channel})")
    if not req.to_address:
        raise HTTPException(status_code=400, detail="to_address required")

    rendered = _render(req.template_name, req.body, req.subject, req.variables, req.locale)
    if not rendered["body"]:
        raise HTTPException(status_code=400, detail="empty message body")

    cfg = get_provider_config(channel)
    if channel == "sms":
        result = providers.send_sms(req.to_address, rendered["body"], cfg)
    else:  # email
        subject = rendered["subject"] or "EGI"
        result = providers.send_email(
            req.to_address, subject, rendered["body"], rendered.get("html"), cfg
        )

    return record_message(
        channel=channel,
        direction="outbound",
        to_address=req.to_address,
        subject=rendered["subject"],
        body=rendered["body"],
        template_name=req.template_name,
        status=result["status"],
        error=result.get("error"),
        external_id=result.get("external_id"),
        person_id=req.person_id,
        operation_id=req.operation_id,
        locale=rendered.get("locale"),
    )


def _audit(actor: str, action: str, target_id: Optional[str], detail: str = "") -> None:
    from modules import audit

    audit.log_action(actor, action, "message", target_id, detail=detail)
