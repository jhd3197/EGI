# Unit tests for routes.dependencies — parse_bbox and get_or_404.
# Called directly as plain functions (no router needed).
# TEST DATA — NOT REAL.
import pytest
from fastapi import HTTPException

from routes import dependencies


# ── parse_bbox ──────────────────────────────────────────────────────────────

def test_parse_bbox_none_returns_none():
    assert dependencies.parse_bbox(None) is None
    assert dependencies.parse_bbox("") is None


def test_parse_bbox_valid_four_floats():
    out = dependencies.parse_bbox("-67.1,10.5,-66.9,10.7")
    assert out == [-67.1, 10.5, -66.9, 10.7]


def test_parse_bbox_wrong_length_raises_400():
    with pytest.raises(HTTPException) as exc:
        dependencies.parse_bbox("1,2,3")
    assert exc.value.status_code == 400


def test_parse_bbox_non_numeric_raises_400():
    with pytest.raises(HTTPException) as exc:
        dependencies.parse_bbox("a,b,c,d")
    assert exc.value.status_code == 400


# ── get_or_404 ──────────────────────────────────────────────────────────────

def test_get_or_404_returns_value():
    record = {"id": "x", "name": "Shelter de prueba"}
    assert dependencies.get_or_404(lambda _id: record, "x") is record


def test_get_or_404_raises_404_on_none():
    with pytest.raises(HTTPException) as exc:
        dependencies.get_or_404(lambda _id: None, "missing")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Record not found"


def test_get_or_404_uses_label_in_message():
    with pytest.raises(HTTPException) as exc:
        dependencies.get_or_404(lambda _id: None, "missing", label="Shelter")
    assert exc.value.detail == "Shelter not found"


def test_get_or_404_falsy_record_raises():
    # Any falsy fetch result (e.g. empty dict) is treated as "not found".
    with pytest.raises(HTTPException):
        dependencies.get_or_404(lambda _id: {}, "x")
