# SMS check-in webhook. TEST DATA — NOT REAL.


def test_sms_checkin_creates_unreviewed_safe_record(client):
    res = client.post("/sms/webhook", json={
        "body": "EGI CHECKIN V-12345678, Juan Pérez, Refugio Norte",
        "sender": "+584140000000",
    })
    assert res.status_code == 200
    created = res.json()["created"]
    assert created["status"] == "safe"
    assert created["source"] == "sms"
    assert created["reviewed"] == 0
    assert created["cedula"] == "V-12345678"
    assert created["name"] == "Juan Pérez"
    assert created["location"] == "Refugio Norte"


def test_sms_checkin_hidden_until_approved(client):
    res = client.post("/sms/webhook", json={
        "body": "EGI CHECKIN V-22222222, Ana Gómez, Sur",
    })
    pid = res.json()["created"]["id"]
    # Untrusted (source=sms, reviewed=0): not in public search...
    ids = [r["id"] for r in client.get("/persons", params={"q": "Ana"}).json()["records"]]
    assert pid not in ids
    # ...but it IS in the moderation queue.
    pending = [r["id"] for r in client.get("/moderation/pending").json()["records"]]
    assert pid in pending
    # After approval it becomes visible.
    client.post(f"/moderation/{pid}/approve")
    ids = [r["id"] for r in client.get("/persons", params={"q": "Ana"}).json()["records"]]
    assert pid in ids


def test_sms_checkin_space_separated(client):
    res = client.post("/sms/webhook", json={
        "body": "EGI CHECKIN V-33333333 Carlos Refugio",
    })
    created = res.json()["created"]
    assert created["cedula"] == "V-33333333"
    assert created["name"] == "Carlos"
    assert created["location"] == "Refugio"


def test_sms_checkin_syncs_to_cloud(client):
    # Success criterion: an SMS check-in creates a record that GET /sync returns.
    client.post("/sms/webhook", json={"body": "EGI CHECKIN V-44444444, Eva, Este"})
    records = client.get("/sync", params={"since": "1970-01-01T00:00:00Z"}).json()["records"]
    assert any(r["source"] == "sms" and r["cedula"] == "V-44444444" for r in records)


def test_sms_rejects_non_checkin(client):
    assert client.post("/sms/webhook", json={"body": "hola"}).status_code == 400


def test_sms_rejects_missing_cedula(client):
    assert client.post("/sms/webhook", json={"body": "EGI CHECKIN"}).status_code == 400


# ── plan-11: outbound, two-way replies, broadcast ────────────────────────────

def _make_person(client, name="María", contact="+584140001111", status="missing"):
    rec = {
        "id": f"egi-test-{name}", "name": name, "status": status,
        "contact": contact, "disaster_id": "op-1",
    }
    client.post("/sync", json={"records": [rec]})
    return rec["id"]


def test_sms_notify_queues_outbound_message(client):
    pid = _make_person(client)
    res = client.post("/sms/notify", json={
        "person_id": pid, "template_name": "report_received",
    })
    assert res.status_code == 200
    msg = res.json()
    assert msg["channel"] == "sms"
    assert msg["direction"] == "outbound"
    assert msg["status"] == "sent"            # log driver
    assert "María" in msg["body"]
    assert msg["to_address"] == "+584140001111"


def test_sms_reply_attaches_report_to_person(client):
    pid = _make_person(client, name="Ana", contact="+584140002222")
    # We must have an open conversation: send an outbound first.
    client.post("/sms/notify", json={"person_id": pid, "template_name": "request_info"})
    # The family replies from the same number.
    res = client.post("/sms/webhook", json={
        "body": "La vi en el refugio sur, está bien",
        "sender": "+58 414 000 2222",  # same number, different formatting
    })
    assert res.status_code == 200
    body = res.json()
    assert body["matched"] is True
    assert body["person_id"] == pid
    # The reply is now a report (PFIF note) on the person.
    reports = client.get(f"/persons/{pid}/reports").json()["records"]
    assert any("refugio sur" in (r["note"] or "") for r in reports)
    assert any(r["source"] == "sms" for r in reports)


def test_sms_reply_without_conversation_rejected(client):
    # No prior outbound to this number -> not a checkin, no conversation -> 400.
    assert client.post("/sms/webhook", json={
        "body": "hola quien es", "sender": "+584149999999",
    }).status_code == 400


def test_sms_broadcast_to_operation_contacts(client):
    _make_person(client, name="P1", contact="+584140003333")
    _make_person(client, name="P2", contact="+584140004444")
    res = client.post("/sms/broadcast", json={
        "operation_id": "op-1",
        "body": "Sector A despejado. Repórtense.",
    })
    assert res.status_code == 200
    out = res.json()
    assert out["recipients"] >= 2
    assert out["sent"] == out["recipients"]
    # Each broadcast leaves an outbound message in the log.
    msgs = client.get("/messages", params={"operation_id": "op-1", "channel": "sms"}).json()
    assert len([m for m in msgs["records"] if m["direction"] == "outbound"]) >= 2


def test_sms_broadcast_explicit_list(client):
    res = client.post("/sms/broadcast", json={
        "to_addresses": ["+584140005555", "+584140006666"],
        "template_name": "alert",
        "variables": {"title": "Aviso", "body": "Prueba", "operation_name": "Op"},
    })
    assert res.json()["sent"] == 2
