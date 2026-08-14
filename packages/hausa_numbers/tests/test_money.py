"""Système monétaire hausa (franc CFA) — montants, scalaires, restitution.

La calculatrice sert à compter de l'argent : un mot y vaut 5 F par unité
numérique sous le millier, et le millier est une unité de 1 000 F à part.

Ces tests fixent surtout la frontière que le moteur ne doit jamais franchir :
``ɗari`` vaut 500 F comme **montant** et 100 comme **multiplicateur**. Les
confondre ferait rendre 250 000 F là où il faut 50 000 F.
"""

from __future__ import annotations

import pytest
from hausa_numbers import (
    UNIT_CFA,
    DomainError,
    OutOfRangeError,
    UnresolvedFormError,
    evaluate,
    format_money,
    parse_expression,
    parse_money,
    parse_scalar,
    render_expression,
    render_result,
)


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("sifili", 0),
        ("daya", 5),
        ("biyu", 10),
        ("uku", 15),
        ("hudu", 20),
        ("biyar", 25),
        ("shida", 30),
        ("bakwai", 35),
        ("takwas", 40),
        ("tara", 45),
        ("goma", 50),
        ("ashirin", 100),
        ("talatin", 150),
        ("arba'in", 200),
        ("hamsin", 250),
        ("sittin", 300),
        ("saba'in", 350),
        ("tamanin", 400),
        ("tasa'in", 450),
        ("dari", 500),
    ],
)
def test_base_amounts_are_five_francs_per_unit(text: str, amount: int) -> None:
    assert parse_money(text) == amount


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("goma sha daya", 55),
        ("goma sha biyu", 60),
        ("goma sha biyar", 75),
        ("ashirin da daya", 105),
        ("ashirin da biyu", 110),
        ("ashirin da biyar", 125),
        ("talatin da biyar", 175),
        ("hamsin da biyar", 275),
        ("tamanin da biyu", 410),
        ("tasa'in da tara", 495),
        ("dari da daya", 505),
        ("dari da biyu", 510),
        ("dari da goma", 550),
        ("dari da ashirin", 600),
        ("dari da hamsin", 750),
    ],
)
def test_composed_amounts_are_built_not_tabulated(text: str, amount: int) -> None:
    """Les composés sont dérivés par la grammaire, pas listés un à un."""
    assert parse_money(text) == amount


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("dari biyu", 1_000),
        ("dari uku", 1_500),
        ("dari hudu", 2_000),
        ("dari biyar", 2_500),
        ("dari shida", 3_000),
        ("dari takwas", 4_000),
        ("dari goma", 5_000),
    ],
)
def test_dari_scales_by_five_hundred(text: str, amount: int) -> None:
    assert parse_money(text) == amount


@pytest.mark.parametrize("word", ["jika", "jikka", "dubu", "dari biyu"])
def test_all_thousand_synonyms_collapse_to_one_value(word: str) -> None:
    """`jika`, `jikka`, `dubu` et `dari biyu` sont un seul concept interne."""
    assert parse_money(word) == 1_000


@pytest.mark.parametrize(
    ("suffix", "amount"),
    [
        ("", 1_000),
        (" biyu", 2_000),
        (" uku", 3_000),
        (" hudu", 4_000),
        (" biyar", 5_000),
        (" goma", 10_000),
        (" ashirin", 20_000),
        (" hamsin", 50_000),
        (" dari", 100_000),
    ],
)
def test_jika_and_dubu_behave_identically(suffix: str, amount: int) -> None:
    """Aucune arithmétique propre à l'un ou à l'autre (règle 6)."""
    assert parse_money(f"jika{suffix}") == amount
    assert parse_money(f"dubu{suffix}") == amount


@pytest.mark.parametrize(
    ("text", "scalar"),
    [
        ("daya", 1),
        ("biyu", 2),
        ("biyar", 5),
        ("goma", 10),
        ("ashirin", 20),
        ("hamsin", 50),
        ("dari", 100),
    ],
)
def test_scalar_keeps_the_plain_numeral_value(text: str, scalar: int) -> None:
    assert parse_scalar(text) == scalar


