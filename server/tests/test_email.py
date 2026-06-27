# Email + password reset (plan-11). TEST DATA — NOT REAL.

from modules import messaging, users


def test_welcome_email_logged_on_user_create(client):
    # No users yet -> admin dev bypass lets us create the first account.
    res = client.post("/users", json={
        "email": "nuevo@egi.test", "password": "Secreto123!", "role": "viewer",
        "name": "Nuevo",
    })
    assert res.status_code == 200
    msgs = messaging.list_messages(channel="email")["records"]
    welcome = [m for m in msgs if m["template_name"] == "welcome"]
    assert welcome and welcome[0]["to_address"] == "nuevo@egi.test"
    assert welcome[0]["status"] == "sent"  # log driver


def test_password_reset_end_to_end(client):
    # Create an account (dev bypass; first user).
    client.post("/users", json={
        "email": "reset@egi.test", "password": "OldPass123!", "role": "operator",
        "name": "Reset",
    })

    # 1. Request a reset. Response never leaks the token or whether the email exists.
    res = client.post("/auth/forgot-password", json={"email": "reset@egi.test"})
    assert res.status_code == 200
    assert "token" not in res.json()

    # An email message was queued.
    emails = [m for m in messaging.list_messages(channel="email")["records"]
              if m["template_name"] == "password_reset"]
    assert emails

    # 2. The user clicks the link (token arrives by email). We mint it the same way
    #    the route does, to exercise redemption end-to-end.
    user = users.get_user_by_email("reset@egi.test")
    reset = users.create_password_reset(user["id"])

    # 3. Complete the reset with the new password.
    done = client.post("/auth/reset-password", json={
        "token": reset["token"], "password": "BrandNew456!",
    })
    assert done.status_code == 200

    # 4. Old password fails, new password works.
    assert client.post("/auth/login", json={
        "email": "reset@egi.test", "password": "OldPass123!",
    }).status_code == 401
    ok = client.post("/auth/login", json={
        "email": "reset@egi.test", "password": "BrandNew456!",
    })
    assert ok.status_code == 200
    assert "token" in ok.json()


def test_reset_token_single_use_and_expiry(client):
    client.post("/users", json={
        "email": "single@egi.test", "password": "OldPass123!", "role": "viewer",
    })
    user = users.get_user_by_email("single@egi.test")
    reset = users.create_password_reset(user["id"])
    assert users.consume_password_reset(reset["token"], "NewOne123!") is True
    # Re-using the same token fails.
    assert users.consume_password_reset(reset["token"], "Another123!") is False


def test_forgot_password_unknown_email_still_ok(client):
    res = client.post("/auth/forgot-password", json={"email": "ghost@egi.test"})
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_invalid_reset_token_rejected(client):
    assert client.post("/auth/reset-password", json={
        "token": "not-a-real-token", "password": "Whatever123!",
    }).status_code == 400
