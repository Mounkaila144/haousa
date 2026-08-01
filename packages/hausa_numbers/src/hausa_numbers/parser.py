"""Parseur deterministe de nombres hausa, sans traduction intermediaire."""

from __future__ import annotations

from dataclasses import dataclass, field

from .exceptions import ParseError
from .generator import HUNDRED, MAX_VALUE, SCALES, TENS, UNITS
from .normalizer import normalize_hausa_text

_UNIT_VALUES = {word: value for value, word in UNITS.items()}
_TENS_VALUES = {word: value for value, word in TENS.items()}
#: Échelles du lexique, de la plus grande à la plus petite, centaine comprise.
#: Dérivé du générateur — donc du lexique — pour que le parseur ne puisse pas
#: connaître un mot d'échelle que le décodeur ignore, ou l'inverse.
_SCALES = tuple((word, value) for value, word in SCALES) + ((HUNDRED, 100),)


@dataclass(frozen=True)
class ParseCandidate:
    value: int
    confidence: float = 1.0
    source: str = "grammar"


@dataclass(frozen=True)
class ParseResult:
    best: ParseCandidate | None
    alternatives: list[ParseCandidate] = field(default_factory=list)
    accepted: bool = False
    error_code: str | None = None


def _below_hundred(tokens: list[str]) -> int:
    if len(tokens) == 1:
        if tokens[0] in _UNIT_VALUES:
            return _UNIT_VALUES[tokens[0]]
        if tokens[0] in _TENS_VALUES:
            return _TENS_VALUES[tokens[0]]
    if len(tokens) == 2 and tokens[0] == "sha" and tokens[1] in _UNIT_VALUES:
        return 10 + _UNIT_VALUES[tokens[1]]
    if len(tokens) == 3:
        if tokens[:2] == ["goma", "sha"] and tokens[2] in _UNIT_VALUES:
            return 10 + _UNIT_VALUES[tokens[2]]
        if tokens[0] in _TENS_VALUES and _TENS_VALUES[tokens[0]] >= 20:
            if tokens[1] == "da" and tokens[2] in _UNIT_VALUES:
                return _TENS_VALUES[tokens[0]] + _UNIT_VALUES[tokens[2]]
    raise ParseError("Tsarin lambar Hausa ba daidai ba.", code="INVALID_STRUCTURE")


def _parse_level(tokens: list[str], level: int = 0) -> int:
    if not tokens:
        raise ParseError("Babu lamba.", code="EMPTY_INPUT")
    if level >= len(_SCALES):
        return _below_hundred(tokens)

    word, factor = _SCALES[level]
    if tokens[0] != word:
        return _parse_level(tokens, level + 1)

    rest = tokens[1:]
    # Priorite au multiplicateur complet. En hausa, le meme ``da`` compose
    # aussi ce multiplicateur (par ex. ``dubu ɗari uku da arba'in da biyar``
    # = 345 000). Le couper trop tot fabriquerait a tort 300 045.
    if rest:
        try:
            multiplier = _parse_level(rest, level + 1)
        except ParseError:
            pass
        else:
            if 0 < multiplier < 1_000:
                return multiplier * factor

    # Un 'da' interne au multiplicateur (ashirin da biyar) ne doit pas etre
    # confondu avec le separateur du reste. On essaie chaque frontiere et ne
    # conserve qu'une decomposition grammaticale valide.
    solutions: set[int] = set()
    for index in range(len(rest) - 1, -1, -1):
        if rest[index] != "da":
            continue
        left, right = rest[:index], rest[index + 1 :]
        if not right:
            continue
        try:
            multiplier = 1 if not left else _parse_level(left, level + 1)
            remainder = _parse_level(right, level + 1)
        except ParseError:
            continue
        if 0 < multiplier < 1_000 and 0 < remainder < factor:
            solutions.add(multiplier * factor + remainder)

    if not rest:
        solutions.add(factor)

    if len(solutions) != 1:
        code = "AMBIGUOUS_NUMBER" if len(solutions) > 1 else "INVALID_STRUCTURE"
        raise ParseError("Tsarin lambar Hausa ba daidai ba.", code=code)
    return solutions.pop()


def _parse_or_raise(text: str) -> int:
    normalized = normalize_hausa_text(text)
    if not normalized:
        raise ParseError("Babu rubutu.", code="EMPTY_INPUT")
    if normalized == "sifili":
        return 0
    if normalized.isascii() and normalized.isdigit():
        value = int(normalized)
    else:
        value = _parse_level(normalized.split())
    if not 0 <= value <= MAX_VALUE:
        raise ParseError("Lambar ta wuce iyaka.", code="OUT_OF_RANGE")
    return value


def hausa_words_to_number(text: str) -> int:
    """Analyse stricte : leve ``ParseError`` au lieu de deviner."""
    return _parse_or_raise(text)


def parse(text: str) -> int | None:
    """Interface historique tolerante utilisee par l'API."""
    try:
        return _parse_or_raise(text)
    except (ParseError, TypeError):
        return None


def parse_detailed(text: str) -> ParseResult:
    try:
        value = _parse_or_raise(text)
    except (ParseError, TypeError) as exc:
        return ParseResult(None, accepted=False, error_code=getattr(exc, "code", "PARSE_ERROR"))
    return ParseResult(ParseCandidate(value), accepted=True)


__all__ = [
    "ParseCandidate",
    "ParseResult",
    "hausa_words_to_number",
    "parse",
    "parse_detailed",
]
