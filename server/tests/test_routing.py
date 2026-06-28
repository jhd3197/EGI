"""Tests for offline routing packs (plan-21, Phase 2).

Covers the public pack index/detail/meta endpoints and the demo pack the server
seeds on init: a connected La Guaira road grid the PWA can run A* over offline.
All endpoints are public — a victim downloads a pack before any account exists.
"""


def test_demo_pack_listed(client):
    r = client.get("/routing/packs")
    assert r.status_code == 200, r.text
    records = r.json()["records"]
    ids = {p["id"] for p in records}
    assert "la-guaira-demo" in ids
    demo = next(p for p in records if p["id"] == "la-guaira-demo")
    assert demo["region"] == "La Guaira"
    assert demo["node_count"] >= 30
    assert demo["edge_count"] > 0
    assert isinstance(demo["bbox"], list) and len(demo["bbox"]) == 4


def test_list_filter_by_region(client):
    assert client.get("/routing/packs?region=La Guaira").json()["records"]
    assert client.get("/routing/packs?region=Nowhere").json()["records"] == []


def test_pack_graph_download(client):
    g = client.get("/routing/packs/la-guaira-demo").json()
    assert g["id"] == "la-guaira-demo"
    assert g["version"] == 1
    # bbox is [minLon, minLat, maxLon, maxLat].
    assert g["bbox"][0] < g["bbox"][2] and g["bbox"][1] < g["bbox"][3]
    # nodes are [lat, lon]; edges are [fromIdx, toIdx, meters, flags].
    assert len(g["nodes"]) == 36
    for e in g["edges"]:
        assert len(e) == 4
        assert 0 <= e[0] < len(g["nodes"]) and 0 <= e[1] < len(g["nodes"])
        assert e[2] > 0  # precomputed metres


def test_pack_meta_endpoint(client):
    meta = client.get("/routing/packs/la-guaira-demo/meta").json()
    assert meta["id"] == "la-guaira-demo"
    assert "nodes" not in meta  # metadata only, no graph payload


def test_missing_pack_404(client):
    assert client.get("/routing/packs/does-not-exist").status_code == 404
    assert client.get("/routing/packs/does-not-exist/meta").status_code == 404


def test_reseed_is_idempotent(client):
    import modules.routing as routing

    before = client.get("/routing/packs/la-guaira-demo/meta").json()
    routing.seed_demo_packs()  # same version → no-op
    after = client.get("/routing/packs/la-guaira-demo/meta").json()
    assert before["version"] == after["version"] == 1
    assert before["created_at"] == after["created_at"]
