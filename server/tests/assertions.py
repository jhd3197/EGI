# Shared assertion helpers for the EGI server test suite.

def assert_is_pdf(response):
    """Assert an HTTP response is a successful PDF (status 200 + magic bytes)."""
    assert response.status_code == 200, getattr(response, "text", response)
    assert response.content[:4] == b"%PDF"


def assert_bbox_validation(client, endpoint):
    """A malformed ?bbox query param on ``endpoint`` must yield HTTP 400."""
    assert client.get(f"{endpoint}?bbox=1,2,3").status_code == 400
    assert client.get(f"{endpoint}?bbox=a,b,c,d").status_code == 400


def assert_user_response_sanitized(user_or_list):
    """No password_hash leaks in a user dict (or list of user dicts)."""
    items = user_or_list if isinstance(user_or_list, list) else [user_or_list]
    for u in items:
        assert "password_hash" not in u
