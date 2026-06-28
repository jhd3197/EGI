# Unit tests for small shared helpers: ids, jsonutil, api_response,
# db.placeholders, security.sha256_hex.
# TEST DATA — NOT REAL.
import hashlib

import pytest

import api_response
import db
import ids
import jsonutil
import security


# ── ids.new_id ──────────────────────────────────────────────────────────────

def test_new_id_shape_and_length():
    rid = ids.new_id("person")
    prefix, _, hexpart = rid.partition("-")
    assert prefix == "person"
    assert len(hexpart) == 8
    assert all(c in "0123456789abcdef" for c in hexpart)


def test_new_id_custom_length():
    rid = ids.new_id("sh", length=12)
    assert len(rid.split("-", 1)[1]) == 12


def test_new_id_length_clamped():
    # Clamped to [1, 32].
    assert len(ids.new_id("x", length=0).split("-", 1)[1]) == 1
    assert len(ids.new_id("x", length=999).split("-", 1)[1]) == 32


def test_new_id_is_unique():
    assert ids.new_id("a") != ids.new_id("a")


# ── jsonutil.dumps / loads_list ─────────────────────────────────────────────

def test_dumps_none_passes_through():
    assert jsonutil.dumps(None) is None


def test_dumps_encodes_iterable_as_list():
    assert jsonutil.dumps(["a", "b"]) == '["a", "b"]'
    assert jsonutil.dumps(("a", "b")) == '["a", "b"]'


def test_dumps_unencodable_returns_none():
    # A non-iterable can't be wrapped in list() -> None.
    assert jsonutil.dumps(5) is None


def test_loads_list_empty_and_none():
    assert jsonutil.loads_list(None) == []
    assert jsonutil.loads_list("") == []


def test_loads_list_garbage_returns_empty():
    assert jsonutil.loads_list("{not json") == []


def test_loads_list_non_list_json_returns_empty():
    # Valid JSON but not a list -> [].
    assert jsonutil.loads_list('{"a": 1}') == []
    assert jsonutil.loads_list("42") == []


def test_loads_list_roundtrip():
    assert jsonutil.loads_list(jsonutil.dumps(["x", "y"])) == ["x", "y"]


# ── api_response.records / ok ───────────────────────────────────────────────

def test_records_basic():
    assert api_response.records([1, 2, 3]) == {"records": [1, 2, 3]}


def test_records_materializes_iterable_and_merges_extras():
    out = api_response.records(iter([1, 2]), count=2, cursor="abc")
    assert out == {"records": [1, 2], "count": 2, "cursor": "abc"}


def test_ok_basic_and_with_fields():
    assert api_response.ok() == {"ok": True}
    assert api_response.ok(id="x", written=1) == {"ok": True, "id": "x", "written": 1}


# ── db.placeholders ─────────────────────────────────────────────────────────

def test_placeholders_three():
    assert db.placeholders([1, 2, 3]) == "?, ?, ?"


def test_placeholders_single_and_empty():
    assert db.placeholders([1]) == "?"
    assert db.placeholders([]) == ""


# ── security.sha256_hex ─────────────────────────────────────────────────────

def test_sha256_hex_matches_hashlib():
    assert security.sha256_hex("token") == hashlib.sha256(b"token").hexdigest()


def test_sha256_hex_is_deterministic():
    assert security.sha256_hex("abc") == security.sha256_hex("abc")
    assert len(security.sha256_hex("abc")) == 64
