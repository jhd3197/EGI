# User accounts + RBAC tests (plan-08). TEST DATA — NOT REAL.
#
# Covers the modules/users.py data layer, the auth.py RBAC dependencies, and
# the HTTP routes under /auth and /users. All emails/names here are obviously
# fake (example.test) per the test-data policy.

import auth
from modules import users


# ── helpers ─────────────────────────────────────────────────────────────────

def _seed_pending(client, rec_id="egi-imp-users"):
    """Insert an unreviewed pfif_import record (copied from test_auth.py)."""
    client.post("/sync", json={"records": [{
        "id": rec_id, "name": "Registro de prueba", "status": "missing",
        "source": "pfif_import", "reviewed": 0,
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    return rec_id


def _login(client, email, password):
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ── 1. Password hashing ──────────────────────────────────────────────────────

def test_hash_password_differs_from_plaintext_and_verifies():
    pw = "Sup3r-Secret-TEST"
    h = users.hash_password(pw)
    assert h != pw
    assert users.verify_password(pw, h) is True
    assert users.verify_password("wrong-password", h) is False


def test_hash_password_uses_salt():
    pw = "another-TEST-pw"
    assert users.hash_password(pw) != users.hash_password(pw)


def test_verify_password_never_raises_on_garbage():
    assert users.verify_password("x", "not-a-real-hash") is False


# ── 2. Tokens ────────────────────────────────────────────────────────────────

def test_token_create_resolve_and_revoke(temp_db):
    user = users.create_user("t-tok@example.test", "pw-tok-123", role="operator")
    tok = users.create_token(user["id"], name="cli")
    assert tok["token"]
    assert tok["token_hash"] == users.hash_token(tok["token"])

    resolved = users.get_user_for_token(tok["token"])
    assert resolved is not None
    assert resolved["id"] == user["id"]

    assert users.revoke_token(tok["token_hash"]) is True
    assert users.get_user_for_token(tok["token"]) is None


def test_get_user_for_token_none_and_garbage(temp_db):
    assert users.get_user_for_token(None) is None
    assert users.get_user_for_token("") is None
    assert users.get_user_for_token("totally-bogus-token") is None


# ── 3. Role hierarchy ────────────────────────────────────────────────────────

def test_role_satisfies_hierarchy():
    assert users.role_satisfies("admin", "viewer") is True
    assert users.role_satisfies("admin", "admin") is True
    assert users.role_satisfies("operator", "operator") is True
    assert users.role_satisfies("commander", "operator") is True
    assert users.role_satisfies("viewer", "operator") is False
    assert users.role_satisfies("operator", "admin") is False
    assert users.role_satisfies(None, "viewer") is False
    assert users.role_satisfies("bogus", "viewer") is False


# ── 4. create_user validation + normalization ────────────────────────────────

def test_create_user_duplicate_email_raises(temp_db):
    users.create_user("dup@example.test", "pw-12345")
    try:
        users.create_user("dup@example.test", "pw-67890")
        assert False, "expected ValueError on duplicate email"
    except ValueError:
        pass


def test_create_user_bad_role_raises(temp_db):
    try:
        users.create_user("badrole@example.test", "pw-12345", role="superuser")
        assert False, "expected ValueError on bad role"
    except ValueError:
        pass


def test_create_user_missing_fields_raise(temp_db):
    try:
        users.create_user("", "pw")
        assert False, "expected ValueError on empty email"
    except ValueError:
        pass
    try:
        users.create_user("noPw@example.test", "")
        assert False, "expected ValueError on empty password"
    except ValueError:
        pass


def test_create_user_normalizes_email(temp_db):
    users.create_user("  MixedCase@Example.TEST  ", "pw-norm-123")
    assert users.get_user_by_email("mixedcase@example.test") is not None
    # authenticate with a different case works too
    assert users.authenticate("MIXEDCASE@EXAMPLE.TEST", "pw-norm-123") is not None


# ── 5. authenticate ──────────────────────────────────────────────────────────

def test_authenticate_correct_wrong_and_inactive(temp_db):
    user = users.create_user("auth@example.test", "right-pw-123", role="viewer")
    assert users.authenticate("auth@example.test", "right-pw-123") is not None
    assert users.authenticate("auth@example.test", "wrong-pw") is None
    assert users.authenticate("missing@example.test", "whatever") is None

    users.update_user(user["id"], active=0)
    assert users.authenticate("auth@example.test", "right-pw-123") is None


# ── 6. set_password revokes tokens ───────────────────────────────────────────

def test_set_password_revokes_existing_tokens(temp_db):
    user = users.create_user("setpw@example.test", "old-pw-123", role="operator")
    tok = users.create_token(user["id"])
    assert users.get_user_for_token(tok["token"]) is not None

    assert users.set_password(user["id"], "new-pw-456") is True
    # Old token no longer resolves; new password authenticates.
    assert users.get_user_for_token(tok["token"]) is None
    assert users.authenticate("setpw@example.test", "new-pw-456") is not None


# ── 7. HTTP login / logout / me ──────────────────────────────────────────────

def test_http_login_logout_me_flow(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    users.create_user("t-me@example.test", "pw-me-123", role="operator", name="Mee")

    token = _login(client, "t-me@example.test", "pw-me-123")

    me = client.get("/auth/me", headers=_bearer(token))
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == "t-me@example.test"
    assert "password_hash" not in body["user"]

    logout = client.post("/auth/logout", headers=_bearer(token))
    assert logout.status_code == 200
    assert logout.json()["revoked"] is True

    # Token revoked -> subsequent /auth/me is 401.
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_http_login_bad_credentials(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    users.create_user("t-bad@example.test", "correct-pw-123", role="viewer")
    res = client.post("/auth/login",
                      json={"email": "t-bad@example.test", "password": "nope"})
    assert res.status_code == 401


def test_http_me_requires_token(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    assert client.get("/auth/me").status_code == 401


def test_http_login_never_leaks_password_hash(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    users.create_user("t-leak@example.test", "pw-leak-123", role="commander")
    res = client.post("/auth/login",
                      json={"email": "t-leak@example.test", "password": "pw-leak-123"})
    assert res.status_code == 200
    assert "password_hash" not in res.json()["user"]
    assert "password_hash" not in res.text


# ── 8. RBAC gating on a real protected endpoint ──────────────────────────────

def test_rbac_viewer_forbidden_operator_allowed(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    users.create_user("t-viewer@example.test", "pw-view-123", role="viewer")
    users.create_user("t-op@example.test", "pw-op-123", role="operator")

    rec_id = _seed_pending(client)
    viewer_tok = _login(client, "t-viewer@example.test", "pw-view-123")
    op_tok = _login(client, "t-op@example.test", "pw-op-123")

    forbidden = client.post(f"/moderation/{rec_id}/approve", headers=_bearer(viewer_tok))
    assert forbidden.status_code == 403

    allowed = client.post(f"/moderation/{rec_id}/approve", headers=_bearer(op_tok))
    assert allowed.status_code == 200


# ── 9. Admin user CRUD over HTTP ─────────────────────────────────────────────

def test_admin_user_crud(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    users.create_user("t-admin@example.test", "pw-admin-123", role="admin")
    admin_tok = _login(client, "t-admin@example.test", "pw-admin-123")
    h = _bearer(admin_tok)

    # Create
    created = client.post("/users", headers=h, json={
        "email": "t-new@example.test", "password": "pw-new-123",
        "role": "operator", "name": "Newbie",
    })
    assert created.status_code == 200, created.text
    new_id = created.json()["user"]["id"]
    assert "password_hash" not in created.json()["user"]

    # List
    listed = client.get("/users", headers=h)
    assert listed.status_code == 200
    emails = [u["email"] for u in listed.json()["users"]]
    assert "t-new@example.test" in emails
    assert all("password_hash" not in u for u in listed.json()["users"])

    # Patch
    patched = client.patch(f"/users/{new_id}", headers=h, json={"role": "commander"})
    assert patched.status_code == 200
    assert patched.json()["user"]["role"] == "commander"

    # Delete
    deleted = client.delete(f"/users/{new_id}", headers=h)
    assert deleted.status_code == 200
    assert client.delete(f"/users/{new_id}", headers=h).status_code == 404


def test_users_endpoint_forbidden_for_operator(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    users.create_user("t-op2@example.test", "pw-op2-123", role="operator")
    op_tok = _login(client, "t-op2@example.test", "pw-op2-123")
    assert client.get("/users", headers=_bearer(op_tok)).status_code == 403


def test_create_user_duplicate_email_http_400(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    users.create_user("t-admin2@example.test", "pw-admin-123", role="admin")
    users.create_user("t-exists@example.test", "pw-exists-123", role="viewer")
    admin_tok = _login(client, "t-admin2@example.test", "pw-admin-123")
    res = client.post("/users", headers=_bearer(admin_tok), json={
        "email": "t-exists@example.test", "password": "pw-x-123", "role": "viewer",
    })
    assert res.status_code == 400


def test_patch_missing_user_http_404(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    users.create_user("t-admin3@example.test", "pw-admin-123", role="admin")
    admin_tok = _login(client, "t-admin3@example.test", "pw-admin-123")
    res = client.patch("/users/usr-doesnotexist", headers=_bearer(admin_tok),
                       json={"name": "Ghost"})
    assert res.status_code == 404


def test_reset_password_returns_temp_and_revokes_token(client, monkeypatch):
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    users.create_user("t-admin4@example.test", "pw-admin-123", role="admin")
    target = users.create_user("t-target@example.test", "pw-target-123", role="operator")
    admin_tok = _login(client, "t-admin4@example.test", "pw-admin-123")

    # Target logs in -> gets a token that should later be revoked.
    target_tok = _login(client, "t-target@example.test", "pw-target-123")
    assert client.get("/auth/me", headers=_bearer(target_tok)).status_code == 200

    res = client.post(f"/users/{target['id']}/reset-password",
                      headers=_bearer(admin_tok), json={})
    assert res.status_code == 200
    temp_pw = res.json()["temporary_password"]
    assert temp_pw

    # Old token stops working; the temp password authenticates.
    assert client.get("/auth/me", headers=_bearer(target_tok)).status_code == 401
    assert users.authenticate("t-target@example.test", temp_pw) is not None


# ── 10. Static-token deprecation ─────────────────────────────────────────────

def test_static_token_operator_ok_but_admin_forbidden(client, monkeypatch):
    # No users exist; only a static OPERATOR_TOKENS env token configured.
    monkeypatch.setenv("OPERATOR_TOKENS", "static-op-token-xyz")
    rec_id = _seed_pending(client)

    # Operator-level endpoint accepts the static token.
    ok = client.post(f"/moderation/{rec_id}/approve",
                     headers=_bearer("static-op-token-xyz"))
    assert ok.status_code == 200

    # Admin-only /users rejects the static (operator-level) token with 403.
    forbidden = client.get("/users", headers=_bearer("static-op-token-xyz"))
    assert forbidden.status_code == 403
