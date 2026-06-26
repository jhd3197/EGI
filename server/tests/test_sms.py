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
