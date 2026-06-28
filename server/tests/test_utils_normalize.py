# Unit tests for the shared normalize helpers (names, cédulas, phones).
# TEST DATA — NOT REAL.
import normalize


# ── normalize_name ──────────────────────────────────────────────────────────

def test_normalize_name_none_and_empty():
    assert normalize.normalize_name(None) == ""
    assert normalize.normalize_name("") == ""


def test_normalize_name_lowercases_strips_accents_collapses_ws():
    assert normalize.normalize_name("  José   PÉREZ  ") == "jose perez"


def test_normalize_name_accent_equivalence():
    assert normalize.normalize_name("María") == normalize.normalize_name("maria")


# ── normalize_cedula ────────────────────────────────────────────────────────

def test_normalize_cedula_none_and_empty():
    assert normalize.normalize_cedula(None) == ""
    assert normalize.normalize_cedula("") == ""


def test_normalize_cedula_keep_prefix_default_true():
    assert normalize.normalize_cedula("V-12.345.678") == "V12345678"
    assert normalize.normalize_cedula("v12345678") == "V12345678"


def test_normalize_cedula_collapses_variants():
    assert (
        normalize.normalize_cedula("V-12.345.678")
        == normalize.normalize_cedula("v12345678")
    )


def test_normalize_cedula_keep_prefix_false_strips_letter():
    assert normalize.normalize_cedula("V-12.345.678", keep_prefix=False) == "12345678"


def test_normalize_cedula_no_prefix_input():
    assert normalize.normalize_cedula("12345678") == "12345678"


def test_normalize_cedula_no_digits_returns_empty():
    assert normalize.normalize_cedula("V-") == ""
    assert normalize.normalize_cedula("abc") == ""


def test_normalize_cedula_letter_after_digit_ignored():
    # The nationality letter is only captured before any digit.
    assert normalize.normalize_cedula("12V34") == "1234"


# ── normalize_phone ─────────────────────────────────────────────────────────

def test_normalize_phone_none_and_empty():
    assert normalize.normalize_phone(None) == ""
    assert normalize.normalize_phone("") == ""


def test_normalize_phone_match_last_10_digits():
    assert normalize.normalize_phone("+58 412-555-1234") == "4125551234"


def test_normalize_phone_match_too_short_returns_empty():
    # Fewer than 7 digits -> "".
    assert normalize.normalize_phone("123456") == ""


def test_normalize_phone_match_keeps_last_ten():
    # 11 digits -> drops the leading one.
    assert normalize.normalize_phone("14155552671") == "4155552671"


def test_normalize_phone_plus_keeps_plus():
    assert normalize.normalize_phone("+58 (412) 555-1234", strategy="plus") == "+584125551234"


def test_normalize_phone_whatsapp_strips_prefix():
    assert (
        normalize.normalize_phone("whatsapp:+584125551234", strategy="whatsapp")
        == "+584125551234"
    )


def test_normalize_phone_digits_only_drops_plus():
    assert normalize.normalize_phone("+58 412-555-1234", strategy="digits") == "584125551234"
