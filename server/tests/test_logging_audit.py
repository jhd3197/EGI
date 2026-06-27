# Structured logging, request-id tracing & consolidated audit log
# (plan-15 Phase 2). TEST DATA — NOT REAL.

import json
import logging

from logging_config import JsonFormatter, request_id_var
from modules import audit


def test_request_id_header_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert r.headers.get("X-Request-ID") == "trace-abc-123"


def test_request_id_generated_when_absent(client):
    r = client.get("/health")
    rid = r.headers.get("X-Request-ID")
    assert rid and len(rid) >= 8


def test_json_formatter_includes_request_id():
    fmt = JsonFormatter()
    token = request_id_var.set("rid-xyz")
    try:
        record = logging.makeLogRecord(
            {"msg": "hello", "levelname": "INFO", "name": "egi.test"}
        )
        record.request_id = request_id_var.get("")
        line = fmt.format(record)
    finally:
        request_id_var.reset(token)
    obj = json.loads(line)
    assert obj["message"] == "hello"
    assert obj["request_id"] == "rid-xyz"
    assert obj["level"] == "INFO"


def test_audit_log_endpoint_consolidated(client):
    audit.log_action("op:test", "approve", "person", "p-1", detail="ok")
    audit.log_history("p-1", "create", actor="op:test", source="web")

    r = client.get("/audit/log")
    assert r.status_code == 200
    body = r.json()
    kinds = {e["kind"] for e in body["entries"]}
    assert "action" in kinds
    assert "history" in kinds


def test_audit_log_filter_by_source(client):
    audit.log_action("op:test", "reject", "person", "p-2")
    audit.log_history("p-2", "update", actor="op:test")

    actions = client.get("/audit/log?source=actions").json()["entries"]
    assert actions and all(e["kind"] == "action" for e in actions)

    history = client.get("/audit/log?source=history").json()["entries"]
    assert history and all(e["kind"] == "history" for e in history)


def test_audit_log_export_attachment(client):
    audit.log_action("op:test", "approve", "person", "p-3")
    r = client.get("/audit/log?format=export")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    assert "entries" in r.json()
