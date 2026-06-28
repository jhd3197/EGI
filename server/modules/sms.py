"""SMS: text-only emergency check-in + two-way conversation (plan-02, plan-11).

Inbound. A community member with no data/internet texts a configured number; a
gateway (Twilio, a local GSM modem, or a community provider) forwards it to
``POST /sms/webhook``. Two kinds of inbound message are handled:

  * **Check-in** — ``EGI CHECKIN <cedula> <name> <location>``. Parsed into a
    ``safe`` self check-in stored as an UNTRUSTED record (source='sms',
    reviewed=0) so a moderator must approve it before it shows in public search.
  * **Reply** — any other text from a number we previously messaged about a
    person. We attach it to that person as a report (PFIF note, source='sms')
    so a family reply ("la vi en el refugio sur") lands on the right record
    (plan-11 two-way conversation). Inbound text with no open conversation is
    rejected (400), preserving the original check-in-only contract.

Outbound + broadcast live alongside, funnelling through ``modules/messaging.py``
so everything shows in the unified message log with delivery status.

Privacy: text-only. No photos or exact coordinates (see plan §14).
"""

import re
import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
import normalize
from models import ReportRecord, SendMessageRequest, now_iso

KEYWORD = "EGI CHECKIN"


def _norm_phone(value: Optional[str]) -> str:
    """Reduce a phone number to digits (+ optional leading +) for matching."""
    return normalize.normalize_phone(value, "plus")


def parse_checkin(body: str) -> dict:
    """Parse an EGI CHECKIN message into {cedula, name, location}.

    Raises HTTPException(400) when the keyword is missing or no cédula is found.
    """
    if not body:
        raise HTTPException(status_code=400, detail="empty SMS body")
    text = body.strip()
    upper = text.upper()
    if not upper.startswith(KEYWORD):
        raise HTTPException(status_code=400, detail="not an EGI CHECKIN message")

    remainder = text[len(KEYWORD):].strip()
    if not remainder:
        raise HTTPException(status_code=400, detail="missing check-in fields")

    if "," in remainder:
        parts = [p.strip() for p in remainder.split(",")]
        cedula = parts[0] if len(parts) > 0 else ""
        name = parts[1] if len(parts) > 1 else ""
        location = parts[2] if len(parts) > 2 else ""
    else:
        # Whitespace form: first token is the cédula, last token the location,
        # everything between is the name (best effort).
        tokens = remainder.split()
        cedula = tokens[0] if tokens else ""
        if len(tokens) >= 3:
            name = " ".join(tokens[1:-1])
            location = tokens[-1]
        elif len(tokens) == 2:
            name, location = tokens[1], ""
        else:
            name, location = "", ""

    if not cedula:
        raise HTTPException(status_code=400, detail="missing cédula in check-in")
    return {"cedula": cedula, "name": name, "location": location}


def receive_checkin(body: str, sender: Optional[str] = None) -> dict:
    """Create a ``safe`` self check-in person record from an SMS body.

    Stored as source='sms', reviewed=0 (untrusted → moderator-only until approved).
    """
    fields = parse_checkin(body)
    now = now_iso()
    person_id = f"egi-sms-{uuid.uuid4().hex[:8]}"
    name = fields["name"] or "Check-in SMS"
    location = fields["location"]
    # Provenance keeps the raw text + sender (digits only, light privacy) for audit.
    safe_sender = re.sub(r"[^0-9+]", "", sender) if sender else None
    provenance = f"SMS check-in from {safe_sender or 'unknown'}: {body.strip()[:160]}"

    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO persons
            (id, name, status, location, last_known_location, cedula, source,
             provenance, reviewed, reporter_name, created_at, updated_at)
            VALUES (?, ?, 'safe', ?, ?, ?, 'sms', ?, 0, ?, ?, ?)
            """,
            (person_id, name, location, location, fields["cedula"], provenance,
             name, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()

    out = {"created": db.row_to_dict(row), "parsed": fields}

    # Attach a PFIF note linking the check-in evidence to the person, mirroring
    # the two-way receive_reply path. Best-effort: a report failure must never
    # break the person creation. Lazy import avoids a circular import.
    try:
        from modules import reports

        out["report"] = reports.create_person_report(
            person_id,
            ReportRecord(
                author_name=name,
                status="safe",
                note=f"Auto check-in vía SMS — {location}" if location
                else "Auto check-in vía SMS",
                location=location,
                source="sms",
                confidence="self",
            ),
        )
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[EGI sms] check-in report failed for {person_id}: {e}")

    # Match the SMS check-in against the registry (plan-27 Phase 5): a check-in
    # often duplicates a family's missing report, so queue a merge candidate for
    # review before it goes public. Best-effort; never break the webhook.
    try:
        from modules import dedup

        dedup.generate_candidates_for(person_id)
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[EGI sms] candidate scan skipped for {person_id}: {e}")

    # Best-effort confirmation SMS back to the sender (never break the webhook).
    if sender:
        try:
            out["confirmation"] = _send_checkin_confirmation(
                sender, person_id, (out["created"] or {}).get("disaster_id")
            )
        except Exception as e:  # pragma: no cover - defensive
            _log(f"[EGI sms] check-in confirmation failed for {safe_sender}: {e}")

    return out


def _log(msg: str) -> None:
    """ASCII-safe print so a constrained Windows console never breaks a webhook."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


