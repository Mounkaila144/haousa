"""Analyse et evaluation d'operations arithmetiques dites en hausa."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import DomainError, ExpressionParseError
from .generator import generate
from .loader import load_lexicon
from .money import (
    DEFAULT_THOUSAND_NAMING,
    MAX_MONEY_CFA,
    UNIT_CFA,
    ThousandNaming,
    format_money,
    parse_money,
    parse_scalar,
)
from .normalizer import normalize_hausa_text

#: Opérateurs dont l'opérande droit est un **multiplicateur**, pas un montant.
#:
#: `dari sau dari` vaut 500 F × 100, jamais 500 × 500 : à droite de `sau` le
#: nombre compte des fois, pas des francs (cf. §9). Additionner ou soustraire,
#: à l'inverse, met en jeu deux montants.
_SCALAR_RIGHT_OPERATORS = frozenset({"multiply", "divide"})

HAUSA_OPERATORS = {
    "add": ("a ƙara", "ƙara", "a kara", "kara"),
    "subtract": ("a hidda", "hidda", "debe", "a debe"),
    "multiply": ("sau",),
    "divide": ("a raba chi sau", "raba chi sau", "kashi"),
}
_SYMBOLS = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}
_CANONICAL = {"+": "a ƙara", "-": "a hidda", "*": "sau", "/": "a raba chi sau"}


@dataclass(frozen=True, slots=True)
class Expression:
    left: int
    symbol: str
    right: int

    @property
    def operator_name(self) -> str | None:
        return next((name for name, symbol in _SYMBOLS.items() if symbol == self.symbol), None)


@dataclass(frozen=True, slots=True)
class ExpressionResult:
    expression: Expression
    value: int
    remainder: int = 0

    @property
    def exact(self) -> bool:
        return self.remainder == 0


@dataclass(frozen=True, slots=True)
class ExpressionParseResult:
    expression: Expression | None
    accepted: bool = False
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedOperation:
    original_text: str
    normalized_text: str
    left_text: str
    left_value: int
    operator: str
    right_text: str
    right_value: int


def _operator_surfaces() -> list[tuple[tuple[str, ...], str, str]]:
    surfaces: list[tuple[tuple[str, ...], str, str]] = []
    for name, aliases in HAUSA_OPERATORS.items():
        for alias in aliases:
            normalized = tuple(normalize_hausa_text(alias).split())
            surfaces.append((normalized, name, _SYMBOLS[name]))
    return sorted(set(surfaces), key=lambda item: len(item[0]), reverse=True)


def parse_hausa_operation(text: str) -> ParsedOperation:
    if not isinstance(text, str) or not text.strip():
        raise ExpressionParseError("Babu aiki.", code="EMPTY_INPUT")
    normalized = normalize_hausa_text(text)
    tokens = normalized.split()
    matches: list[tuple[int, int, str, str]] = []
    for index in range(len(tokens)):
        for surface, name, symbol in _operator_surfaces():
            if tuple(tokens[index : index + len(surface)]) == surface:
                matches.append((index, index + len(surface), name, symbol))
                break
    # Retirer les correspondances incluses dans une locution plus longue.
    maximal = [
        match
        for match in matches
        if not any(
            other[0] <= match[0]
            and match[1] <= other[1]
            and (other[0], other[1]) != (match[0], match[1])
            for other in matches
        )
    ]
    if not maximal:
        raise ExpressionParseError("Ba a gane alamar lissafi ba.", code="MISSING_OPERATOR")
    if len(maximal) != 1:
        raise ExpressionParseError(
            "Akwai alamomin lissafi fiye da daya.", code="MULTIPLE_OPERATORS"
        )
    start, end, name, _symbol = maximal[0]
    if start == 0:
        raise ExpressionParseError("Lambar hagu ta bace.", code="MISSING_LEFT_OPERAND")
    if end == len(tokens):
        raise ExpressionParseError("Lambar dama ta bace.", code="MISSING_RIGHT_OPERAND")
    left_text, right_text = " ".join(tokens[:start]), " ".join(tokens[end:])
    # L'opérande gauche est toujours un montant. Le droit dépend de l'opérateur
    # : un multiplicateur pour `sau`/`raba`, un montant pour `ƙara`/`hidda`.
    left = parse_money(left_text)
    if name in _SCALAR_RIGHT_OPERATORS:
        right = parse_scalar(right_text)
    else:
        right = parse_money(right_text)
    if left is None or right is None:
        raise ExpressionParseError("Ba a gane lambar ba.", code="INVALID_OPERAND")
    return ParsedOperation(text, normalized, left_text, left, name, right_text, right)


def parse_expression_detailed(text: str) -> ExpressionParseResult:
    try:
        parsed = parse_hausa_operation(text)
    except (ExpressionParseError, TypeError) as exc:
        return ExpressionParseResult(None, error_code=getattr(exc, "code", "PARSE_ERROR"))
    return ExpressionParseResult(
        Expression(parsed.left_value, _SYMBOLS[parsed.operator], parsed.right_value),
        accepted=True,
    )


def parse_expression(text: str) -> Expression | None:
    return parse_expression_detailed(text).expression


def evaluate(expression: Expression) -> ExpressionResult:
    left, right = expression.left, expression.right
    if expression.symbol == "+":
        value, remainder = left + right, 0
    elif expression.symbol == "-":
        value, remainder = left - right, 0
    elif expression.symbol == "*":
        value, remainder = left * right, 0
    elif expression.symbol == "/":
        if right == 0:
            raise DomainError("Ba za a raba da sifili ba.", code="DIVISION_BY_ZERO")
        value, remainder = divmod(left, right)
    else:
        raise DomainError("Ba a gane alamar lissafi ba.", code="UNKNOWN_OPERATOR")
    if value < 0:
        raise DomainError("Sakamako mara kyau baya cikin iyaka.", code="NEGATIVE_RESULT")
    if value > MAX_MONEY_CFA:
        raise DomainError("Sakamako ya wuce iyaka.", code="RESULT_OUT_OF_RANGE")
    # L'unité de compte est de 5 F : diviser peut tomber entre deux montants
    # (115 F ÷ 5 = 23 F, qui ne se dit pas). On refuse alors explicitement —
    # arrondir en silence ferait rendre la monnaie de travers (§29/§30).
    if (value % UNIT_CFA) or (remainder % UNIT_CFA):
        raise DomainError(
            "Sakamako ba shi da siga a kuɗi.",
            code="RESULT_NOT_EXPRESSIBLE",
        )
    return ExpressionResult(expression, value, remainder)


def evaluate_text(text: str) -> ExpressionResult | None:
    expression = parse_expression(text)
    return evaluate(expression) if expression is not None else None


def render_expression(
    expression: Expression,
    naming: ThousandNaming = DEFAULT_THOUSAND_NAMING,
) -> str:
    """Relit l'opération entendue, chaque opérande dans **sa** lecture.

    Le multiplicateur de `sau` se relit comme un nombre (`ɗari` = 100), le
    reste comme des montants (`ɗari` = 500 F). Les rendre tous les deux en
    montants ferait relire « dari sau dari » comme 500 F × 500 F.
    """
    left = format_money(expression.left, naming)
    if expression.operator_name in _SCALAR_RIGHT_OPERATORS:
        right = generate(expression.right)
    else:
        right = format_money(expression.right, naming)
    return f"{left} {_CANONICAL[expression.symbol]} {right}"


def to_spoken(text: str) -> str:
    """Réécrit un texte canonique en sa forme **à prononcer**.

    Certaines formes écrites ne se lisent pas telles quelles par la synthèse
    vocale embarquée : `jikka` (1 000) sort en « jika », la gémination étant
    perdue. Le lexique porte alors une forme parlée (`jik'ka`) qui rétablit la
    coupe syllabique attendue.

    C'est une transformation de **sortie** uniquement : elle n'est jamais
    appliquée avant une analyse, sans quoi la forme parlée deviendrait une
    entrée acceptée et le lexique aurait deux formes canoniques concurrentes.
    Substitution sur frontières de mots, jamais de rapprochement flou.
    """
    if not isinstance(text, str) or not text.strip():
        return text
    forms = load_lexicon().spoken_forms
    if not forms:
        return text
    return " ".join(forms.get(word, word) for word in text.split())


def render_spoken(
    expression: Expression,
    naming: ThousandNaming = DEFAULT_THOUSAND_NAMING,
) -> str:
    """Forme **prononçable** de l'opération (cf. ``to_spoken``)."""
    return to_spoken(render_expression(expression, naming))


def render_result(
    result: ExpressionResult,
    naming: ThousandNaming = DEFAULT_THOUSAND_NAMING,
) -> str:
    """Résultat en francs CFA, dit avec l'appellation choisie du millier.

    Le reste d'une division est lui aussi un montant : diviser 1 500 F en deux
    laisse 750 F, pas « 150 ».
    """
    value = format_money(result.value, naming)
    if result.remainder:
        return f"{value} saura {format_money(result.remainder, naming)}"
    return value


def supported_operators() -> dict[str, str]:
    return {symbol: name for name, symbol in _SYMBOLS.items()}


__all__ = [
    "HAUSA_OPERATORS",
    "Expression",
    "ExpressionParseResult",
    "ExpressionResult",
    "ParsedOperation",
    "evaluate",
    "evaluate_text",
    "parse_expression",
    "parse_expression_detailed",
    "parse_hausa_operation",
    "render_expression",
    "render_result",
    "render_spoken",
    "supported_operators",
    "to_spoken",
]
