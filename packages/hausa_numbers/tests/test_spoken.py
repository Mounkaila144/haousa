"""Formes de prononciation : ce que la synthèse vocale doit lire.

La synthèse embarquée (Piper, ``phoneme_type: text``) lit des **caractères**,
pas des phonèmes. Une gémination écrite ``kk`` lui échappe : ``jikka`` sort en
« jika ». Le lexique porte donc une forme parlée distincte de la forme écrite.
"""

from __future__ import annotations

import hausa_numbers
import pytest


def test_lexicon_exposes_spoken_forms():
    assert hausa_numbers.load_lexicon().spoken_forms.get("jikka") == "jik'ka"


@pytest.mark.parametrize(
    ("written", "spoken"),
    [
        ("jikka", "jik'ka"),
        ("jikka biyar", "jik'ka biyar"),
        ("jikka goma sha ɗaya", "jik'ka goma sha ɗaya"),
        ("jikka biyar a hidda goma", "jik'ka biyar a hidda goma"),
    ],
)
def test_thousand_is_spoken_with_a_syllable_break(written, spoken):
    assert hausa_numbers.to_spoken(written) == spoken


@pytest.mark.parametrize(
    "written",
    ["ɗari uku da hamsin", "arba'in a ƙara uku", "goma sha ɗaya", "sifili", ""],
)
def test_text_without_a_spoken_form_is_left_untouched(written):
    assert hausa_numbers.to_spoken(written) == written


def test_spoken_form_is_never_an_accepted_input():
    """La forme parlée ne doit pas devenir une deuxième forme canonique.

    Si ``jik'ka`` était analysable, le lexique aurait deux écritures concurrentes
    pour 1 000 et le corpus d'entraînement se retrouverait avec les deux.
    """
    assert hausa_numbers.parse("jik'ka") is None
    assert hausa_numbers.parse("jikka") == 1_000


def test_render_spoken_differs_from_written_only_when_needed():
    with_thousand = hausa_numbers.parse_expression("jikka biyar a hidda goma")
    assert hausa_numbers.render_spoken(with_thousand) != hausa_numbers.render_expression(
        with_thousand
    )

    without = hausa_numbers.parse_expression("ɗari uku da hamsin sau biyu")
    assert hausa_numbers.render_spoken(without) == hausa_numbers.render_expression(without)


def test_spoken_form_only_uses_characters_the_voice_model_knows():
    """L'apostrophe est un token du modèle (elle sert déjà à ``arba'in``).

    Une forme parlée employant un caractère absent du vocabulaire serait
    silencieusement ignorée par la synthèse.
    """
    known = set("abcdefghijklmnoprstuwyzɓɗƙƴpqvx '-,.:;?!")
    for spoken in hausa_numbers.load_lexicon().spoken_forms.values():
        assert set(spoken) <= known, spoken
