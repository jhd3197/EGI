# Health, readiness & metrics endpoints (plan-15 Phase 1). TEST DATA — NOT REAL.

import db
from modules import health


def test_health_structured_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert "version" in body
    checks = body["checks"]
    assert checks["database"]["status"] in ("pass", "warn")
    assert "response_ms" in checks["database"]
    assert checks["uploads_dir"]["status"] in ("pass", "warn")
    assert "free_bytes" in checks["uploads_dir"]
    assert "pending" in checks["sync_queue"]


def test_health_503_on_db_failure(client, monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(health, "check_database", lambda: {"status": "fail", "error": "db down"})
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "unhealthy"


def test_ready_endpoint(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_metrics_scrapeable(client):
    # Generate a request so a counter exists.
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    text = r.text
    assert "egi_http_requests_total" in text
    assert "egi_http_request_duration_seconds_bucket" in text
    assert "egi_db_size_bytes" in text
    assert "egi_pending_moderation_total" in text
    assert "egi_build_info" in text
    # No personal data: concrete ids never appear as route labels.
    assert 'route="/health"' in text


def test_metrics_sync_counter(client):
    payload = {
        "records": [
            {"id": "egi-test-1", "name": "TEST PERSON", "status": "missing"},
        ]
    }
    client.post("/sync", json=payload)
    text = client.get("/metrics").text
    assert 'egi_sync_records_total{direction="in"}' in text


def test_uploads_check_reports_free_space(tmp_path):
    result = health.check_uploads_dir(tmp_path)
    assert result["status"] in ("pass", "warn")
    assert result["free_bytes"] > 0
