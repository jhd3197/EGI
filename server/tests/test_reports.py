# SITREP generation + scheduled reports (plan-13 §3). TEST DATA — NOT REAL.

import importlib.util

from assertions import assert_is_pdf
from factories import create_operation
from modules import scheduled_reports, sitrep

_HAS_REPORTLAB = importlib.util.find_spec("reportlab") is not None


def _seed_op(client, name="SITREP Op"):
    op = create_operation(client, name=name)
    base = {"createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
            "disaster_id": op["id"]}
    client.post("/sync", json={"records": [
        {"id": "r1", "name": "A", "status": "missing", "lat": 10.5, "lon": -66.9, **base},
        {"id": "r2", "name": "B", "status": "found", **base},
    ]})
    return op


def test_sitrep_json(client):
    op = _seed_op(client)
    res = client.get(f"/operations/{op['id']}/sitrep", params={"format": "json"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["operation"]["id"] == op["id"]
    assert body["metrics"]["persons_total"] == 2
    assert body["metrics"]["persons_by_status"]["missing"] == 1
    assert "quality" in body and "suggested_sectors" in body


def test_sitrep_html(client):
    op = _seed_op(client)
    res = client.get(f"/operations/{op['id']}/sitrep", params={"format": "html"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "SITREP" in res.text
    assert "Personas por estado" in res.text


def test_sitrep_unknown_operation_404(client):
    res = client.get("/operations/ghost/sitrep")
    assert res.status_code == 404


def test_sitrep_pdf(client):
    op = _seed_op(client)
    res = client.get(f"/operations/{op['id']}/sitrep", params={"format": "pdf"})
    if _HAS_REPORTLAB:
        assert_is_pdf(res)
        assert res.headers["content-type"] == "application/pdf"
    else:
        # Degrades to 503 when reportlab is absent (like the flyer route).
        assert res.status_code == 503


def test_sitrep_module_html_renders_without_routing():
    # Pure render of a hand-built data dict (no DB) to lock the HTML shape.
    data = {
        "generated_at": "2026-06-27T00:00:00Z",
        "operation": {"id": "op-x", "name": "Demo", "status": "open"},
        "metrics": {
            "persons_total": 3, "geolocated_persons": 1, "pending_review": 0,
            "persons_by_status": {"missing": 2, "found": 1},
            "tasks": {"active": 2, "total": 5},
        },
        "recent_intake": [{"day": "2026-06-26", "count": 3}],
        "resolved": [],
        "quality": {"avg_score": 80.0, "scored": 3, "avg_completeness": 90.0,
                    "avg_confidence": 70.0, "avg_freshness": 95.0, "issues": {"stale": 1}},
        "suggested_sectors": [
            {"sector": "S1", "weight": 2, "centroid": {"lat": 10.5, "lon": -66.9}},
        ],
    }
    out = sitrep.render_html(data)
    assert "Demo" in out and "Desaparecido" in out and "S1" in out


# ── scheduled reports ────────────────────────────────────────────────────────

def test_scheduled_report_crud(client):
    op = _seed_op(client)
    created = client.post("/reports/scheduled", json={
        "operation_id": op["id"], "name": "Daily", "format": "html",
        "schedule_cron": "daily", "recipients": "cmd@example.com",
    })
    assert created.status_code == 200, created.text
    rid = created.json()["id"]
    assert client.get("/reports/scheduled").json()["reports"]
    assert client.get(f"/reports/scheduled/{rid}").json()["id"] == rid
    # Deactivate, then delete.
    patched = client.patch(f"/reports/scheduled/{rid}", json={"active": False})
    assert patched.json()["active"] == 0
    assert client.delete(f"/reports/scheduled/{rid}").json()["ok"] is True
    assert client.get(f"/reports/scheduled/{rid}").status_code == 404


def test_scheduled_report_requires_recipients(client):
    op = _seed_op(client)
    res = client.post("/reports/scheduled", json={
        "operation_id": op["id"], "format": "html", "recipients": "",
    })
    assert res.status_code == 400


def test_is_due_logic():
    never = {"active": 1, "last_run_at": None, "schedule_cron": "daily"}
    assert scheduled_reports.is_due(never) is True
    inactive = {"active": 0, "last_run_at": None, "schedule_cron": "daily"}
    assert scheduled_reports.is_due(inactive) is False
    recent = {"active": 1, "last_run_at": scheduled_reports.now_iso(), "schedule_cron": "daily"}
    assert scheduled_reports.is_due(recent) is False


def test_run_due_delivers_and_stamps(client):
    op = _seed_op(client)
    created = client.post("/reports/scheduled", json={
        "operation_id": op["id"], "name": "Daily", "format": "html",
        "schedule_cron": "daily", "recipients": "cmd@example.com",
    }).json()
    # Manual trigger of the cron job; email uses the log driver (no creds).
    out = client.post("/reports/run-due").json()
    assert out["ran"] == 1
    assert out["results"][0]["sent"] == 1
    # last_run_at is stamped, so a second run-due is not due anymore.
    again = client.post("/reports/run-due").json()
    assert again["ran"] == 0
