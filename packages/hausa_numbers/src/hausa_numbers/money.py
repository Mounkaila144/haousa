"""Système **monétaire** hausa du Niger — franc CFA.

Cette couche est distincte du moteur numérique (`parser.py`, `generator.py`),
qui reste un système positionnel classique où ``ɗari`` vaut 100 et ``jikka``
1 000. Ce moteur-là n'est pas faux : c'est exactement le **scalaire** dont on a
besoin pour les multiplicateurs. Il est donc conservé tel quel et réutilisé ici.

Deux lectures d'un même mot, jamais mélangées
---------------------------------------------

``ɗari`` vaut 500 F comme **montant**, et 100 comme **multiplicateur** :

    dari sau dari  ->  500 F × 100  =  50 000 F

D'où deux fonctions, et non une constante ambiguë : :func:`parse_money` et
:func:`parse_scalar`. Le contexte grammatical (opérateur) décide de laquelle
s'applique, jamais le mot lui-même.

La règle monétaire
------------------

Sous le millier, l'unité de compte est de 5 F — un mot vaut donc cinq fois sa
valeur numérique :

    ɗaya = 5 F      goma = 50 F      ashirin = 100 F      ɗari = 500 F

Le millier, lui, est une unité monétaire **à part entière** valant 1 000 F, et
non le numéral 1 000 rééchelonné (qui donnerait 5 000 F). Son multiplicateur
est un scalaire :

    jikka = 1 000 F        jikka biyar = 1 000 × 5 = 5 000 F
    jikka goma = 10 000 F  jikka ɗari  = 1 000 × 100 = 100 000 F

Les deux systèmes se rejoignent sans contradiction : ``ɗari biyu`` (numéral 200
× 5) et ``jikka`` valent tous deux 1 000 F. C'est une règle métier de cette
application, pas une propriété du hausa : `jika`/`jikka`/`dubu` y sont des
alias d'un unique concept interne, ``THOUSAND_CFA``.
"""

from __future__ import annotations

from typing import Final, Literal

from .exceptions import OutOfRangeError, ParseError
from .generator import generate
from .loader import load_lexicon
from .normalizer import normalize_hausa_text
from .parser import hausa_words_to_number

#: Unité de compte sous le millier : un mot vaut 5 F CFA par unité numérique.
UNIT_CFA: Final = 5

#: Le millier monétaire. Valeur **unique** derrière `jika`, `jikka` et `dubu` :
#: jamais deux constantes concurrentes, sans quoi les synonymes divergeraient.
THOUSAND_CFA: Final = 1_000

#: Plus grand montant exprimable : le multiplicateur du millier reste un
#: scalaire inférieur à 1 000, sans quoi la forme produite réemploierait le mot
#: du millier à l'intérieur de son propre multiplicateur.
MAX_MONEY_CFA: Final = 999 * THOUSAND_CFA + (999 * UNIT_CFA)

MIN_MONEY_CFA: Final = 0

#: Appellation du millier retenue par l'utilisateur. Ne change **que** la
#: restitution : les deux formes restent comprises en entrée (cf. §8).
ThousandNaming = Literal["jika", "dubu"]

DEFAULT_THOUSAND_NAMING: Final[ThousandNaming] = "jika"

THOUSAND_NAMINGS: Final[tuple[ThousandNaming, ...]] = ("jika", "dubu")


def _thousand_token() -> str:
    """Forme normalisée du millier — celle que produit le normaliseur.

    `jika` et `dubu` convergent vers la forme canonique du lexique avant toute
    analyse : le parseur ne voit donc qu'un seul mot.
    """
    return load_lexicon().scales["thousand"].canonical or "jikka"


def thousand_word(naming: ThousandNaming = DEFAULT_THOUSAND_NAMING) -> str:
    """Mot du millier à **écrire et prononcer** selon la préférence.

    `jika` rend la forme canonique du lexique (``jikka``, k géminé, hausa du
    Niger) : même mot, orthographe du projet. `dubu` rend le standard nigérian.
    """
    if naming not in THOUSAND_NAMINGS:
        raise ValueError(f"Appellation du millier inconnue : {naming!r}")
    return _thousand_token() if naming == "jika" else "dubu"


def parse_scalar(text: str) -> int | None:
    """Valeur **numérique** d'un nombre hausa — multiplicateur ou diviseur.

    C'est le moteur numérique classique, inchangé : ``ɗari`` y vaut 100.
    """
    try:
        return hausa_words_to_number(text)
    except (ParseError, TypeError):
        return None