def _send_checkin_confirmation(
    sender: str, person_id: str, operation_id: Optional[str] = None
) -> dict:
    """Send the Spanish-first check-in confirmation SMS, logged as outbound."""
    from modules import messaging

    req = SendMessageRequest(
        channel="sms",
        to_address=sender,
        person_id=person_id,
        operation_id=operation_id,
        template_name="checkin_confirmation",
    )
    return messaging.send_message(req, actor="system")


def is_checkin(body: str) -> bool:
    return bool(body) and body.strip().upper().startswith(KEYWORD)


def receive_sms(body: str, sender: Optional[str] = None) -> dict:
    """Top-level inbound SMS handler: route to check-in or two-way reply.

    A check-in (``EGI CHECKIN …``) creates a person record. Any other text is
    treated as a reply to an open conversation and attached to the matching
    person as a report. Text with neither shape raises 400 (unchanged contract).
    """
    if is_checkin(body):
        return receive_checkin(body, sender)
    return receive_reply(body, sender)


def _find_open_conversation(sender: Optional[str]) -> Optional[str]:
    """Return the person_id of the most recent outbound SMS to ``sender``."""
    norm = _norm_phone(sender)
    if not norm:
        return None
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT to_address, person_id FROM messages "
            "WHERE channel = 'sms' AND direction = 'outbound' AND person_id IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    for row in rows:
        if _norm_phone(row["to_address"]) == norm:
            return row["person_id"]
    return None


def receive_reply(body: str, sender: Optional[str] = None) -> dict:
    """Attach an inbound reply to the person we last messaged at this number.

    Raises 400 when the text is not a check-in and there is no open conversation
    for the sender (keeps the webhook from accepting random texts).
    """
    if not body or not body.strip():
        raise HTTPException(status_code=400, detail="empty SMS body")
    person_id = _find_open_conversation(sender)
    if not person_id:
        raise HTTPException(
            status_code=400,
            detail="not an EGI CHECKIN and no open conversation for this sender",
        )
    # Lazy import avoids a circular import (messaging imports nothing from sms,
    # but reports/messaging both touch db — keep the dependency one-directional).
    from modules import messaging, reports

    safe_sender = _norm_phone(sender)
    report = reports.create_person_report(
        person_id,
        ReportRecord(
            author_name=safe_sender or "SMS",
            note=body.strip()[:1000],
            source="sms",
            confidence="witness",
        ),
    )
    msg = messaging.record_message(
        channel="sms",
        direction="inbound",
        from_address=safe_sender or None,
        body=body.strip()[:1000],
        status="delivered",
        person_id=person_id,
    )
    return {"matched": True, "person_id": person_id, "report": report, "message": msg}


# ── Outbound notifications + broadcast (plan-11) ──────────────────────────────

def _person(conn, person_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    return db.row_to_dict(row) if row else None


def notify_person(
    person_id: str,
    template_name: str,
    to_address: Optional[str] = None,
    extra_vars: Optional[dict] = None,
    locale: Optional[str] = None,
    actor: str = "system",
) -> dict:
    """Send a templated SMS to a person's contact number (or an override).

    Templates: ``report_received``, ``status_changed``, ``request_info``. The
    person's name/status fill the template variables automatically.
    """
    from modules import messaging

    with db.get_db() as conn:
        person = _person(conn, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    to = to_address or person.get("contact")
    if not to:
        raise HTTPException(status_code=400, detail="no contact number for this person")
    variables = {
        "person_name": person.get("name") or person.get("cedula") or "",
        "status": person.get("status") or "",
        "operation_name": person.get("disaster_id") or "",
    }
    if extra_vars:
        variables.update(extra_vars)
    req = SendMessageRequest(
        channel="sms",
        to_address=to,
        person_id=person_id,
        operation_id=person.get("disaster_id"),
        template_name=template_name,
        variables=variables,
        locale=locale,
    )
    return messaging.send_message(req, actor=actor)


def _operation_phones(operation_id: str) -> List[str]:
    """Collect distinct contact phone numbers for persons in an operation."""
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT contact FROM persons "
            "WHERE disaster_id = ? AND contact IS NOT NULL AND contact != '' "
            "AND merged_into IS NULL",
            (operation_id,),
        ).fetchall()
    phones, seen = [], set()
    for row in rows:
        norm = _norm_phone(row["contact"])
        # Only keep things that look like phone numbers (>= 7 digits).
        if len(re.sub(r"\D", "", norm)) >= 7 and norm not in seen:
            seen.add(norm)
            phones.append(row["contact"])
    return phones


def broadcast(data, actor: str = "system") -> dict:
    """Broadcast one SMS to a list of numbers (explicit, or an operation's contacts)."""
    from modules import messaging

    recipients = list(data.to_addresses or [])
    if not recipients and data.operation_id:
        recipients = _operation_phones(data.operation_id)
    if not recipients:
        raise HTTPException(status_code=400, detail="no recipients")

    sent, failed, results = 0, 0, []
    for to in recipients:
        req = SendMessageRequest(
            channel="sms",
            to_address=to,
            operation_id=data.operation_id,
            body=data.body,
            template_name=data.template_name,
            variables=data.variables,
            locale=data.locale,
        )
        msg = messaging.send_message(req, actor=actor)
        results.append(msg)
        if msg["status"] == "sent":
            sent += 1
        else:
            failed += 1
    return {"recipients": len(recipients), "sent": sent, "failed": failed, "messages": results}
