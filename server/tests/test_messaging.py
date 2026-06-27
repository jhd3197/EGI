# Communications-hub core: templates, providers, message log (plan-11).
# TEST DATA — NOT REAL.

from modules import templates


# ── Template rendering ───────────────────────────────────────────────────────

def test_template_renders_variables():
    out = templates.render("status_changed", {
        "person_name": "María", "status": "found", "operation_name": "Op1",
    }, "es")
    assert "María" in out["body"]
    assert "found" in out["body"]
    assert out["locale"] == "es"


def test_template_missing_variable_is_blank_not_error():
    # Omitting operation_name must not raise; it renders as empty.
    out = templates.render("status_changed", {"person_name": "Ana"}, "en")
    assert "Ana" in out["body"]


def test_template_locale_fallback_to_default():
    # Unsupported locale falls back to Spanish (DEFAULT_LOCALE).
    out = templates.render("report_received", {"person_name": "X"}, "fr")
    assert out["locale"] == "es"


def test_template_html_present_for_email_templates():
    out = templates.render("welcome", {"name": "Eva", "role": "viewer"}, "es")
    assert "html" in out and "Eva" in out["html"]


def test_unknown_template_raises():
    import pytest
    with pytest.raises(KeyError):
        templates.render("does_not_exist", {})


# ── Single send + message log ────────────────────────────────────────────────

def test_send_single_email_via_messages_endpoint(client):
    res = client.post("/messages", json={
        "channel": "email",
        "to_address": "someone@egi.test",
        "template_name": "welcome",
        "variables": {"name": "Pedro", "role": "operator"},
    })
    assert res.status_code == 200
    msg = res.json()
    assert msg["channel"] == "email"
    assert msg["status"] == "sent"
    assert msg["to_address"] == "someone@egi.test"


def test_send_rejects_unsupported_channel_for_messages(client):
    # Push is sent per-subscription via /alerts, not /messages.
    res = client.post("/messages", json={"channel": "push", "to_address": "x", "body": "y"})
    assert res.status_code == 400


def test_message_status_update_callback(client):
    sent = client.post("/messages", json={
        "channel": "sms", "to_address": "+584140000000", "body": "hola",
    }).json()
    res = client.post(f"/messages/{sent['id']}/status", json={"status": "delivered"})
    assert res.status_code == 200
    assert res.json()["status"] == "delivered"


def test_messages_list_filters(client):
    client.post("/messages", json={"channel": "sms", "to_address": "+1", "body": "a"})
    client.post("/messages", json={"channel": "email", "to_address": "e@e.test", "body": "b"})
    sms_only = client.get("/messages", params={"channel": "sms"}).json()["records"]
    assert sms_only and all(m["channel"] == "sms" for m in sms_only)


# ── Pluggable providers ──────────────────────────────────────────────────────

def test_provider_crud_and_default_switch(client):
    a = client.post("/message-providers", json={
        "channel": "sms", "name": "primary", "config": {"driver": "log"},
        "is_default": 1,
    }).json()
    b = client.post("/message-providers", json={
        "channel": "sms", "name": "backup", "config": {"driver": "twilio"},
        "is_default": 1,
    }).json()
    listed = client.get("/message-providers", params={"channel": "sms"}).json()["records"]
    defaults = [p for p in listed if p["is_default"]]
    # Setting a new default clears the previous one.
    assert len(defaults) == 1 and defaults[0]["id"] == b["id"]

    # Config round-trips as a parsed dict.
    assert b["config"]["driver"] == "twilio"

    client.delete(f"/message-providers/{a['id']}")
    remaining = client.get("/message-providers", params={"channel": "sms"}).json()["records"]
    assert a["id"] not in [p["id"] for p in remaining]


def test_provider_rejects_bad_channel(client):
    assert client.post("/message-providers", json={"channel": "carrier", "name": "x"}).status_code == 400
