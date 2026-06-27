# Community poster PDF (plan-14 §9). TEST DATA — NOT REAL.


def test_poster_pdf_for_operation(client):
    op_id = client.post("/operations", json={"name": "Operativo Prueba"}).json()["id"]
    res = client.get(f"/operations/{op_id}/poster.pdf", params={"lang": "es"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")


def test_poster_unknown_operation_404(client):
    res = client.get("/operations/does-not-exist/poster.pdf")
    assert res.status_code == 404
