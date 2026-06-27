# Server-to-server federation (plan-12 §4). The peer is simulated by
# monkeypatching federation._http_get / _http_post — no real network.
# TEST DATA — NOT REAL.

import json

import pytest

from modules import federation


def _person(**overrides):
    base = {
        "id": "egi-test-0001",
        "name": "Juan Pérez de prueba",
        "status": "missing",
        "disaster_id": "d-test",
        "location": "Refugio de prueba",
        "cedula": "V-00000000",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


# ── CRUD + key pinning ────────────────────────────────────────────────────────

def test_add_list_get_remove_peer(temp_db):
    peer = federation.add_peer(name="Hub Norte", base_url="https://norte.example/")
    # base_url is normalized (trailing slash stripped).
    assert peer["base_url"] == "https://norte.example"
    assert peer["id"].startswith("peer-")

    rows = federation.list_peers()["records"]
    assert [r["id"] for r in rows] == [peer["id"]]

    got = federation.get_peer(peer["id"])
    assert got["name"] == "Hub Norte"

    federation.remove_peer(peer["id"])
    assert federation.list_peers()["records"] == []


def test_get_unknown_peer_404(temp_db):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        federation.get_peer("peer-nope")
    assert exc.value.status_code == 404


def test_key_pinning_rejects_changed_key(temp_db):
    from fastapi import HTTPException

    peer = federation.add_peer(
        name="Hub Sur", base_url="https://sur.example", public_key="KEY-AAA"
    )
    # Same key is fine.
    federation.update_peer(peer["id"], public_key="KEY-AAA")
    # A different key is rejected (trust-on-first-use pin).
    with pytest.raises(HTTPException) as exc:
        federation.update_peer(peer["id"], public_key="KEY-BBB")
    assert exc.value.status_code == 409
    assert "pinned" in exc.value.detail


def test_add_peer_same_url_rejects_changed_key(temp_db):
    from fastapi import HTTPException

    federation.add_peer(
        name="Hub Este", base_url="https://este.example", public_key="KEY-AAA"
    )
    with pytest.raises(HTTPException) as exc:
        federation.add_peer(
            name="Hub Este", base_url="https://este.example", public_key="KEY-BBB"
        )
    assert exc.value.status_code == 409


# ── Pull ──────────────────────────────────────────────────────────────────────

def test_pull_applies_records_and_dedupes(temp_db, monkeypatch):
    peer = federation.add_peer(name="Hub", base_url="https://hub.example")
    payload = json.dumps({"records": [_person()], "reports": []})

    def fake_get(url, headers, timeout):
        return 200, payload

    monkeypatch.setattr(federation, "_http_get", fake_get)

    result = federation.pull_from_peer(peer["id"])
    assert result["pulled"] == 1
    assert result["saved"] == 1
    assert result["skipped"] == 0

    # Record landed in the local DB via sync_upload.
    import db

    with db.get_db() as conn:
        row = conn.execute(
            "SELECT name FROM persons WHERE id = ?", ("egi-test-0001",)
        ).fetchone()
    assert row["name"] == "Juan Pérez de prueba"

    # last_sync_at is now set.
    assert federation.get_peer(peer["id"])["last_sync_at"]

    # A SECOND pull of the same payload adds NO duplicate rows: the upsert is
    # keyed on the client id, so re-pulling the same record updates the existing
    # row in place rather than inserting a copy.
    result2 = federation.pull_from_peer(peer["id"])
    assert result2["pulled"] == 1
    assert result2["saved"] + result2["skipped"] == 1

    with db.get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM persons WHERE id = ?", ("egi-test-0001",)
        ).fetchone()[0]
    assert count == 1

    # An older re-pull IS skipped by last-write-wins (stale relay guard).
    def fake_get_stale(url, headers, timeout):
        return 200, json.dumps(
            {"records": [_person(updatedAt="2025-01-01T00:00:00Z")], "reports": []}
        )

    monkeypatch.setattr(federation, "_http_get", fake_get_stale)
    result3 = federation.pull_from_peer(peer["id"])
    assert result3["saved"] == 0
    assert result3["skipped"] == 1


def test_pull_network_error_returns_error(temp_db, monkeypatch):
    peer = federation.add_peer(name="Hub", base_url="https://hub.example")

    def boom(url, headers, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(federation, "_http_get", boom)
    result = federation.pull_from_peer(peer["id"])
    assert "error" in result


def test_pull_unknown_peer_raises(temp_db):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        federation.pull_from_peer("peer-nope")
    assert exc.value.status_code == 404


# ── Push ──────────────────────────────────────────────────────────────────────

def test_push_posts_local_records_and_updates_last_push(temp_db, monkeypatch):
    # Seed a local record via the real sync path.
    from models import PersonRecord, SyncPayload
    from modules.sync import sync_upload

    sync_upload(SyncPayload(records=[PersonRecord(**_person())]))

    peer = federation.add_peer(name="Hub", base_url="https://hub.example")

    captured = {}

    def fake_post(url, body_bytes, headers, timeout):
        captured["url"] = url
        captured["body"] = body_bytes.decode("utf-8")
        captured["headers"] = headers
        return 200, json.dumps({"saved": 1, "skipped": 0})

    monkeypatch.setattr(federation, "_http_post", fake_post)

    result = federation.push_to_peer(peer["id"])
    assert result["pushed"] == 1
    assert captured["url"] == "https://hub.example/sync"
    # The body carries the seeded record in camelCase /sync shape.
    body = json.loads(captured["body"])
    assert body["records"][0]["id"] == "egi-test-0001"
    assert "updatedAt" in body["records"][0]

    # last_push_at is now set.
    assert federation.get_peer(peer["id"])["last_push_at"]


def test_push_with_token_sends_authorization_header(temp_db, monkeypatch):
    from models import PersonRecord, SyncPayload
    from modules.sync import sync_upload

    sync_upload(SyncPayload(records=[PersonRecord(**_person())]))
    peer = federation.add_peer(
        name="Hub", base_url="https://hub.example", token="secret-token"
    )

    captured = {}

    def fake_post(url, body_bytes, headers, timeout):
        captured["headers"] = headers
        return 200, "{}"

    monkeypatch.setattr(federation, "_http_post", fake_post)
    federation.push_to_peer(peer["id"])
    assert captured["headers"].get("Authorization") == "Bearer secret-token"


def test_push_network_error_returns_error(temp_db, monkeypatch):
    peer = federation.add_peer(name="Hub", base_url="https://hub.example")

    def boom(url, body_bytes, headers, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(federation, "_http_post", boom)
    result = federation.push_to_peer(peer["id"])
    assert "error" in result
    # last_push_at stays unset since the push failed.
    assert not federation.get_peer(peer["id"])["last_push_at"]


# ── Sync (pull + push) ────────────────────────────────────────────────────────

def test_sync_peer_runs_pull_then_push(temp_db, monkeypatch):
    peer = federation.add_peer(name="Hub", base_url="https://hub.example")
    monkeypatch.setattr(
        federation, "_http_get",
        lambda url, headers, timeout: (200, json.dumps({"records": [_person()], "reports": []})),
    )
    monkeypatch.setattr(
        federation, "_http_post",
        lambda url, body_bytes, headers, timeout: (200, "{}"),
    )
    result = federation.sync_peer(peer["id"])
    assert result["pull"]["saved"] == 1
    assert "pushed" in result["push"]
