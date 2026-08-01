"""Conversion deterministe des entiers en mots hausa canoniques."""

from __future__ import annotations

from .exceptions import OutOfRangeError
from .loader import load_lexicon

MIN_VALUE = 0
MAX_VALUE = 999_999_999_999_999


def _from_lexicon() -> tuple[dict[int, str], dict[int, str], tuple[tuple[int, str], ...], str]:
    """Formes canoniques lues du **lexique**, jamais recopiées ici.

    `dubu` était écrit en dur dans ce module, dans le parseur et dans la
    grammaire, en plus du lexique : quatre sources de vérité pour un même mot.
    Corriger 1 000 (`dubu` → `jika`) demandait donc quatre modifications
    cohérentes, et une seule oubliée suffisait à faire diverger le décodeur du
    parseur — tout serait devenu `repeat` sans la moindre erreur visible.
    """
    lexicon = load_lexicon()
    units = {unit.value: unit.isolated for unit in lexicon.units.values()}
    tens = {value: term.canonical for value, term in lexicon.tens.items() if term.canonical}
    scales = tuple(
        sorted(
            (
                (scale.value, scale.canonical)
                for scale in lexicon.scales.values()
                if scale.canonical and scale.value >= 1_000
            ),
            reverse=True,
        )
    )
    hundred = lexicon.scales["hundred"].canonical or "ɗari"
    return units, tens, scales, hundred


UNITS, TENS, SCALES, HUNDRED = _from_lexicon()

#: Échelle de 1 000, seule à avoir une forme courte sans multiplicateur.
THOUSAND_WORD = next((word for value, word in SCALES if value == 1_000), "")


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
    head = HUNDRED if hundreds == 1 else f"{HUNDRED} {UNITS[hundreds]}"
    return head if remainder == 0 else f"{head} da {_below_hundred(remainder)}"


def _positive(value: int) -> str:
    if value < 1_000:
        return _below_thousand(value)
    for scale_value, scale_word in SCALES:
        if value >= scale_value:
            multiplier, remainder = divmod(value, scale_value)
            if scale_word == THOUSAND_WORD and multiplier == 1 and remainder == 0:
                head = THOUSAND_WORD
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
    "HUNDRED",
    "MAX_VALUE",
    "MIN_VALUE",
    "SCALES",
    "TENS",
    "THOUSAND_WORD",
    "UNITS",
    "generate",
    "generate_combined",
    "number_to_hausa",
]
