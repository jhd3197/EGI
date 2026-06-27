# Operator auth + audit logging. TEST DATA — NOT REAL.
# When OPERATOR_TOKENS is set, protected endpoints require a valid bearer token;
# when unset, auth is disabled (dev) and actions still log an audit row.

import auth


def _seed_pending(client, rec_id="egi-imp-auth"):
    client.post("/sync", json={"records": [{
        "id": rec_id, "name": "Registro de prueba", "status": "missing",
        "source": "pfif_import", "reviewed": 0,
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    return rec_id


def test_disabled_when_no_tokens(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    rec_id = _seed_pending(client)
    # No Authorization header, but auth disabled -> allowed.
    assert client.post(f"/moderation/{rec_id}/approve").status_code == 200


def test_protected_requires_valid_token(client, monkeypatch):
    monkeypatch.setenv("OPERATOR_TOKENS", "s3cr3t-token-a,s3cr3t-token-b")
    rec_id = _seed_pending(client)

    # Missing header -> 401.
    assert client.post(f"/moderation/{rec_id}/approve").status_code == 401
    # Wrong token -> 401.
    bad = client.post(f"/moderation/{rec_id}/approve",
                      headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    # Valid token -> 200.
    ok = client.post(f"/moderation/{rec_id}/approve",
                     headers={"Authorization": "Bearer s3cr3t-token-a"})
    assert ok.status_code == 200


def test_operator_action_is_audited(client, monkeypatch):
    monkeypatch.setenv("OPERATOR_TOKENS", "tok-12345678")
    rec_id = _seed_pending(client)
    client.post(f"/moderation/{rec_id}/approve",
                headers={"Authorization": "Bearer tok-12345678"})

    res = client.get("/moderation/audit", headers={"Authorization": "Bearer tok-12345678"})
    assert res.status_code == 200
    actions = res.json()["actions"]
    approve_rows = [a for a in actions if a["action"] == "approve" and a["target_id"] == rec_id]
    assert approve_rows
    # The actor is a short non-secret principal, never the full token.
    assert approve_rows[0]["actor"].startswith("op:")
    assert "tok-12345678" not in approve_rows[0]["actor"]


def test_auth_failure_is_audited(client, monkeypatch):
    monkeypatch.setenv("OPERATOR_TOKENS", "good-token-xyz")
    rec_id = _seed_pending(client)
    client.post(f"/moderation/{rec_id}/approve", headers={"Authorization": "Bearer wrong"})
    res = client.get("/moderation/audit", headers={"Authorization": "Bearer good-token-xyz"})
    failures = [a for a in res.json()["actions"] if a["action"] == "auth_failure"]
    assert failures


def test_token_principal_never_leaks_token():
    assert auth.token_principal("supersecretvalue") == "op:supers…"
    assert "supersecretvalue" not in auth.token_principal("supersecretvalue")
