"""Email helpers (plan-11): welcome, password reset, and alert emails.

Thin convenience layer over ``modules/messaging.py`` so callers don't repeat the
template + provider plumbing. Every send is persisted in the unified ``messages``
log with delivery status. Like the SMS layer it degrades to the ``log`` driver
when no SMTP/SendGrid provider is configured, so flows work with zero credentials.
"""

import os
from typing import Optional


def _base_url() -> str:
    return (os.environ.get("PUBLIC_BASE_URL") or "http://localhost:3000").rstrip("/")


def send_email(
    to_address: str,
    template_name: str,
    variables: Optional[dict] = None,
    locale: Optional[str] = None,
    subject: Optional[str] = None,
    person_id: Optional[str] = None,
    operation_id: Optional[str] = None,
    actor: str = "system",
) -> dict:
    """Send a templated email through the hub. Returns the persisted message dict."""
    from models import SendMessageRequest
    from modules import messaging

    req = SendMessageRequest(
        channel="email",
        to_address=to_address,
        subject=subject,
        template_name=template_name,
        variables=variables or {},
        locale=locale,
        person_id=person_id,
        operation_id=operation_id,
    )
    return messaging.send_message(req, actor=actor)


def send_welcome(user: dict, locale: Optional[str] = None, actor: str = "system") -> dict:
    return send_email(
        user["email"], "welcome",
        variables={"name": user.get("name") or user.get("email"), "role": user.get("role", "")},
        locale=locale or user.get("locale"), actor=actor,
    )


def send_password_reset(
    user: dict, raw_token: str, ttl_minutes: int = 60,
    locale: Optional[str] = None, actor: str = "system",
) -> dict:
    """Email a password-reset link built from the raw (un-hashed) token."""
    reset_url = f"{_base_url()}/reset-password?token={raw_token}"
    return send_email(
        user["email"], "password_reset",
        variables={"reset_url": reset_url, "token": raw_token, "expires_minutes": ttl_minutes},
        locale=locale or user.get("locale"), actor=actor,
    )
