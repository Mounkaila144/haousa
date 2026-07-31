"""Conversion deterministe des entiers en mots hausa canoniques."""

from __future__ import annotations

from .exceptions import OutOfRangeError

MIN_VALUE = 0
MAX_VALUE = 999_999_999_999_999

UNITS = {
    1: "ɗaya",
    2: "biyu",
    3: "uku",
    4: "huɗu",
    5: "biyar",
    6: "shida",
    7: "bakwai",
    8: "takwas",
    9: "tara",
}
TENS = {
    10: "goma",
    20: "ashirin",
    30: "talatin",
    40: "arba'in",
    50: "hamsin",
    60: "sittin",
    70: "saba'in",
    80: "tamanin",
    90: "tasa'in",
}
SCALES = (
    (1_000_000_000_000, "tiriliyan"),
    (1_000_000_000, "biliyan"),
    (1_000_000, "miliyan"),
    (1_000, "dubu"),
)


def _below_hundred(value: int) -> str:
    if value < 10:
        return UNITS[value]
    if value in TENS:
        return TENS[value]
    if value < 20:
        return f"goma sha {UNITS[value - 10]}"
    tens, unit = divmod(value, 10)
    return f"{TENS[tens * 10]} da {UNITS[unit]}"


def _below_thousand(value: int) -> str:
    if value < 100:
        return _below_hundred(value)
    hundreds, remainder = divmod(value, 100)
    head = "ɗari" if hundreds == 1 else f"ɗari {UNITS[hundreds]}"
    return head if remainder == 0 else f"{head} da {_below_hundred(remainder)}"


def _positive(value: int) -> str:
    if value < 1_000:
        return _below_thousand(value)
    for scale_value, scale_word in SCALES:
        if value >= scale_value:
            multiplier, remainder = divmod(value, scale_value)
            if scale_word == "dubu" and multiplier == 1 and remainder == 0:
                head = "dubu"
            else:
                head = f"{scale_word} {_positive(multiplier)}"
            return head if remainder == 0 else f"{head} da {_positive(remainder)}"
    raise AssertionError("unreachable")


def generate(value: int) -> str:
    """Retourne la forme canonique hausa de ``value``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("generate() attend un entier.")
    if not MIN_VALUE <= value <= MAX_VALUE:
        raise OutOfRangeError(f"Nombre hors plage : {value}.")
    return "sifili" if value == 0 else _positive(value)


def generate_combined(value: int) -> str:
    """Alias historique : le hausa n'emploie pas une forme d'unite distincte."""
    return generate(value)


number_to_hausa = generate

__all__ = [
    "MAX_VALUE",
    "MIN_VALUE",
    "SCALES",
    "TENS",
    "UNITS",
    "generate",
    "generate_combined",
    "number_to_hausa",
]
