# Push subscriptions (plan-11). TEST DATA — NOT REAL.

from modules import push


def test_vapid_public_key_endpoint(client):
    res = client.get("/push/vapid-public-key")
    assert res.status_code == 200
    # None unless VAPID_PUBLIC_KEY is configured (default dev: not configured).
    assert "key" in res.json()


def test_subscribe_and_unsubscribe(client):
    sub = {
        "kind": "webpush",
        "endpoint": "https://push.example.com/abc123",
        "p256dh": "key", "auth": "auth",
        "topic": "op-1",
    }
    res = client.post("/push/subscribe", json=sub)
    assert res.status_code == 200
    body = res.json()
    assert body["created"] is True
    assert body["topic"] == "op-1"

    # Re-subscribing the same endpoint updates, not duplicates.
    res2 = client.post("/push/subscribe", json={**sub, "topic": "op-2"})
    assert res2.json()["created"] is False
    assert res2.json()["topic"] == "op-2"

    # Unsubscribe removes it.
    out = client.post("/push/unsubscribe", json={"endpoint": sub["endpoint"]})
    assert out.json()["removed"] == 1


def test_subscribe_rejects_bad_kind(client):
    res = client.post("/push/subscribe", json={"kind": "carrier-pigeon", "endpoint": "x"})
    assert res.status_code == 400


def test_send_to_operation_fans_out_to_topic_and_global(client):
    # One device subscribed to op-9, one global (no topic).
    client.post("/push/subscribe", json={"endpoint": "ep-op9", "topic": "op-9"})
    client.post("/push/subscribe", json={"endpoint": "ep-global", "topic": None})
    # A device on another operation should NOT receive it.
    client.post("/push/subscribe", json={"endpoint": "ep-other", "topic": "op-3"})

    result = push.send_to_operation("op-9", "Título", "Cuerpo")
    assert result["recipients"] == 2          # op-9 + global, not op-3
    assert result["sent"] == 2                 # log driver

    # Each push left an outbound message keyed to the operation.
    msgs = client.get("/messages", params={"operation_id": "op-9", "channel": "push"}).json()
    assert len(msgs["records"]) == 2
