# Paper-import OCR flow with the LLM mocked, plus the draft review flow.
# No real Tesseract or LLM is ever invoked. TEST DATA — NOT REAL.
import types

import pytest

import main
import ocr


@pytest.fixture()
def fake_ocr(monkeypatch):
    """Stub the OCR engine so tests never need Tesseract/easyocr."""
    monkeypatch.setattr(main, "ocr_image", lambda path: ("Texto OCR de prueba", 0.9))


def _upload(client, run_llm=True):
    return client.post(
        "/import/paper",
        files={"file": ("reporte.jpg", b"fake-image-bytes", "image/jpeg")},
        data={"disaster_id": "d-test", "run_llm": str(run_llm).lower()},
    )


def test_import_paper_creates_unreviewed_draft(client, fake_ocr, monkeypatch):
    # Mocked LLM extraction returns structured fields (stands in for OpenAI/Groq/etc).
    monkeypatch.setattr(main, "extract_with_llm", lambda text: {
        "name": "Juan Pérez de prueba",
        "status": "missing",
        "cedula": "V-00000000",
    })

    res = _upload(client, run_llm=True)
    assert res.status_code == 200
    body = res.json()
    assert body["reviewed"] is False
    assert body["ocr_text"] == "Texto OCR de prueba"
    assert body["extracted"]["name"] == "Juan Pérez de prueba"

    record_id = body["id"]
    # The draft is persisted with source='ocr' and reviewed=0 (out of trusted set).
    draft = client.get(f"/import/paper/{record_id}").json()
    assert draft["source"] == "ocr"
    assert draft["reviewed"] == 0
    assert draft["status"] == "missing"
    assert draft["cedula"] == "V-00000000"

    unreviewed = client.get("/import/paper", params={"reviewed": 0}).json()["records"]
    assert any(r["id"] == record_id for r in unreviewed)


def test_import_paper_without_llm(client, fake_ocr, monkeypatch):
    # When run_llm is false the LLM must not be called and no fields are extracted.
    def _boom(text):
        raise AssertionError("extract_with_llm should not be called when run_llm=False")

    monkeypatch.setattr(main, "extract_with_llm", _boom)
    res = _upload(client, run_llm=False)
    assert res.status_code == 200
    body = res.json()
    assert body["extracted"] is None
    assert body["ocr_text"] == "Texto OCR de prueba"


def test_review_publishes_draft(client, fake_ocr, monkeypatch):
    monkeypatch.setattr(main, "extract_with_llm", lambda text: {"name": "Borrador", "status": "missing"})
    record_id = _upload(client).json()["id"]

    # Moderator approves: reviewed defaults to 1, fields can be corrected.
    res = client.post(
        f"/import/paper/{record_id}/review",
        json={"name": "Nombre corregido", "status": "found", "reviewed": 1},
    )
    assert res.status_code == 200

    draft = client.get(f"/import/paper/{record_id}").json()
    assert draft["reviewed"] == 1
    assert draft["name"] == "Nombre corregido"
    assert draft["status"] == "found"

    # It should no longer appear among the unreviewed drafts.
    unreviewed = client.get("/import/paper", params={"reviewed": 0}).json()["records"]
    assert all(r["id"] != record_id for r in unreviewed)


def test_review_missing_record_404(client):
    res = client.post("/import/paper/nope/review", json={"reviewed": 1})
    assert res.status_code == 404


def test_extract_with_llm_skipped_when_no_model(monkeypatch):
    # With no LLM_MODEL configured, extraction is a no-op returning None.
    monkeypatch.setattr(ocr, "LLM_MODEL", "")
    assert ocr.extract_with_llm("cualquier texto") is None


def test_extract_with_llm_uses_mocked_model(monkeypatch):
    # Inject a fake `prompture` module so no real provider/API is touched.
    monkeypatch.setattr(ocr, "LLM_MODEL", "openai/test-model")

    class _Result:
        def model_dump(self, exclude_none=True):
            return {"name": "Juan Pérez de prueba", "status": "missing"}

    fake_prompture = types.ModuleType("prompture")
    fake_prompture.extract_with_model = lambda schema, prompt, model_name: _Result()
    monkeypatch.setitem(__import__("sys").modules, "prompture", fake_prompture)

    out = ocr.extract_with_llm("Reporte de prueba")
    assert out == {"name": "Juan Pérez de prueba", "status": "missing"}
