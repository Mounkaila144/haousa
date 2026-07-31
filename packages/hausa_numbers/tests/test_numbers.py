import pytest
from hausa_numbers import (
    generate,
    hausa_words_to_number,
    normalize_hausa_text,
    parse,
)

CASES = {
    0: "sifili",
    1: "ɗaya",
    2: "biyu",
    3: "uku",
    4: "huɗu",
    5: "biyar",
    6: "shida",
    7: "bakwai",
    8: "takwas",
    9: "tara",
    10: "goma",
    11: "goma sha ɗaya",
    12: "goma sha biyu",
    13: "goma sha uku",
    14: "goma sha huɗu",
    15: "goma sha biyar",
    16: "goma sha shida",
    17: "goma sha bakwai",
    18: "goma sha takwas",
    19: "goma sha tara",
    20: "ashirin",
    21: "ashirin da ɗaya",
    29: "ashirin da tara",
    30: "talatin",
    40: "arba'in",
    50: "hamsin",
    60: "sittin",
    70: "saba'in",
    80: "tamanin",
    90: "tasa'in",
    91: "tasa'in da ɗaya",
    99: "tasa'in da tara",
    100: "ɗari",
    101: "ɗari da ɗaya",
    110: "ɗari da goma",
    115: "ɗari da goma sha biyar",
    120: "ɗari da ashirin",
    125: "ɗari da ashirin da biyar",
    200: "ɗari biyu",
    250: "ɗari biyu da hamsin",
    299: "ɗari biyu da tasa'in da tara",
    999: "ɗari tara da tasa'in da tara",
    1_000: "dubu",
    1_001: "dubu ɗaya da ɗaya",
    1_025: "dubu ɗaya da ashirin da biyar",
    1_500: "dubu ɗaya da ɗari biyar",
    2_523: "dubu biyu da ɗari biyar da ashirin da uku",
    10_000: "dubu goma",
    25_750: "dubu ashirin da biyar da ɗari bakwai da hamsin",
    100_000: "dubu ɗari",
    1_000_000: "miliyan ɗaya",
    2_500_000: "miliyan biyu da dubu ɗari biyar",
    1_000_000_000: "biliyan ɗaya",
    1_000_000_000_000: "tiriliyan ɗaya",
}


@pytest.mark.parametrize(("value", "words"), CASES.items())
def test_generation_and_parsing(value, words):
    assert generate(value) == words
    assert hausa_words_to_number(words) == value
    assert parse(words) == value


@pytest.mark.parametrize("alias", ["tasa in", "tasa’in", "tasain", "tisa'in", "casa'in"])
def test_ninety_aliases(alias):
    assert normalize_hausa_text(alias) == "tasa'in"
    assert hausa_words_to_number(alias) == 90


def test_short_teens_and_ascii_aliases():
    assert hausa_words_to_number("sha daya") == 11
    assert hausa_words_to_number("dari biyu da hamsin") == 250


@pytest.mark.parametrize("text", ["", "kalma", "ɗaya biyu", "ashirin da", "💥"])
def test_invalid_numbers_are_rejected(text):
    assert parse(text) is None
