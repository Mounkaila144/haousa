import pytest
from hausa_numbers import (
    DomainError,
    evaluate,
    parse_expression,
    parse_expression_detailed,
    parse_hausa_operation,
    render_result,
)


@pytest.mark.parametrize(
    ("text", "left", "symbol", "right", "result"),
    [
        # Montants en francs CFA : sous le millier un mot vaut 5 F par unité
        # numérique (`ashirin da uku` = 23 × 5 = 115 F).
        ("ashirin da uku a ƙara goma sha biyar", 115, "+", 75, 190),
        ("ɗari biyar a hidda ɗari biyu", 2500, "-", 1000, 1500),
        ("tasa'in da tara a kara daya", 495, "+", 5, 500),
        # `jika biyu` (2 000 F) et `ɗari biyu` (200 × 5) sont deux façons de
        # dire des montants du même système : la soustraction les mêle sans
        # conversion.
        ("jika biyu a hidda ɗari biyu", 2000, "-", 1000, 1000),
        # À droite de `sau` et de `raba`, le nombre compte des fois : c'est un
        # multiplicateur, pas un montant (`biyar` = 5, non 25 F).
        ("goma sau biyar", 50, "*", 5, 250),
        ("ɗari ɗaya a raba chi sau biyu", 500, "/", 2, 250),
        ("ɗari sau ɗari", 500, "*", 100, 50_000),
    ],
)
def test_operations(text, left, symbol, right, result):
    operation = parse_expression(text)
    assert operation is not None
    assert (operation.left, operation.symbol, operation.right) == (left, symbol, right)
    evaluated = evaluate(operation)
    assert evaluated.value == result
    assert render_result(evaluated)


def test_central_parser_keeps_trace():
    parsed = parse_hausa_operation("ashirin da uku a kara goma sha biyar")
    assert parsed.normalized_text == "ashirin da uku a ƙara goma sha biyar"
    assert parsed.operator == "add"
    # Valeurs en francs CFA : 23 × 5 et 15 × 5.
    assert (parsed.left_value, parsed.right_value) == (115, 75)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "EMPTY_INPUT"),
        ("ɗaya biyu", "MISSING_OPERATOR"),
        ("ɗaya a ƙara", "MISSING_RIGHT_OPERAND"),
        ("ɗaya a ƙara biyu sau uku", "MULTIPLE_OPERATORS"),
        ("kalma a ƙara biyu", "INVALID_OPERAND"),
    ],
)
def test_operation_errors(text, code):
    assert parse_expression_detailed(text).error_code == code


def test_division_by_zero():
    expression = parse_expression("goma kashi sifili")
    assert expression is not None
    with pytest.raises(DomainError, match="sifili") as caught:
        evaluate(expression)
    assert caught.value.code == "DIVISION_BY_ZERO"