def test_dari_is_five_hundred_as_amount_and_hundred_as_multiplier() -> None:
    """La règle qui distingue cette calculatrice d'un moteur numérique."""
    assert parse_money("dari") == 500
    assert parse_scalar("dari") == 100


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("dari a kara dari", 1_000),
        ("jika a hidda dari", 500),
        ("dubu a hidda dari", 500),
        ("dari sau biyu", 1_000),
        ("dari sau goma", 5_000),
        ("dari sau dari", 50_000),
        ("ashirin sau biyar", 500),
        ("jika sau goma", 10_000),
        ("dubu sau goma", 10_000),
        ("jika a raba chi sau biyu", 500),
        ("dubu a raba chi sau biyu", 500),
        ("dari a raba chi sau biyar", 100),
        ("jika goma a raba chi sau biyu", 5_000),
    ],
)
def test_operations_use_money_left_and_scalar_right(text: str, expected: int) -> None:
    expression = parse_expression(text)
    assert expression is not None, text
    assert evaluate(expression).value == expected


def test_multiplying_two_amounts_is_never_money_times_money() -> None:
    """`dari sau dari` = 500 F × 100, jamais 500 × 500 (règle 9)."""
    expression = parse_expression("dari sau dari")
    assert expression is not None
    assert (expression.left, expression.right) == (500, 100)
    assert evaluate(expression).value == 50_000


@pytest.mark.parametrize(
    ("amount", "jika_form", "dubu_form"),
    [
        (0, "sifili", "sifili"),
        (5, "ɗaya", "ɗaya"),
        (50, "goma", "goma"),
        (100, "ashirin", "ashirin"),
        (250, "hamsin", "hamsin"),
        (495, "tasa'in da tara", "tasa'in da tara"),
        (500, "ɗari", "ɗari"),
        (550, "ɗari da goma", "ɗari da goma"),
        (1_000, "jikka", "dubu"),
        (2_000, "jikka biyu", "dubu biyu"),
        (5_000, "jikka biyar", "dubu biyar"),
        (10_000, "jikka goma", "dubu goma"),
        (50_000, "jikka hamsin", "dubu hamsin"),
        (100_000, "jikka ɗari", "dubu ɗari"),
    ],
)
def test_preference_only_changes_the_thousand_word(
    amount: int, jika_form: str, dubu_form: str
) -> None:
    assert format_money(amount, "jika") == jika_form
    assert format_money(amount, "dubu") == dubu_form


@pytest.mark.parametrize("amount", [0, 5, 495, 500, 1_000, 1_500, 2_500, 5_500, 50_000, 999_995])
def test_rendered_amount_parses_back_to_itself(amount: int) -> None:
    """Aller-retour : ce que l'application dit, elle sait le réentendre."""
    for naming in ("jika", "dubu"):
        assert parse_money(format_money(amount, naming)) == amount


def test_preference_never_changes_the_computed_value() -> None:
    expression = parse_expression("jika goma a raba chi sau biyu")
    assert expression is not None
    result = evaluate(expression)
    assert result.value == 5_000
    assert render_result(result, "jika") == "jikka biyar"
    assert render_result(result, "dubu") == "dubu biyar"


def test_replayed_operation_keeps_each_operand_in_its_own_reading() -> None:
    """Relire l'opération ne doit pas transformer le multiplicateur en montant."""
    expression = parse_expression("dari sau dari")
    assert expression is not None
    # 500 F se relit `ɗari` ; le multiplicateur 100 se relit `ɗari` aussi, mais
    # parce qu'il vaut cent — et non parce qu'il vaudrait 500 F.
    assert render_expression(expression) == "ɗari sau ɗari"


def test_division_remainder_is_an_amount_not_a_numeral() -> None:
    expression = parse_expression("dari uku a raba chi sau biyu")
    assert expression is not None
    result = evaluate(expression)
    assert (result.value, result.remainder) == (750, 0)
    assert render_result(result) == "ɗari da hamsin"