def _money_below_thousand(tokens: list[str]) -> int | None:
    """Montant d'une expression sous le millier : numéral × 5 F."""
    if not tokens:
        return None
    scalar = parse_scalar(" ".join(tokens))
    if scalar is None:
        return None
    amount = scalar * UNIT_CFA
    return amount if amount < THOUSAND_CFA else None


def _parse_money_tokens(tokens: list[str]) -> int | None:
    if not tokens:
        return None

    if tokens[0] != _thousand_token():
        # Aucun millier : le montant est le numéral rééchelonné. La borne des
        # 1 000 F n'est pas imposée ici — `ɗari biyu` (200 × 5) vaut bien
        # 1 000 F et doit être accepté comme synonyme de `jikka`.
        scalar = parse_scalar(" ".join(tokens))
        return None if scalar is None else scalar * UNIT_CFA

    rest = tokens[1:]
    if not rest:
        return THOUSAND_CFA

    # Priorité au multiplicateur complet, comme dans le moteur numérique : en
    # hausa le même `da` compose aussi le multiplicateur (`jikka ɗari uku da
    # arba'in da biyar` = 345 000 F). Le couper trop tôt fabriquerait un tout
    # autre montant.
    multiplier = parse_scalar(" ".join(rest))
    if multiplier is not None and 0 < multiplier < THOUSAND_CFA:
        return THOUSAND_CFA * multiplier

    # Sinon, `da` sépare le multiplicateur du reste : `jikka biyar da ɗari`.
    solutions: set[int] = set()
    for index in range(len(rest) - 1, -1, -1):
        if rest[index] != "da":
            continue
        left, right = rest[:index], rest[index + 1 :]
        if not right:
            continue
        multiplier = 1 if not left else parse_scalar(" ".join(left))
        remainder = _money_below_thousand(right)
        if multiplier is None or remainder is None:
            continue
        if 0 < multiplier < THOUSAND_CFA and 0 < remainder < THOUSAND_CFA:
            solutions.add(THOUSAND_CFA * multiplier + remainder)

    # Une seule lecture grammaticale, sinon on refuse : une calculatrice
    # d'argent ne devine pas un montant (cf. §30).
    return solutions.pop() if len(solutions) == 1 else None


def parse_money(text: str) -> int | None:
    """Montant en francs CFA, ou ``None`` si l'énoncé n'est pas un montant.

    Ne devine jamais : une expression ambiguë ou incomplète est refusée plutôt
    que ramenée à une valeur plausible.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    normalized = normalize_hausa_text(text)
    if not normalized:
        return None
    if normalized == "sifili":
        return 0
    amount = _parse_money_tokens(normalized.split())
    if amount is None or not MIN_MONEY_CFA <= amount <= MAX_MONEY_CFA:
        return None
    return amount


def format_money(
    amount: int,
    naming: ThousandNaming = DEFAULT_THOUSAND_NAMING,
) -> str:
    """Montant CFA rendu en mots hausa, selon l'appellation choisie.

    Les multiples de 1 000 passent par le mot du millier (`jikka biyar`), forme
    la plus courte à l'oreille ; le reste par le numéral rééchelonné (`ɗari
    uku` = 1 500 F). Les deux restent compris en entrée dans tous les cas.
    """
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError("format_money() attend un entier.")
    if not MIN_MONEY_CFA <= amount <= MAX_MONEY_CFA:
        raise OutOfRangeError(
            f"Montant hors plage : {amount}.",
            code="OUT_OF_RANGE",
        )
    if amount % UNIT_CFA:
        # L'unité de compte est de 5 F : un montant intermédiaire n'a pas de
        # forme dite. Le taire vaudrait mieux que d'arrondir en silence.
        raise OutOfRangeError(
            f"Montant non exprimable, l'unité est de {UNIT_CFA} F : {amount}.",
            code="UNRESOLVED_FORM",
        )

    word = thousand_word(naming)
    thousands, remainder = divmod(amount, THOUSAND_CFA)

    if thousands == 0:
        return generate(amount // UNIT_CFA)

    head = word if thousands == 1 else f"{word} {generate(thousands)}"
    if remainder == 0:
        return head
    return f"{head} da {generate(remainder // UNIT_CFA)}"


__all__ = [
    "DEFAULT_THOUSAND_NAMING",
    "MAX_MONEY_CFA",
    "MIN_MONEY_CFA",
    "THOUSAND_CFA",
    "THOUSAND_NAMINGS",
    "UNIT_CFA",
    "ThousandNaming",
    "format_money",
    "parse_money",
    "parse_scalar",
    "thousand_word",
]
