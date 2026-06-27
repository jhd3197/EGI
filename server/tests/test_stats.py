# Dashboard statistics endpoints (plan-13 §3): per-operation and global stats
# plus the daily time series. TEST DATA — NOT REAL. All names/coords are fake.

def _seed(client, op_id, records):
    base = {"createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"}
    payload = []
    for r in records:
        rec = {**base, **r}
        rec.setdefault("disaster_id", op_id)
        payload.append(rec)
    res = client.post("/sync", json={"records": payload})
    assert res.status_code == 200, res.text


def test_operation_stats_counts_by_status(client):
    op = client.post("/operations", json={"name": "Stats Op"}).json()
    _seed(client, op["id"], [
        {"id": "s1", "name": "A", "status": "missing"},
        {"id": "s2", "name": "B", "status": "missing"},
        {"id": "s3", "name": "C", "status": "found"},
    ])
    res = client.get(f"/stats/operations/{op['id']}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["persons_total"] == 3
    assert body["persons_by_status"]["missing"] == 2
    assert body["persons_by_status"]["found"] == 1
    # All valid statuses are present (zero-filled).
    assert "deceased" in body["persons_by_status"]
    assert body["records_per_day"][0]["count"] == 3


def test_operation_stats_excludes_merged(client):
    op = client.post("/operations", json={"name": "Merge Op"}).json()
    _seed(client, op["id"], [
        {"id": "m1", "name": "Canon", "status": "missing"},
        {"id": "m2", "name": "Dup", "status": "missing", "merged_into": "m1"},
    ])
    body = client.get(f"/stats/operations/{op['id']}").json()
    assert body["persons_total"] == 1


def test_operation_stats_404(client):
    assert client.get("/stats/operations/ghost").status_code == 404


def test_operation_stats_active_tasks(client):
    op = client.post("/operations", json={"name": "Task Op"}).json()
    # Creating an action plan seeds default templates as pending tasks.
    res = client.post(f"/operations/{op['id']}/action-plans", json={})
    assert res.status_code == 200, res.text
    body = client.get(f"/stats/operations/{op['id']}").json()
    assert body["tasks"]["total"] >= 1
    assert body["tasks"]["active"] >= 1


def test_global_stats(client):
    op = client.post("/operations", json={"name": "Global Op"}).json()
    _seed(client, op["id"], [
        {"id": "g1", "name": "A", "status": "missing"},
        {"id": "g2", "name": "B", "status": "safe"},
        {"id": "g3", "name": "Pending", "status": "missing", "source": "ocr", "reviewed": 0},
    ])
    body = client.get("/stats/global").json()
    # All live (non-rejected, non-merged) rows count; the pending one is also
    # surfaced separately via the moderation_queue field.
    assert body["persons_total"] == 3
    assert body["persons_by_status"]["missing"] == 2
    assert body["operations_total"] >= 1
    assert body["moderation_queue"] == 1
    assert "duplicate_clusters" in body


def test_operation_timeseries(client):
    op = client.post("/operations", json={"name": "TS Op"}).json()
    _seed(client, op["id"], [{"id": "t1", "name": "A", "status": "found"}])
    res = client.get(f"/stats/operations/{op['id']}/timeseries", params={"days": 7})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["days"] == 7
    assert body["new_reports"][0]["count"] == 1
    assert body["resolved"][0]["count"] == 1
