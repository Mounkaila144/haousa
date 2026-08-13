#!/usr/bin/env python3
"""Génère le corpus d'enregistrement TTS hausa depuis le moteur linguistique.

Pourquoi générer plutôt qu'écrire à la main
-------------------------------------------

Le modèle doit savoir dire **ce que l'application dit**, ni plus ni moins. Or
ces deux ensembles ne coïncident pas : ``ɗari uku`` est compris (1 500 F) mais
n'est jamais prononcé, puisque ``format_money(1500)`` rend ``jikka da ɗari``.
Un corpus écrit à la main dériverait du moteur dès la première évolution du
lexique ; celui-ci est reconstruit depuis ``hausa_numbers``, donc juste par
construction.

Ce que le corpus couvre
-----------------------

Toutes les **formes de sortie** du moteur, et elles seules :

1. les trois consignes parlées de l'interface ;
2. les montants sous le millier — ``format_money`` y rend un numéral de 0 à 199
   (l'unité de compte étant de 5 F) ;
3. les milliers, avec les DEUX appellations : `jikka` (Niger) et `dubu`
   (Nigeria) sont un réglage utilisateur, la voix doit savoir dire les deux ;
4. les milliers suivis d'un reste (``jikka biyar da ɗari``) ;
5. la relecture des opérations, chaque opérande dans sa lecture propre — le
   multiplicateur de `sau` est un nombre, pas un montant ;
6. le reste de division (``saura``).

`miliyan` est volontairement absent : le plus grand montant exprimable est
999 995 F, le million n'est jamais prononcé par la calculatrice.

Sortie
------

En-tête ``id,texte_zarma,affichage`` : c'est le contrat exact qu'impose le
Studio vocal (`entrainement/tts_recorder/lib/csv_codec.dart`). Le nom de la
colonne est celui de l'outil, pas une affirmation sur la langue.

Usage :

    python scripts/generate_tts_prompts.py > dataset/tts/tts_prompts.csv
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "hausa_numbers" / "src"))

import hausa_numbers  # noqa: E402
from hausa_numbers import (  # noqa: E402
    THOUSAND_CFA,
    UNIT_CFA,
    Expression,
    format_money,
    render_expression,
    render_result,
)

#: Graine fixe : le corpus doit être reproductible à l'identique, sans quoi
#: deux exécutions produiraient des listes différentes et les enregistrements
#: déjà faits ne correspondraient plus aux identifiants.
SEED = 20260813

#: Consignes parlées de l'interface (`apps/mobile/lib/l10n/hausa_messages.dart`).
SYSTEM_PROMPTS = [
    ("sys_confirm", "Shin wannan ne?", "Est-ce bien cela ?"),
    ("sys_cannot_answer", "Ba zan iya bayar da amsa ba.", "Je ne peux pas répondre."),
    ("sys_repeat", "Da fatan za a sake magana.", "Veuillez répéter."),
]


class Corpus:
    """Accumule les consignes en refusant les doublons de texte."""

    def __init__(self) -> None:
        self._rows: list[tuple[str, str, str]] = []
        self._seen: set[str] = set()

    def add(self, prompt_id: str, text: str, display: str) -> None:
        if text in self._seen:
            return
        self._seen.add(text)
        self._rows.append((prompt_id, text, display))

    def add_amount(self, prefix: str, amount: int, naming: str = "jika") -> None:
        self.add(f"{prefix}_{amount}", format_money(amount, naming), f"{amount} F")

    @property
    def rows(self) -> list[tuple[str, str, str]]:
        return self._rows

    def __len__(self) -> int:
        return len(self._rows)


def _sample(rng: random.Random, population: list[int], count: int) -> list[int]:
    count = min(count, len(population))
    return sorted(rng.sample(population, count))


def build_corpus() -> Corpus:
    rng = random.Random(SEED)
    corpus = Corpus()

    for prompt_id, text, display in SYSTEM_PROMPTS:
        corpus.add(prompt_id, text, display)

    # --- 1. Montants sous le millier ------------------------------------- #
    # `format_money` y rend `generate(montant / 5)`, soit un numéral de 0 à 199.
    # On couvre chaque structure : zéro, unités, `goma sha X`, dizaines,
    # `dizaine da unité`, `ɗari`, `ɗari da X`.
    corpus.add_amount("amount", 0)
    for unit in range(1, 10):
        corpus.add_amount("amount", unit * UNIT_CFA)
    for teen in range(10, 20):
        corpus.add_amount("amount", teen * UNIT_CFA)
    for tens in range(20, 100, 10):
        corpus.add_amount("amount", tens * UNIT_CFA)
    # `dizaine da unité` : toutes les dizaines, unités échantillonnées.
    for tens in range(20, 100, 10):
        for unit in _sample(rng, list(range(1, 10)), 5):
            corpus.add_amount("amount", (tens + unit) * UNIT_CFA)
    corpus.add_amount("amount", 100 * UNIT_CFA)  # `ɗari` = 500 F
    for numeral in _sample(rng, list(range(101, 200)), 40):
        corpus.add_amount("amount", numeral * UNIT_CFA)

    # --- 2. Milliers, dans les DEUX appellations --------------------------- #
    # Le pays choisi ne change que ce mot : la voix doit porter les deux, sinon
    # la moitié des utilisateurs entendrait un mot jamais enregistré.
    thousand_counts = (
        list(range(1, 10))
        + _sample(rng, list(range(10, 20)), 6)
        + list(range(20, 100, 10))
        + _sample(rng, list(range(21, 100)), 10)
        + [100, 200, 500, 900]
        + _sample(rng, list(range(101, 1000)), 20)
    )
    for naming in ("jika", "dubu"):
        for count in sorted(set(thousand_counts)):
            corpus.add_amount(f"thousand_{naming}", count * THOUSAND_CFA, naming)

    # --- 3. Millier suivi d'un reste --------------------------------------- #
    for naming in ("jika", "dubu"):
        for count in _sample(rng, list(range(1, 100)), 16):
            for numeral in _sample(rng, list(range(1, 200)), 2):
                corpus.add_amount(
                    f"mixed_{naming}",
                    count * THOUSAND_CFA + numeral * UNIT_CFA,
                    naming,
                )

    # --- 4. Relecture des opérations --------------------------------------- #
    # L'écran de confirmation relit l'opération entendue : elle doit se dire
    # aussi naturellement que le résultat.
    money_pool = [n * UNIT_CFA for n in range(1, 200)] + [n * THOUSAND_CFA for n in range(1, 100)]
    for symbol in ("+", "-", "*", "/"):
        scalar_right = symbol in {"*", "/"}
        for _ in range(20):
            left = rng.choice(money_pool)
            right = rng.choice(range(2, 101)) if scalar_right else rng.choice(money_pool)
            expression = Expression(left, symbol, right)
            corpus.add(
                f"op_{symbol}_{left}_{right}",
                render_expression(expression),
                f"{left} {symbol} {right}",
            )

    # --- 5. Reste de division ---------------------------------------------- #
    # `saura` n'apparaît nulle part ailleurs : sans ces prises, le mot le plus
    # porteur de sens d'une division resterait absent du modèle.
    for _ in range(40):
        left = rng.choice([n * UNIT_CFA for n in range(20, 200)])
        right = rng.choice(range(3, 20))
        quotient, remainder = divmod(left, right)
        if remainder % UNIT_CFA or quotient % UNIT_CFA or remainder == 0:
            continue
        result = hausa_numbers.evaluate(Expression(left, "/", right))
        corpus.add(
            f"remainder_{left}_{right}",
            render_result(result),
            f"{quotient} F reste {remainder} F",
        )

    return corpus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Fichier CSV de sortie (défaut : sortie standard).",
    )
    args = parser.parse_args()

    corpus = build_corpus()
    stream = args.output.open("w", encoding="utf-8", newline="") if args.output else sys.stdout
    try:
        writer = csv.writer(stream, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["id", "texte_zarma", "affichage"])
        writer.writerows(corpus.rows)
    finally:
        if args.output:
            stream.close()

    lengths = [len(text.split()) for _, text, _ in corpus.rows]
    print(
        f"{len(corpus)} consignes, de {min(lengths)} à {max(lengths)} mots.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
