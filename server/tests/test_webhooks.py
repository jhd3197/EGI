# Outbound webhooks with retry (plan-12 §3).
# TEST DATA — NOT REAL. _http_post is monkeypatched so no real network is hit.

import pytest

from modules import webhooks


@pytest.fixture()
def captured(monkeypatch):
    """Monkeypatch webhooks._http_post to capture calls and return 200 by default."""
    calls = []

    def fake_post(url, body_bytes, headers, timeout):
        calls.append({"url": url, "body": body_bytes, "headers": dict(headers)})
        return 200, "ok"

    monkeypatch.setattr(webhooks, "_http_post", fake_post)
    return calls


# ── Subscription CRUD ─────────────────────────────────────────────────────────

def test_subscription_crud(client):
    created = client.post("/webhooks", json={
        "url": "https://example.test/hook", "events": "person.created",
    }).json()
    wid = created["id"]
    assert wid.startswith("whk-")
    assert created["active"] == 1

    listed = client.get("/webhooks").json()["records"]
    assert wid in [w["id"] for w in listed]

    got = client.get(f"/webhooks/{wid}").json()
    assert got["url"] == "https://example.test/hook"

    deleted = client.delete(f"/webhooks/{wid}")
    assert deleted.status_code == 200
    assert client.get(f"/webhooks/{wid}").status_code == 404


def test_event_validation_rejects_bad_event(client):
    res = client.post("/webhooks", json={
        "url": "https://example.test/hook", "events": "person.exploded",
    })
    assert res.status_code == 400


def test_wildcard_events_accepted(client):
    res = client.post("/webhooks", json={"url": "https://x.test/h", "events": "*"})
    assert res.status_code == 200


# ── Emission + delivery ───────────────────────────────────────────────────────

def test_emit_delivers_to_matching_and_wildcard(client, captured):
    client.post("/webhooks", json={"url": "https://a.test/h", "events": "person.created"})
    client.post("/webhooks", json={"url": "https://b.test/h", "events": "*"})
    client.post("/webhooks", json={"url": "https://c.test/h", "events": "operation.closed"})

    webhooks.emit("person.created", {"id": "p1", "name": "Ana"})

    urls = {c["url"] for c in captured}
    assert "https://a.test/h" in urls   # exact match
    assert "https://b.test/h" in urls   # wildcard
    assert "https://c.test/h" not in urls  # non-matching event

    # A success row was recorded.
    rows = webhooks.list_deliveries()["records"]
    assert any(r["success"] == 1 and r["event_type"] == "person.created" for r in rows)


def test_hmac_signature_present_and_correct(client, captured):
    import hashlib
    import hmac
    import json

    secret = "s3cr3t"
    client.post("/webhooks", json={
        "url": "https://signed.test/h", "events": "person.created", "secret": secret,
    })
    payload = {"id": "p1", "name": "Ana"}
    webhooks.emit("person.created", payload)

    call = next(c for c in captured if c["url"] == "https://signed.test/h")
    assert "X-EGI-Signature" in call["headers"]
    expected = "sha256=" + hmac.new(
        secret.encode(), call["body"], hashlib.sha256
    ).hexdigest()
    assert call["headers"]["X-EGI-Signature"] == expected
    # And the body is the JSON payload we emitted.
    assert json.loads(call["body"].decode()) == payload


def test_no_signature_without_secret(client, captured):
    client.post("/webhooks", json={"url": "https://nosig.test/h", "events": "*"})
    webhooks.emit("person.created", {"id": "p1"})
    call = next(c for c in captured if c["url"] == "https://nosig.test/h")
    assert "X-EGI-Signature" not in call["headers"]


# ── Failure + retry ───────────────────────────────────────────────────────────

def test_failure_records_retry_then_succeeds(client, monkeypatch):
    sub = client.post("/webhooks", json={
        "url": "https://flaky.test/h", "events": "person.created",
    }).json()

    # First attempt: transport error.
    def raising(url, body_bytes, headers, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(webhooks, "_http_post", raising)
    webhooks.emit("person.created", {"id": "p1"})

    rows = webhooks.list_deliveries(subscription_id=sub["id"])["records"]
    assert len(rows) == 1
    assert rows[0]["success"] == 0
    assert rows[0]["next_retry_at"] is not None

    # Make the retry due by backdating next_retry_at, then retry with success.
    import db
    with db.get_db() as conn:
        conn.execute(
            "UPDATE webhook_deliveries SET next_retry_at = ? WHERE subscription_id = ?",
            ("1970-01-01T00:00:00+00:00", sub["id"]),
        )
        conn.commit()

    monkeypatch.setattr(webhooks, "_http_post", lambda *a, **k: (200, "ok"))
    result = webhooks.retry_pending()
    assert result["retried"] == 1
    assert result["succeeded"] == 1

    rows = webhooks.list_deliveries(subscription_id=sub["id"])["records"]
    assert any(r["success"] == 1 and r["attempt"] == 2 for r in rows)


def test_non_2xx_records_failure(client, monkeypatch):
    sub = client.post("/webhooks", json={"url": "https://err.test/h", "events": "*"}).json()
    monkeypatch.setattr(webhooks, "_http_post", lambda *a, **k: (500, "boom"))
    webhooks.emit("person.created", {"id": "p1"})
    rows = webhooks.list_deliveries(subscription_id=sub["id"])["records"]
    assert rows[0]["success"] == 0
    assert rows[0]["response_status"] == 500
    assert rows[0]["next_retry_at"] is not None


def test_emit_never_raises_even_if_post_raises(client, monkeypatch):
    client.post("/webhooks", json={"url": "https://boom.test/h", "events": "*"})

    def raising(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(webhooks, "_http_post", raising)
    # Must not propagate.
    webhooks.emit("person.created", {"id": "p1"})


# ── /webhooks/{id}/test endpoint ──────────────────────────────────────────────

def test_test_endpoint_delivers(client, captured):
    sub = client.post("/webhooks", json={"url": "https://t.test/h", "events": "*"}).json()
    res = client.post(f"/webhooks/{sub['id']}/test")
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert any(c["url"] == "https://t.test/h" for c in captured)


# ── Emission hook from sync ───────────────────────────────────────────────────

def test_sync_new_person_triggers_person_created(client, captured):
    sub = client.post("/webhooks", json={
        "url": "https://sync.test/h", "events": "person.created",
    }).json()
    client.post("/sync", json={"records": [{
        "id": "egi-test-wh-1",
        "name": "Persona de prueba",
        "status": "missing",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    assert any(c["url"] == "https://sync.test/h" for c in captured)
    rows = webhooks.list_deliveries(subscription_id=sub["id"])["records"]
    assert any(r["event_type"] == "person.created" and r["success"] == 1 for r in rows)
