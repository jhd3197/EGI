"""User accounts, password hashing, and opaque bearer tokens (plan-08).

This is the data layer behind real, role-scoped operator accounts. It replaces
the static ``OPERATOR_TOKENS`` env var (see ``auth.py`` for the FastAPI
dependencies that consume it).

Security choices (plan-08 §3):
  * Passwords are hashed with **bcrypt** (cost factor 12+) via passlib. The
    plaintext is never stored or logged.
  * Bearer tokens are 32-byte URL-safe random strings. We store only
    ``SHA-256(token)`` so the database never holds a usable token; the raw value
    is returned to the client exactly once at creation.
  * Roles are a strict hierarchy: viewer < operator < commander < admin. A
    dependency that requires role R is satisfied by any role at level >= R.

Like the rest of the server, callers get plain dicts (``db.row_to_dict``); the
``password_hash`` column is stripped by ``public_user`` before anything leaves
the API.
"""

import hashlib
import secrets
import uuid
from typing import List, Optional

from passlib.context import CryptContext

import db
from models import now_iso

# bcrypt at cost factor 12 (plan-08 §3). ``deprecated='auto'`` lets us bump the
# cost later and transparently re-hash on next login.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# Role hierarchy. Higher number => more privilege. Kept in sync with the SQLite
# CHECK constraint on users.role in db.py.
ROLE_LEVELS = {"viewer": 0, "operator": 1, "commander": 2, "admin": 3}
VALID_ROLES = set(ROLE_LEVELS)


# ── Password hashing ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time-ish bcrypt verify. Never raises on malformed input."""
    try:
        return _pwd_context.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


# ── Token helpers ───────────────────────────────────────────────────────────

