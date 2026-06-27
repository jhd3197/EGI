# Data-quality scoring (plan-13 §4): completeness/confidence/freshness scoring,
# stale detection, low-quality list, recalculation. TEST DATA — NOT REAL.

from datetime import datetime, timezone, timedelta

from modules import quality


def _iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def _sync(client, records):
    res = client.post("/sync", json={"records": records})
    assert res.status_code == 200, res.text


def test_score_complete_record_high(client):
    now = _iso(datetime.now(timezone.utc))
    _sync(client, [{
        "id": "q-full", "name": "Ana Pérez", "status": "missing", "age": 30,
        "sex": "F", "contact": "+58 4141234567", "location": "Caracas",
        "last_seen_date": "2026-06-01", "source": "web", "reviewed": 1,
        "createdAt": now, "updatedAt": now,
    }])
    score = quality.score_person("q-full")
    assert score["completeness"] == 100
    assert score["confidence"] >= 80
    assert score["freshness"] >= 95
    assert score["score"] >= 90
    assert score["issues"] == []


def test_score_sparse_record_flags_issues(client):
    now = _iso(datetime.now(timezone.utc))
    _sync(client, [{
        "id": "q-sparse", "status": "missing", "source": "ocr", "reviewed": 0,
        "createdAt": now, "updatedAt": now,
    }])
    score = quality.score_person("q-sparse")
    assert "missing_name" in score["issues"]
    assert "missing_contact" in score["issues"]
    assert "missing_location" in score["issues"]
    assert "unreviewed" in score["issues"]
    assert score["score"] < 60


def test_rejected_record_zero_confidence(client):
    now = _iso(datetime.now(timezone.utc))
    _sync(client, [{
        "id": "q-rej", "name": "X", "status": "missing", "reviewed": -1,
        "createdAt": now, "updatedAt": now,
    }])
    score = quality.score_person("q-rej")
    assert score["confidence"] == 0
    assert "rejected" in score["issues"]


def test_stale_record_flagged(client):
    old = _iso(datetime.now(timezone.utc) - timedelta(days=45))
    _sync(client, [{
        "id": "q-stale", "name": "Old", "status": "missing",
        "createdAt": old, "updatedAt": old,
    }])
    score = quality.score_person("q-stale")
    assert score["freshness"] == 0
    assert "stale" in score["issues"]
    out = quality.stale_records(days=30)
    assert "q-stale" in [r["id"] for r in out["records"]]


def test_score_person_404(client):
    res = client.get("/quality/persons/ghost")
    assert res.status_code == 404


def test_recalculate_and_low_quality(client):
    now = _iso(datetime.now(timezone.utc))
    _sync(client, [
        {"id": "q1", "name": "Full", "contact": "x@y.com", "location": "A",
         "age": 1, "sex": "F", "status": "missing", "reviewed": 1,
         "createdAt": now, "updatedAt": now},
        {"id": "q2", "status": "missing", "source": "ocr",
         "createdAt": now, "updatedAt": now},
    ])
    out = client.post("/quality/recalculate").json()
    assert out["scored"] == 2
    low = client.get("/quality/low", params={"threshold": 60}).json()
    ids = [r["person_id"] for r in low["records"]]
    assert "q2" in ids and "q1" not in ids
    # Summary aggregates are present.
    summ = client.get("/quality/summary").json()
    assert summ["scored"] == 2
    assert summ["avg_score"] is not None


def test_recalculate_excludes_merged(client):
    now = _iso(datetime.now(timezone.utc))
    _sync(client, [
        {"id": "qa", "name": "Canon", "status": "missing", "createdAt": now, "updatedAt": now},
        {"id": "qb", "name": "Dup", "status": "missing", "merged_into": "qa",
         "createdAt": now, "updatedAt": now},
    ])
    out = quality.recalculate_all()
    assert out["scored"] == 1


def test_quality_route_caches_and_returns(client):
    now = _iso(datetime.now(timezone.utc))
    _sync(client, [{"id": "qc", "name": "C", "status": "missing",
                    "createdAt": now, "updatedAt": now}])
    first = client.get("/quality/persons/qc")
    assert first.status_code == 200
    cached = quality.get_score("qc")
    assert cached is not None and cached["person_id"] == "qc"
