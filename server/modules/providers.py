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

import normalize


def _log(msg: str) -> None:
    """Print a driver log line without ever raising on a constrained console.

    The bot replies contain emoji/accents; a cp1252 stdout (Windows) would raise
    UnicodeEncodeError on print(). We degrade to an ASCII-safe rendering rather
    than let a debug log line break an inbound webhook.
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


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


# ── WhatsApp (plan-14) ───────────────────────────────────────────────────────
#
# Two real drivers behind the same abstraction: ``twilio`` (Twilio's WhatsApp
# API, same Messages.json endpoint as SMS but a ``whatsapp:`` address prefix) and
# ``meta`` (the WhatsApp Cloud API graph endpoint). Default ``log`` driver keeps
# the bot fully testable with zero credentials.

def send_whatsapp(to_address: str, body: str, cfg: Optional[dict] = None) -> dict:
    driver = _driver(cfg, "WHATSAPP_PROVIDER")
    if not to_address:
        return _fail("missing destination number")
    if driver == "log":
        _log(f"[EGI whatsapp:log] -> {to_address}: {body[:120]}")
        return _ok(external_id="log")
    if driver == "twilio":
        return _send_twilio_whatsapp(to_address, body, cfg)
    if driver == "meta":
        return _send_meta_whatsapp(to_address, body, cfg)
    return _fail(f"unknown whatsapp driver: {driver}")


def _wa_addr(value: str) -> str:
    """Ensure a Twilio WhatsApp address carries the ``whatsapp:`` prefix."""
    value = (value or "").strip()
    return value if value.startswith("whatsapp:") else f"whatsapp:{value}"


def _send_twilio_whatsapp(to_address: str, body: str, cfg: Optional[dict]) -> dict:  # pragma: no cover - network path
    sid = _cfg_get(cfg, "account_sid", "TWILIO_ACCOUNT_SID")
    token = _cfg_get(cfg, "auth_token", "TWILIO_AUTH_TOKEN")
    sender = _cfg_get(cfg, "from", "TWILIO_WHATSAPP_FROM")
    if not (sid and token and sender):
        return _fail("twilio whatsapp not configured (need account_sid, auth_token, from)")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urllib.parse.urlencode(
        {"To": _wa_addr(to_address), "From": _wa_addr(sender), "Body": body}
    ).encode()
    auth = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    auth.add_password(None, url, sid, token)
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(auth))
    try:
        with opener.open(urllib.request.Request(url, data=data), timeout=15) as resp:
            payload = json.loads(resp.read().decode())
        return _ok(external_id=payload.get("sid"))
    except Exception as e:
        return _fail(f"twilio whatsapp send failed: {e}")


def _send_meta_whatsapp(to_address: str, body: str, cfg: Optional[dict]) -> dict:  # pragma: no cover - network path
    token = _cfg_get(cfg, "access_token", "WHATSAPP_ACCESS_TOKEN")
    phone_id = _cfg_get(cfg, "phone_number_id", "WHATSAPP_PHONE_NUMBER_ID")
    if not (token and phone_id):
        return _fail("meta whatsapp not configured (need access_token, phone_number_id)")
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": normalize.normalize_phone(to_address, "digits"),
        "type": "text",
        "text": {"body": body},
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        msgs = data.get("messages") or [{}]
        return _ok(external_id=msgs[0].get("id"))
    except Exception as e:
        return _fail(f"meta whatsapp send failed: {e}")


# ── Telegram (plan-14) ───────────────────────────────────────────────────────
#
# Telegram's Bot API is a single HTTPS call with the bot token in the path. The
# ``log`` default keeps the bot testable with no token.

def send_telegram(to_address: str, body: str, cfg: Optional[dict] = None) -> dict:
    driver = _driver(cfg, "TELEGRAM_PROVIDER")
    if not to_address:
        return _fail("missing destination chat id")
    if driver == "log":
        _log(f"[EGI telegram:log] -> {to_address}: {body[:120]}")
        return _ok(external_id="log")
    if driver == "telegram":
        return _send_telegram_api(to_address, body, cfg)
    return _fail(f"unknown telegram driver: {driver}")


def _send_telegram_api(to_address: str, body: str, cfg: Optional[dict]) -> dict:  # pragma: no cover - network path
    token = _cfg_get(cfg, "bot_token", "TELEGRAM_BOT_TOKEN")
    if not token:
        return _fail("telegram not configured (need TELEGRAM_BOT_TOKEN)")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": to_address, "text": body}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as resp:
            payload = json.loads(resp.read().decode())
        result = payload.get("result") or {}
        return _ok(external_id=str(result.get("message_id") or ""))
    except Exception as e:
        return _fail(f"telegram send failed: {e}")


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
    # Prefer FCM HTTP v1 via firebase-admin when a service-account credential is
    # configured (FCM_SERVER_KEY is the legacy/deprecated API). Fall back to the
    # legacy urllib path, then _fail if neither is configured.
    creds_file = _cfg_get(cfg, "credentials_file", "FCM_CREDENTIALS_FILE") \
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_file:
        return _send_fcm_v1(subscription, title, body, creds_file)

    server_key = _cfg_get(cfg, "server_key", "FCM_SERVER_KEY")
    if not server_key:
        return _fail("fcm not configured (need FCM_CREDENTIALS_FILE or FCM_SERVER_KEY)")
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
        return _fail(f"legacy fcm send failed: {e}")


# Cache the initialized firebase-admin app so we don't re-init on every send.
_fcm_app = None


def _send_fcm_v1(subscription: dict, title: str, body: str, creds_file: str) -> dict:  # pragma: no cover
    """FCM HTTP v1 via firebase-admin + a service-account JSON credential.

    Imports firebase-admin lazily so the module never crashes when the optional
    dependency is absent — we degrade to a ``failed`` result like every other
    driver.
    """
    global _fcm_app
    try:
        import firebase_admin  # optional dependency
        from firebase_admin import credentials, messaging as fcm_messaging
    except Exception:
        return _fail("firebase-admin not installed")
    try:
        if _fcm_app is None:
            cred = credentials.Certificate(creds_file)
            _fcm_app = firebase_admin.initialize_app(cred)
        message = fcm_messaging.Message(
            token=subscription["endpoint"],
            notification=fcm_messaging.Notification(title=title, body=body),
        )
        message_id = fcm_messaging.send(message, app=_fcm_app)
        return _ok(external_id=str(message_id or ""))
    except Exception as e:
        return _fail(f"fcm v1 send failed: {e}")
