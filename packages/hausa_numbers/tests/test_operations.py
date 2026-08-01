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
        ("ashirin da uku a ƙara goma sha biyar", 23, "+", 15, 38),
        ("ɗari biyar a hidda ɗari biyu", 500, "-", 200, 300),
        ("goma sau biyar", 10, "*", 5, 50),
        ("ɗari ɗaya a raba chi sau biyu", 100, "/", 2, 50),
        ("tasa'in da tara a kara daya", 99, "+", 1, 100),
        ("jika biyu a hidda ɗari biyar", 2000, "-", 500, 1500),
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
    assert (parsed.left_value, parsed.right_value) == (23, 15)


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