def test_unparseable_amount_is_refused_never_guessed() -> None:
    """Une calculatrice d'argent préfère se taire (règle §30)."""
    assert parse_money("kalma") is None
    assert parse_money("") is None
    assert parse_money("dari dari dari") is None


def test_amount_off_the_five_franc_unit_has_no_spoken_form() -> None:
    # `UnresolvedFormError` et non `OutOfRangeError` : 7 F est dans la plage,
    # c'est sa FORME qui n'existe pas. L'API distingue les deux (422 vs 400).
    with pytest.raises(UnresolvedFormError):
        format_money(7)


def test_amount_beyond_the_range_is_out_of_range() -> None:
    from hausa_numbers import MAX_MONEY_CFA

    with pytest.raises(OutOfRangeError):
        format_money(MAX_MONEY_CFA + UNIT_CFA)


@pytest.mark.parametrize(
    ("amount", "forme"),
    [
        (1_000_000, "miliyan"),
        (2_000_000, "miliyan biyu"),
        (10_000_000, "miliyan goma"),
        (50_000_000, "miliyan hamsin"),
        (1_001_000, "miliyan da jikka"),
        (1_500_000, "miliyan da jikka ɗari biyar"),
    ],
)
def test_millions_have_their_own_scale(amount: int, forme: str) -> None:
    """Au-delà de 999 995 F, le millier ne suffit plus.

    Son multiplicateur doit rester sous 1 000, sans quoi la forme produite
    réemploierait `jikka` dans son propre multiplicateur. `miliyan` prend le
    relais, sur le même schéma d'un cran supérieur.
    """
    assert format_money(amount) == forme
    assert parse_money(forme) == amount


def test_a_calculation_can_now_cross_the_million() -> None:
    expression = parse_expression("jika dari sau goma")
    assert expression is not None
    assert evaluate(expression).value == 1_000_000


def test_no_scale_word_is_ever_nested_in_its_own_multiplier() -> None:
    """Régression : `format_money` produisait `jikka jikka ɗaya…` au-delà de la
    borne, une forme absurde que `parse_money` refusait ensuite."""
    from hausa_numbers import MAX_MONEY_CFA

    for amount in (999_995, 1_000_000, MAX_MONEY_CFA):
        mots = format_money(amount).split()
        assert mots.count("jikka") <= 1
        assert mots.count("miliyan") <= 1
        assert parse_money(format_money(amount)) == amount


def test_negative_result_is_refused() -> None:
    expression = parse_expression("dari a hidda jika")
    assert expression is not None
    with pytest.raises(DomainError) as caught:
        evaluate(expression)
    assert caught.value.code == "NEGATIVE_RESULT"


def test_division_landing_between_two_amounts_is_refused() -> None:
    """115 F ÷ 5 = 23 F : aucun montant ne se dit ainsi, on refuse."""
    expression = parse_expression("ashirin da uku a raba chi sau biyar")
    assert expression is not None
    assert expression.left == 115
    with pytest.raises(DomainError) as caught:
        evaluate(expression)
    assert caught.value.code == "RESULT_NOT_EXPRESSIBLE"


def test_division_that_lands_on_the_unit_is_allowed() -> None:
    expression = parse_expression("dari a raba chi sau biyar")
    assert expression is not None
    assert evaluate(expression).value == 100


def test_the_largest_amount_never_nests_the_thousand_word() -> None:
    """Régression : au-delà de la borne, la forme réemployait `jikka` en son
    propre multiplicateur (`jikka jikka ɗaya…`), et n'était plus réanalysable.
    """
    from hausa_numbers import MAX_MONEY_CFA

    rendered = format_money(MAX_MONEY_CFA)
    assert rendered.split().count("jikka") == 1
    assert parse_money(rendered) == MAX_MONEY_CFA

    with pytest.raises(OutOfRangeError):
        format_money(MAX_MONEY_CFA + UNIT_CFA)
