"""Pluggable messaging providers for the communications hub (plan-11).

The hub never talks to Twilio/SMTP/FCM directly — it calls ``send_sms`` /
``send_email`` / ``send_push`` here, and the *driver* is chosen from config. This
is what makes the providers swappable: moving from Twilio to another SMS gateway
is a config change (``SMS_PROVIDER`` env or a ``message_providers`` row), not a
code change (success criterion §5).

Design mirrors ``ai.py``: **always degrades, never hard-fails the request.**
  * The default driver for every channel is ``log`` — it "sends" by recording the
    message and returns ``sent``. This keeps dev, demos and the test suite working
    with zero credentials.
  * Real drivers (``twilio``, ``smtp``, ``webpush``, ``fcm``) activate only when
    their config/credentials are present. If a real driver is selected but its
    optional dependency or credentials are missing, we return ``failed`` with a
    short reason rather than raising.

Each ``send_*`` returns a dict: ``{status, external_id, error}`` where ``status``
is one of the ``messages`` lifecycle values (``sent``/``failed`` here; delivery
confirmation arrives later via a provider status callback).
"""

import json
import os
import smtplib
import ssl
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional


def _ok(external_id: Optional[str] = None) -> dict:
    return {"status": "sent", "external_id": external_id, "error": None}


def _fail(error: str) -> dict:
    return {"status": "failed", "external_id": None, "error": error[:300]}


def _cfg_get(cfg: Optional[dict], key: str, env: str, default: Optional[str] = None) -> Optional[str]:
    """Read a setting from the provider config row first, then env, then default."""
    if cfg and cfg.get(key):
        return cfg.get(key)
    return os.environ.get(env, default)


def _driver(cfg: Optional[dict], env: str, default: str = "log") -> str:
    return (_cfg_get(cfg, "driver", env, default) or default).lower()


# ── SMS ──────────────────────────────────────────────────────────────────────

def send_sms(to_address: str, body: str, cfg: Optional[dict] = None) -> dict:
    driver = _driver(cfg, "SMS_PROVIDER")
    if not to_address:
        return _fail("missing destination number")
    if driver == "log":
        print(f"[EGI sms:log] -> {to_address}: {body[:120]}")
        return _ok(external_id="log")
    if driver == "twilio":
        return _send_twilio(to_address, body, cfg)
    return _fail(f"unknown sms driver: {driver}")


def _send_twilio(to_address: str, body: str, cfg: Optional[dict]) -> dict:
    sid = _cfg_get(cfg, "account_sid", "TWILIO_ACCOUNT_SID")
    token = _cfg_get(cfg, "auth_token", "TWILIO_AUTH_TOKEN")
    sender = _cfg_get(cfg, "from", "TWILIO_FROM")
    if not (sid and token and sender):
        return _fail("twilio not configured (need account_sid, auth_token, from)")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urllib.parse.urlencode({"To": to_address, "From": sender, "Body": body}).encode()
    auth = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    auth.add_password(None, url, sid, token)
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(auth))
    try:
        with opener.open(urllib.request.Request(url, data=data), timeout=15) as resp:
            payload = json.loads(resp.read().decode())
        return _ok(external_id=payload.get("sid"))
    except Exception as e:  # pragma: no cover - network path
        return _fail(f"twilio send failed: {e}")


# ── Email ──────────────────────────────────────────────────────────────────────

def send_email(
    to_address: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
    cfg: Optional[dict] = None,
) -> dict:
    driver = _driver(cfg, "EMAIL_PROVIDER")
    if not to_address:
        return _fail("missing destination address")
    if driver == "log":
        print(f"[EGI email:log] -> {to_address}: {subject}")
        return _ok(external_id="log")
    if driver == "smtp":
        return _send_smtp(to_address, subject, body, html, cfg)
    return _fail(f"unknown email driver: {driver}")


def _send_smtp(
    to_address: str, subject: str, body: str, html: Optional[str], cfg: Optional[dict]
) -> dict:  # pragma: no cover - network path
    host = _cfg_get(cfg, "host", "SMTP_HOST")
    if not host:
        return _fail("smtp not configured (need host)")
    port = int(_cfg_get(cfg, "port", "SMTP_PORT", "587") or 587)
    user = _cfg_get(cfg, "user", "SMTP_USER")
    password = _cfg_get(cfg, "password", "SMTP_PASSWORD")
    sender = _cfg_get(cfg, "from", "SMTP_FROM") or user or "egi@localhost"
    use_tls = (_cfg_get(cfg, "use_tls", "SMTP_USE_TLS", "true") or "true").lower() != "false"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_address
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls(context=ssl.create_default_context())
            if user and password:
                server.login(user, password)
            server.sendmail(sender, [to_address], msg.as_string())
        return _ok()
    except Exception as e:
        return _fail(f"smtp send failed: {e}")


# ── Push ──────────────────────────────────────────────────────────────────────

def vapid_public_key() -> Optional[str]:
    """The VAPID public key clients need to subscribe, or None if not configured."""
    return os.environ.get("VAPID_PUBLIC_KEY") or None


def send_push(subscription: dict, title: str, body: str, cfg: Optional[dict] = None) -> dict:
    """Send a push notification to one subscription (webpush or fcm)."""
    kind = subscription.get("kind", "webpush")
    payload = json.dumps({"title": title, "body": body})
    # The default driver simply logs; real delivery needs VAPID/FCM credentials
    # AND the optional pywebpush dependency (web push payload encryption is
    # non-trivial), so absent those we degrade like every other driver.
    driver = _driver(cfg, "PUSH_PROVIDER")
    if driver == "log":
        print(f"[EGI push:log] -> {subscription.get('endpoint', '')[:48]}…: {title}")
        return _ok(external_id="log")
    if kind == "fcm" or driver == "fcm":
        return _send_fcm(subscription, title, body, cfg)
    if kind == "webpush" or driver == "webpush":
        return _send_webpush(subscription, payload, cfg)
    return _fail(f"unknown push kind/driver: {kind}/{driver}")


def _send_webpush(subscription: dict, payload: str, cfg: Optional[dict]) -> dict:  # pragma: no cover
    private = _cfg_get(cfg, "vapid_private_key", "VAPID_PRIVATE_KEY")
    subject = _cfg_get(cfg, "vapid_subject", "VAPID_SUBJECT", "mailto:egi@localhost")
    if not private:
        return _fail("webpush not configured (need VAPID_PRIVATE_KEY)")
    try:
        from pywebpush import webpush  # optional dependency
    except Exception:
        return _fail("pywebpush not installed")
    try:
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": {"p256dh": subscription.get("p256dh"), "auth": subscription.get("auth")},
            },
            data=payload,
            vapid_private_key=private,
            vapid_claims={"sub": subject},
        )
        return _ok()
    except Exception as e:
        return _fail(f"webpush send failed: {e}")


def _send_fcm(subscription: dict, title: str, body: str, cfg: Optional[dict]) -> dict:  # pragma: no cover
    server_key = _cfg_get(cfg, "server_key", "FCM_SERVER_KEY")
    if not server_key:
        return _fail("fcm not configured (need FCM_SERVER_KEY)")
    data = json.dumps({
        "to": subscription["endpoint"],
        "notification": {"title": title, "body": body},
    }).encode()
    req = urllib.request.Request(
        "https://fcm.googleapis.com/fcm/send",
        data=data,
        headers={"Authorization": f"key={server_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode())
        return _ok(external_id=str(payload.get("multicast_id") or ""))
    except Exception as e:
        return _fail(f"fcm send failed: {e}")
