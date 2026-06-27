"""Routes for the OCR paper-import + review flow.

NOTE: the module file is ``imports.py`` (not ``import.py``) because ``import``
is a reserved word and cannot be used as a module name in an import statement.

The OCR engine, LLM extractor, and upload dir are read from the ``main`` module
*at request time* and passed into the logic layer, so the test suite's
monkeypatching of ``main.ocr_image`` / ``main.extract_with_llm`` /
``main.UPLOAD_DIR`` continues to take effect.
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from auth import require_operator
from models import PersonRecord
from modules import normalize, ocr_import
from ratelimit import rate_limit

router = APIRouter()


class NormalizeRequest(BaseModel):
    text: str
    disaster_id: Optional[str] = None


@router.post("/import/paper", dependencies=[Depends(rate_limit)])
def import_paper(
    file: UploadFile = File(...),
    disaster_id: Optional[str] = Form(None),
    run_llm: bool = Form(True),
):
    import main  # late import: read the (possibly monkeypatched) hooks at call time

    return ocr_import.create_paper_import(
        file=file,
        disaster_id=disaster_id,
        run_llm=run_llm,
        upload_dir=main.UPLOAD_DIR,
        ocr_fn=main.ocr_image,
        extract_fn=main.extract_with_llm,
    )


@router.get("/import/paper")
def list_ocr_imports(reviewed: Optional[int] = Query(None)):
    return ocr_import.list_ocr_imports(reviewed)


@router.get("/import/paper/{record_id}")
def get_ocr_import(record_id: str):
    return ocr_import.get_ocr_import(record_id)


@router.post("/import/paper/{record_id}/review")
def review_ocr_import(
    record_id: str, record: PersonRecord, operator: str = Depends(require_operator)
):
    return ocr_import.review_ocr_import(record_id, record, operator=operator)


@router.post("/normalize", dependencies=[Depends(rate_limit)])
def normalize_report(req: NormalizeRequest):
    """Operator/dev: turn a free-text report into an unreviewed ai_draft record."""
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    return normalize.normalize_text(req.text, disaster_id=req.disaster_id)
