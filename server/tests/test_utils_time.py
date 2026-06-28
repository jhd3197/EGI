# Unit tests for the shared timeutil helpers.
# TEST DATA — NOT REAL.
from datetime import datetime, timezone

import timeutil


def test_utc_now_iso_is_parseable_and_aware():
    s = timeutil.utc_now_iso()
    parsed = datetime.fromisoformat(s)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(None)


def test_parse_iso_none_and_empty_return_none():
    assert timeutil.parse_iso(None) is None
    assert timeutil.parse_iso("") is None


def test_parse_iso_handles_trailing_z():
    parsed = timeutil.parse_iso("2026-01-01T00:00:00Z")
    assert parsed == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_parse_iso_offset_form():
    parsed = timeutil.parse_iso("2026-01-01T00:00:00+00:00")
    assert parsed == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_parse_iso_naive_stays_naive():
    parsed = timeutil.parse_iso("2026-01-01T00:00:00")
    assert parsed is not None
    assert parsed.tzinfo is None


def test_parse_iso_garbage_returns_none():
    assert timeutil.parse_iso("not-a-timestamp") is None


def test_normalize_ts_none_and_empty_pass_through():
    assert timeutil.normalize_ts(None) is None
    assert timeutil.normalize_ts("") == ""


def test_normalize_ts_canonical_z_form():
    # Offset form is re-emitted with a Z suffix.
    assert timeutil.normalize_ts("2026-01-01T00:00:00+00:00") == "2026-01-01T00:00:00Z"
    # Already-Z stays Z.
    assert timeutil.normalize_ts("2026-01-01T00:00:00Z") == "2026-01-01T00:00:00Z"


def test_normalize_ts_naive_treated_as_utc():
    assert timeutil.normalize_ts("2026-01-01T00:00:00") == "2026-01-01T00:00:00Z"


def test_normalize_ts_equal_instants_compare_equal():
    a = timeutil.normalize_ts("2026-01-01T00:00:00+00:00")
    b = timeutil.normalize_ts("2026-01-01T00:00:00Z")
    assert a == b


def test_normalize_ts_converts_offset_to_utc():
    # +02:00 instant becomes the equivalent UTC Z form.
    assert timeutil.normalize_ts("2026-01-01T02:00:00+02:00") == "2026-01-01T00:00:00Z"


def test_normalize_ts_unparseable_returned_unchanged():
    assert timeutil.normalize_ts("garbage") == "garbage"
