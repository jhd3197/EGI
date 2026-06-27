# WhatsApp webhook adapter (plan-14 §4). TEST DATA — NOT REAL.

FROM = "whatsapp:+584140001000"


def _post(client, body=None, **extra):
    payload = {"From": FROM}
    if body is not None:
        payload["Body"] = body
    payload.update(extra)
    return client.post("/webhooks/whatsapp", data=payload)


def test_twilio_report_conversation_creates_draft(client):
    _post(client, "reportar")
    _post(client, "Pedro Pérez")
    _post(client, "V-12345678")
    _post(client, "Refugio Norte")
    res = _post(client, "desaparecido")
    draft = res.json()["draft"]
    assert draft["name"] == "Pedro Pérez"
    assert draft["source"] == "whatsapp"
    assert draft["reviewed"] == 0

    pending = [r["id"] for r in client.get("/moderation/pending").json()["records"]]
    assert draft["id"] in pending


def test_messages_logged_both_directions(client):
    _post(client, "reportar")
    msgs = client.get("/messages", params={"channel": "whatsapp"}).json()["records"]
    dirs = {m["direction"] for m in msgs}
    assert "inbound" in dirs
    assert "outbound" in dirs


def test_meta_json_text_message_works(client):
    payload = {
        "entry": [{"changes": [{"value": {"messages": [
            {"from": "584140002000", "type": "text", "text": {"body": "reportar"}}
        ]}}]}]
    }
    res = client.post("/webhooks/whatsapp", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json().get("reply")


def test_delivery_status_payload_ignored(client):
    payload = {"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]}
    res = client.post("/webhooks/whatsapp", json=payload)
    body = res.json()
    assert body.get("ignored") is True or not body.get("draft")
