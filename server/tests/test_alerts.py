# Operation alerts: multi-channel broadcast + delivery tracking (plan-11).
# TEST DATA — NOT REAL.


def _make_operation(client, name="Deslave Norte"):
    res = client.post("/operations", json={"name": name, "region": "Norte"})
    return res.json()["id"]


def _add_person(client, op_id, contact):
    client.post("/sync", json={"records": [{
        "id": f"egi-test-{contact}", "name": "Contacto", "status": "missing",
        "contact": contact, "disaster_id": op_id,
    }]})


def test_alert_broadcasts_to_all_channels(client):
    op_id = _make_operation(client)
    _add_person(client, op_id, "+584140001234")        # sms recipient
    _add_person(client, op_id, "familia@egi.test")     # email recipient
    client.post("/push/subscribe", json={"endpoint": "ep-a", "topic": op_id})

    res = client.post(f"/operations/{op_id}/alerts", json={
        "title": "Sector A despejado",
        "body": "Repórtense en el punto de encuentro.",
    })
    assert res.status_code == 200
    out = res.json()
    assert out["channels"]["sms"]["recipients"] == 1
    assert out["channels"]["email"]["recipients"] == 1
    assert out["channels"]["push"]["recipients"] == 1
    assert out["sent"] == 3                            # log driver delivers all

    # Every message carries the shared alert_id (delivery tracking).
    msgs = client.get(f"/alerts/{out['alert_id']}/messages").json()["records"]
    assert len(msgs) == 3
    assert {m["channel"] for m in msgs} == {"sms", "email", "push"}


def test_alert_channel_subset(client):
    op_id = _make_operation(client, name="Op SMS")
    _add_person(client, op_id, "+584149998888")
    res = client.post(f"/operations/{op_id}/alerts", json={
        "title": "Solo SMS", "body": "test", "channels": ["sms"],
    })
    out = res.json()
    assert set(out["channels"].keys()) == {"sms"}
    assert out["channels"]["sms"]["recipients"] == 1


def test_alert_unknown_operation_404(client):
    assert client.post("/operations/nope/alerts", json={"title": "x", "body": "y"}).status_code == 404


def test_list_alerts_summary(client):
    op_id = _make_operation(client, name="Op List")
    _add_person(client, op_id, "+584141112222")
    client.post(f"/operations/{op_id}/alerts", json={"title": "A1", "body": "uno"})
    client.post(f"/operations/{op_id}/alerts", json={"title": "A2", "body": "dos"})
    alerts = client.get(f"/operations/{op_id}/alerts").json()["records"]
    assert len(alerts) == 2
    assert all(a["alert_id"] for a in alerts)
    assert all("sms" in a["channels"] for a in alerts)
