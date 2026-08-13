"""Formes de prononciation : ce que la synthèse vocale doit lire.

Le lexique peut porter, pour un mot donné, une écriture destinée à la seule
synthèse — distincte de la forme canonique. Le mécanisme existe ; la table est
aujourd'hui **vide**, et ces tests fixent pourquoi.

Elle a porté ``jikka -> "jikk ka"`` tant que la voix était un modèle générique
lisant des caractères sans avoir jamais entendu de hausa : la gémination ``kk``
lui échappait et ``jikka`` sortait en « jika ». La coupe syllabique était donc
écrite à la main dans le texte.

La voix est désormais entraînée sur des enregistrements où ``jikka`` est
réellement prononcé. Lui envoyer ``jikk ka`` lui présenterait une graphie
absente de son corpus — ce serait dégrader la prononciation, pas l'améliorer.
"""

from __future__ import annotations

import hausa_numbers
import pytest


def test_no_spoken_form_is_declared_today():
    """La table est vide, et c'est le comportement attendu.

    Toute entrée ajoutée ici doit d'abord exister dans le corpus
    d'entraînement, sans quoi elle serait prononcée au hasard.
    """
    assert hausa_numbers.load_lexicon().spoken_forms == {}


@pytest.mark.parametrize(
    "written",
    [
        "jikka",
        "jikka biyar",
        "jikka goma sha ɗaya",
        "jikka biyar a hidda goma",
        "ɗari uku da hamsin",
        "arba'in a ƙara uku",
        "sifili",
        "",
    ],
)
def test_text_is_left_untouched_while_the_table_is_empty(written: str) -> None:
    assert hausa_numbers.to_spoken(written) == written


def test_the_written_form_is_the_one_spoken() -> None:
    """`jikka` part tel quel à la synthèse : c'est ce que la voix a appris."""
    assert hausa_numbers.format_money(1_000) == "jikka"
    assert hausa_numbers.to_spoken("jikka") == "jikka"


def test_the_substitution_mechanism_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le mécanisme reste opérant : c'est la table qui est vide, pas le code.

    Sans ce test, vider la table masquerait une éventuelle panne de
    `to_spoken`, et la prochaine entrée ajoutée n'aurait aucun effet.
    """
    import dataclasses

    from hausa_numbers import expressions

    lexique = dataclasses.replace(hausa_numbers.load_lexicon(), spoken_forms={"jikka": "jikk ka"})
    monkeypatch.setattr(expressions, "load_lexicon", lambda: lexique)
    assert hausa_numbers.to_spoken("jikka biyar") == "jikk ka biyar"
    # Substitution sur frontières de mots, jamais à l'intérieur d'un autre mot.
    assert hausa_numbers.to_spoken("ɗari") == "ɗari"


def test_a_spoken_form_is_never_an_accepted_input() -> None:
    """Une forme parlée ne doit pas devenir une deuxième forme canonique.

    Si ``jikk ka`` était analysable, le lexique aurait deux écritures
    concurrentes pour 1 000 et le corpus collecterait les deux.
    """
    assert hausa_numbers.parse_money("jikk ka") is None
    assert hausa_numbers.parse_money("jikka") == 1_000
