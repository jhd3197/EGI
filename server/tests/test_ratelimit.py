# Rate limiting on write endpoints. TEST DATA — NOT REAL.
# A burst of automated POSTs is throttled with 429 + Retry-After; normal,
# under-the-limit usage is untouched.

from ratelimit import limiter


def _post_record(client, i):
    return client.post("/sync", json={"records": [{
        "id": f"egi-rl-{i}", "name": "Carga de prueba", "status": "safe",
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})


def test_burst_is_throttled_with_retry_after(client):
    # Tight window: 3 writes allowed, the 4th should be rejected.
    limiter.configure(max_requests=3, window_seconds=300)
    try:
        for i in range(3):
            assert _post_record(client, i).status_code == 200
        blocked = _post_record(client, 99)
        assert blocked.status_code == 429
        assert blocked.headers.get("Retry-After")
        assert int(blocked.headers["Retry-After"]) >= 1
    finally:
        limiter.configure(max_requests=100000, window_seconds=300)


def test_normal_usage_not_blocked(client):
    # A handful of writes well under the default limit all succeed.
    limiter.configure(max_requests=30, window_seconds=300)
    try:
        for i in range(10):
            assert _post_record(client, i).status_code == 200
    finally:
        limiter.configure(max_requests=100000, window_seconds=300)


def test_disabled_when_max_zero(client):
    limiter.configure(max_requests=0, window_seconds=300)
    try:
        for i in range(50):
            assert _post_record(client, i).status_code == 200
    finally:
        limiter.configure(max_requests=100000, window_seconds=300)
