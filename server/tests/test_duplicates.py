# Fuzzy-dedup clustering + merge/reject endpoints. TEST DATA — NOT REAL.


def _person(pid, **overrides):
    base = {
        "id": pid,
        "name": "Ana López de prueba",
        "given_name": "Ana",
        "family_name": "López",
        "status": "missing",
        "disaster_id": "d-test",
        "age": 30,
        "location": "Refugio Central",
        "last_known_location": "Refugio Central",
        "last_seen_date": "2026-01-01T08:00:00Z",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def _seed(client, people):
    res = client.post("/sync", json={"records": people})
    assert res.status_code == 200


def test_three_duplicates_form_one_cluster(client):
    # Three records for the same person via different match tiers.
    _seed(client, [
        _person("dup-a", cedula="V-12345678"),
        _person("dup-b", cedula="V-12345678", name="Ana L."),  # tier1: same cédula
        _person("dup-c", age=31),                              # tier2: name + age±2
    ])
    clusters = client.get("/duplicates/pending").json()["clusters"]
    assert len(clusters) == 1
    members = {m["id"] for m in clusters[0]["members"]}
    assert members == {"dup-a", "dup-b", "dup-c"}


def test_distinct_people_do_not_cluster(client):
    _seed(client, [
        _person("p1", given_name="Ana", family_name="López", cedula="V-1",
                location="Norte", last_known_location="Norte"),
        _person("p2", given_name="Beto", family_name="Pérez", cedula="V-2",
                age=55, location="Sur", last_known_location="Sur",
                last_seen_date="2026-05-05T08:00:00Z"),
    ])
    assert client.get("/duplicates/pending").json()["clusters"] == []


def test_merge_preserves_reports_and_hides_duplicate(client):
    _seed(client, [
        _person("canon", cedula="V-999"),
        _person("dupe", cedula="V-999"),
    ])
    # A report on the duplicate must follow it to the canonical record.
    client.post("/persons/dupe/reports", json={
        "id": "rep-1", "person_id": "dupe", "note": "Visto en el refugio",
        "createdAt": "2026-01-02T00:00:00Z", "updatedAt": "2026-01-02T00:00:00Z",
    })
    cluster_id = client.get("/duplicates/pending").json()["clusters"][0]["cluster_id"]

    res = client.post(f"/duplicates/{cluster_id}/merge", json={"canonical_id": "canon"})
    body = res.json()
    assert body["merged"] == ["dupe"]
    assert body["reports_moved"] == 1

    # Report now belongs to the canonical record.
    canon_reports = client.get("/persons/canon/reports").json()["records"]
    assert any(r["id"] == "rep-1" for r in canon_reports)

    # Duplicate is soft-deleted: hidden from search but still fetchable + pointed.
    ids = [r["id"] for r in client.get("/persons", params={"q": "Ana"}).json()["records"]]
    assert "dupe" not in ids
    assert "canon" in ids
    assert client.get("/persons/dupe").json()["merged_into"] == "canon"

    # Cluster is gone now that the duplicate is merged.
    assert client.get("/duplicates/pending").json()["clusters"] == []


def test_rejected_cluster_not_suggested_again(client):
    _seed(client, [
        _person("r1", cedula="V-555"),
        _person("r2", cedula="V-555"),
    ])
    cluster_id = client.get("/duplicates/pending").json()["clusters"][0]["cluster_id"]
    client.post(f"/duplicates/{cluster_id}/reject")
    assert client.get("/duplicates/pending").json()["clusters"] == []


def test_merge_unknown_cluster_404(client):
    assert client.post("/duplicates/nope/merge",
                       json={"canonical_id": "x"}).status_code == 404
