# Credential rotation: revoke_all_tokens (plan-15 Phase 6). TEST DATA — NOT REAL.

from modules import users


def _user(email, role="operator"):
    return users.create_user(email, "TESTpassw0rd!", role=role, name="TEST User")


def test_revoke_all_tokens_global(temp_db):
    u1 = _user("rot1@example.test")
    u2 = _user("rot2@example.test")
    users.create_token(u1["id"], name="t1")
    users.create_token(u1["id"], name="t2")
    users.create_token(u2["id"], name="t3")

    revoked = users.revoke_all_tokens()
    assert revoked == 3

    # Tokens are gone: a fresh token resolves, old count is zero.
    import db

    with db.get_db() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM user_tokens").fetchone()["n"]
    assert n == 0


def test_revoke_all_tokens_scoped_to_user(temp_db):
    u1 = _user("rot3@example.test")
    u2 = _user("rot4@example.test")
    users.create_token(u1["id"], name="a")
    users.create_token(u2["id"], name="b")

    revoked = users.revoke_all_tokens(user_id=u1["id"])
    assert revoked == 1

    import db

    with db.get_db() as conn:
        remaining = conn.execute(
            "SELECT user_id FROM user_tokens"
        ).fetchall()
    assert [r["user_id"] for r in remaining] == [u2["id"]]
