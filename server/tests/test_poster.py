# Community poster PDF (plan-14 §9). TEST DATA — NOT REAL.

from assertions import assert_is_pdf
from factories import create_operation


def test_poster_pdf_for_operation(client):
    op_id = create_operation(client, name="Operativo Prueba")["id"]
    res = client.get(f"/operations/{op_id}/poster.pdf", params={"lang": "es"})
    assert_is_pdf(res)
    assert res.headers["content-type"] == "application/pdf"


def test_poster_unknown_operation_404(client):
    res = client.get("/operations/does-not-exist/poster.pdf")
    assert res.status_code == 404
