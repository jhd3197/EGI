# Shared auth/RBAC test helpers for the EGI server suite.
# TEST DATA — NOT REAL. All emails/tokens here are obviously fake.

from modules import users


def bearer(token):
    """Build an Authorization header dict for a bearer token."""
    return {"Authorization": f"Bearer {token}"}


def make_user_with_headers(email, role="operator"):
    """Create a user + token, returning ``(user, auth-headers)``.

    Once any user exists the dev auth bypass is off, so every request must
    then carry a token.
    """
    u = users.create_user(email, f"pw-{role}-12345", role=role)
    tok = users.create_token(u["id"])["token"]
    return u, bearer(tok)


def login(client, email, password):
    """POST /auth/login and return the issued token."""
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def seed_pending(client, rec_id="egi-imp-pending"):
    """Insert an unreviewed pfif_import record (a moderation-queue fixture)."""
    client.post("/sync", json={"records": [{
        "id": rec_id, "name": "Registro de prueba", "status": "missing",
        "source": "pfif_import", "reviewed": 0,
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    return rec_id
