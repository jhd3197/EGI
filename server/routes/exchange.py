"""Routes for CSV/Excel person import & export (plan-12 §1).

Thin HTTP adapters over ``modules/exchange.py``. Exports are operator-gated
(they expose personal crisis data in bulk); imports are operator-gated and
rate-limited (a bulk upload is a heavy write). xlsx requests degrade to a clear
503 when openpyxl is unavailable so CSV keeps working on minimal installs.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from auth import require_operator
from modules import exchange
from ratelimit import rate_limit

router = APIRouter()


def _export(fmt: str, status: Optional[str], disaster_id: Optional[str],
            since: Optional[str]) -> Response:
    try:
        content, filename, media_type = exchange.export_persons(
            fmt, status=status, disaster_id=disaster_id, since=since
        )
    except exchange.OpenpyxlUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/persons.csv")
def export_persons_csv(
    status: Optional[str] = Query(None),
    disaster_id: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    operator: str = Depends(require_operator),
):
    return _export("csv", status, disaster_id, since)


@router.get("/export/persons.xlsx")
def export_persons_xlsx(
    status: Optional[str] = Query(None),
    disaster_id: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    operator: str = Depends(require_operator),
):
    return _export("xlsx", status, disaster_id, since)


@router.get("/import/persons/template.csv")
def import_template_csv(operator: str = Depends(require_operator)):
    return Response(
        content=exchange.template_csv(),
        media_type=exchange.CSV_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="egi-persons-template.csv"'},
    )


@router.post("/import/persons", dependencies=[Depends(rate_limit)])
def import_persons(
    file: UploadFile = File(...),
    auto_approve: bool = Form(False),
    column_map: Optional[str] = Form(None),
    dry_run: bool = Form(False),
    operator: str = Depends(require_operator),
):
    parsed_map = None
    if column_map:
        try:
            parsed_map = json.loads(column_map)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="column_map must be valid JSON")
        if not isinstance(parsed_map, dict):
            raise HTTPException(status_code=400, detail="column_map must be a JSON object")

    file_bytes = file.file.read()
    try:
        return exchange.import_persons(
            file_bytes,
            file.filename or "",
            column_map=parsed_map,
            auto_approve=auto_approve,
            dry_run=dry_run,
        )
    except exchange.OpenpyxlUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