def generate_token() -> str:
    """A fresh opaque bearer token (32 bytes, URL-safe)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 of a token, hex-encoded. This is what we store / look up by."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ── Role helpers ────────────────────────────────────────────────────────────

def role_level(role: Optional[str]) -> int:
    return ROLE_LEVELS.get(role or "", -1)


def role_satisfies(user_role: Optional[str], required_role: str) -> bool:
    return role_level(user_role) >= role_level(required_role)


# ── Serialization ───────────────────────────────────────────────────────────

def public_user(row: Optional[dict]) -> Optional[dict]:
    """Strip the password hash before a user leaves the API."""
    if row is None:
        return None
    out = dict(row)
    out.pop("password_hash", None)
    return out


# ── User CRUD ───────────────────────────────────────────────────────────────

def count_users() -> int:
    with db.get_db() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def get_user_by_id(user_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return db.row_to_dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (_norm_email(email),)
        ).fetchone()
        return db.row_to_dict(row) if row else None


def list_users() -> List[dict]:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
        return [public_user(db.row_to_dict(r)) for r in rows]


def create_user(
    email: str,
    password: str,
    role: str = "viewer",
    name: Optional[str] = None,
    active: int = 1,
) -> dict:
    """Create a user. Raises ValueError on bad role or duplicate email."""
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role!r}")
    email = _norm_email(email)
    if not email:
        raise ValueError("email is required")
    if not password:
        raise ValueError("password is required")
    if get_user_by_email(email):
        raise ValueError("email already exists")

    now = now_iso()
    user_id = f"usr-{uuid.uuid4().hex[:16]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO users
            (id, email, name, role, password_hash, active,
             last_login_at, last_login_ip, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (user_id, email, name, role, hash_password(password), int(active), now, now),
        )
        conn.commit()
    return get_user_by_id(user_id)


def update_user(
    user_id: str,
    *,
    name: Optional[str] = None,
    role: Optional[str] = None,
    active: Optional[int] = None,
) -> Optional[dict]:
    """Patch mutable user fields. Only provided fields change."""
    existing = get_user_by_id(user_id)
    if not existing:
        return None
    if role is not None and role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role!r}")

    sets, params = [], []
    if name is not None:
        sets.append("name = ?")
        params.append(name)
    if role is not None:
        sets.append("role = ?")
        params.append(role)
    if active is not None:
        sets.append("active = ?")
        params.append(int(active))
    if sets:
        sets.append("updated_at = ?")
        params.append(now_iso())
        params.append(user_id)
        with db.get_db() as conn:
            conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
    return get_user_by_id(user_id)


def set_password(user_id: str, password: str) -> bool:
    """Replace a user's password and revoke all their existing tokens.

    Changing the password is a security event, so every outstanding session is
    invalidated — the user must log in again.
    """
    if not password:
        raise ValueError("password is required")
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hash_password(password), now_iso(), user_id),
        )
        conn.execute("DELETE FROM user_tokens WHERE user_id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0


def delete_user(user_id: str) -> bool:
    """Hard-delete a user and all their tokens.

    We delete tokens explicitly rather than relying on ON DELETE CASCADE because
    ``db.get_db()`` does not enable the ``foreign_keys`` pragma per connection.
    """
    with db.get_db() as conn:
        conn.execute("DELETE FROM user_tokens WHERE user_id = ?", (user_id,))
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0


def authenticate(email: str, password: str) -> Optional[dict]:
    """Return the active user for valid email+password, else None.

    Always runs a bcrypt verify (even for unknown emails, against a dummy hash)
    so response timing does not reveal whether an email exists.
    """
    user = get_user_by_email(email)
    if not user:
        # Burn the same work for a missing user to avoid a timing oracle.
        verify_password(password, _DUMMY_HASH)
        return None
    if not user.get("active"):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def touch_login(user_id: str, ip: Optional[str]) -> None:
    with db.get_db() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ?, last_login_ip = ? WHERE id = ?",
            (now_iso(), ip, user_id),
        )
        conn.commit()


# ── Token CRUD ──────────────────────────────────────────────────────────────

def create_token(
    user_id: str, name: Optional[str] = None, expires_at: Optional[str] = None
) -> dict:
    """Mint a new bearer token for a user.

    Returns a dict including the **raw** ``token`` — shown to the client exactly
    once. Only the SHA-256 hash is persisted.
    """
    raw = generate_token()
    token_hash = hash_token(raw)
    now = now_iso()
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_tokens
            (token_hash, user_id, name, expires_at, last_used_at, created_at)
            VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (token_hash, user_id, name, expires_at, now),
        )
        conn.commit()
    return {
        "token": raw,
        "token_hash": token_hash,
        "user_id": user_id,
        "name": name,
        "expires_at": expires_at,
        "created_at": now,
    }


def list_tokens(user_id: str) -> List[dict]:
    """Token metadata for a user (never the raw token — it was never stored)."""
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT token_hash, user_id, name, expires_at, last_used_at, created_at "
            "FROM user_tokens WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [db.row_to_dict(r) for r in rows]


def revoke_token(token_hash: str, user_id: Optional[str] = None) -> bool:
    """Delete a token by its hash. If ``user_id`` is given, only that user's
    token is removed (so a non-admin cannot revoke someone else's token)."""
    with db.get_db() as conn:
        if user_id is not None:
            cur = conn.execute(
                "DELETE FROM user_tokens WHERE token_hash = ? AND user_id = ?",
                (token_hash, user_id),
            )
        else:
            cur = conn.execute(
                "DELETE FROM user_tokens WHERE token_hash = ?", (token_hash,)
            )
        conn.commit()
        return cur.rowcount > 0


def get_user_for_token(token: str) -> Optional[dict]:
    """Resolve a raw bearer token to its active user, or None.

    Enforces token expiry and the user's ``active`` flag, and best-effort
    updates ``last_used_at``. Returns the full user row (caller strips the hash).
    """
    if not token:
        return None
    token_hash = hash_token(token)
    with db.get_db() as conn:
        trow = conn.execute(
            "SELECT * FROM user_tokens WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if not trow:
            return None
        expires_at = trow["expires_at"]
        if expires_at and now_iso() > expires_at:
            # Expired: clean it up and treat as absent.
            conn.execute(
                "DELETE FROM user_tokens WHERE token_hash = ?", (token_hash,)
            )
            conn.commit()
            return None
        urow = conn.execute(
            "SELECT * FROM users WHERE id = ?", (trow["user_id"],)
        ).fetchone()
        if not urow or not urow["active"]:
            return None
        conn.execute(
            "UPDATE user_tokens SET last_used_at = ? WHERE token_hash = ?",
            (now_iso(), token_hash),
        )
        conn.commit()
        return db.row_to_dict(urow)


def _norm_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


# A valid bcrypt hash of a random string, used only to equalize timing for
# unknown-email logins. Never matches a real password.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
