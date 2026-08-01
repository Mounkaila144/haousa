"""Tests du décodage contraint — **sans torch, sans modèle, sans GPU**.

Le décodeur ne dépend du modèle qu'à travers ``LogprobSource``. On l'alimente
donc avec des log-probs fabriquées, ce qui permet d'exercer en CI la propriété
qui compte : *toute sortie est une forme acceptée par la grammaire*.
"""

from __future__ import annotations

import importlib.util
import math
import sys
import types
from pathlib import Path

import pytest

PACKAGE = "hausa_asr_decoding_under_test"
APP_DIR = Path(__file__).resolve().parents[1] / "app"
_package = types.ModuleType(PACKAGE)
_package.__path__ = [str(APP_DIR)]
sys.modules[PACKAGE] = _package


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.{name}", APP_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


decoding = _load("decoding")
ConstrainedDecoder = decoding.ConstrainedDecoder
DecoderConfig = decoding.DecoderConfig
GrammarConstraint = decoding.GrammarConstraint
decoding_confidence = decoding.decoding_confidence


# --------------------------------------------------------------------------
# Tokenizer de test : découpe chaque orthographe en deux morceaux quand elle
# est assez longue. Indispensable — c'est précisément sur les mots à plusieurs
# tokens que la marche de l'automate peut casser (le décodeur n'émettait alors
# qu'une syllabe, « ash », « sh », avant de s'arrêter).
# --------------------------------------------------------------------------

EOT = 0


class FakeTokenizer:
    def __init__(self) -> None:
        self._ids: dict[str, int] = {}

    def _id(self, piece: str) -> int:
        return self._ids.setdefault(piece, len(self._ids) + 1)

    def encode(self, text: str) -> list[int]:
        if len(text.strip()) > 3:
            cut = len(text) // 2
            return [self._id(text[:cut]), self._id(text[cut:])]
        return [self._id(text)]

    @property
    def size(self) -> int:
        return len(self._ids) + 2


class _Row:
    """Ligne de log-probs **sans taille** : le faux tokenizer attribue ses ids
    à la volée, donc le vocabulaire n'est pas connu à l'avance."""

    __slots__ = ("_wanted", "_favour", "_other")

    def __init__(self, wanted: int, favour: float, other: float) -> None:
        self._wanted, self._favour, self._other = wanted, favour, other

    def __getitem__(self, token: int) -> float:
        return self._favour if token == self._wanted else self._other


class ScriptedSource:
    """``LogprobSource`` qui privilégie une séquence d'ids donnée.

    Tout autre token reste possible mais coûteux : le faisceau peut donc s'en
    écarter si la grammaire l'y oblige, exactement comme face au vrai modèle.
    """

    def __init__(
        self, preferred: list[int], vocab: int = 0, *, favour: float = -0.05, other: float = -6.0
    ) -> None:
        self._preferred = preferred
        self._favour = favour
        self._other = other
        self._depth = [0]

    def _row(self, depth: int) -> _Row:
        wanted = self._preferred[depth] if depth < len(self._preferred) else EOT
        return _Row(wanted, self._favour, self._other)

    def start(self):
        self._depth = [0]
        return self._row(0)

    def extend(self, parents, tokens):
        depths = [self._depth[p] + 1 for p in parents]
        self._depth = depths
        return [self._row(d) for d in depths]


@pytest.fixture(scope="module")
def grammar():
    from hausa_numbers.grammar import build_calculator_grammar

    return build_calculator_grammar()


@pytest.fixture(scope="module")
def tokenizer() -> FakeTokenizer:
    return FakeTokenizer()


@pytest.fixture
def constraint(grammar, tokenizer) -> GrammarConstraint:
    return GrammarConstraint(grammar, tokenizer.encode, eot_id=EOT)


def decode_text(tokenizer: FakeTokenizer):
    reverse = {}

    def render(ids) -> str:
        if not reverse:
            reverse.update({v: k for k, v in tokenizer._ids.items()})
        return "".join(reverse.get(int(i), "") for i in ids).strip()

    return render


def run(constraint, tokenizer, text: str, *, threshold: float = 0.0, free_nll: float = 1.0):
    """Décode en privilégiant l'encodage de ``text``."""
    ids: list[int] = []
    for position, word in enumerate(text.split()):
        ids.extend(tokenizer.encode(word if position == 0 else " " + word))
    source = ScriptedSource(ids, tokenizer.size)
    decoder = ConstrainedDecoder(
        constraint, DecoderConfig(beam_width=8, reject_threshold=threshold)
    )
    return decoder.decode(
        source,
        decode_text(tokenizer),
        free_neg_log_likelihood=free_nll,
        free_token_count=max(1, len(ids)),
    )


# --------------------------------------------------------------------------
# Propriété centrale : la sortie est grammaticale par construction
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spoken",
    [
        "ashirin kashi goma",
        "arba'in a ƙara uku",
        "arba'in a hidda goma",
        "ɗari uku da hamsin sau uku",
        "goma sha ɗaya a hidda goma",
    ],
)
def test_valid_expression_is_decoded_verbatim(constraint, tokenizer, grammar, spoken):
    result = run(constraint, tokenizer, spoken)
    assert result.best is not None
    assert grammar.accepts(result.best.text)


def test_every_hypothesis_is_accepted_by_the_grammar(constraint, tokenizer, grammar):
    result = run(constraint, tokenizer, "ɗari uku da hamsin sau biyu")
    assert result.hypotheses
    for hypothesis in result.hypotheses:
        assert grammar.accepts(hypothesis.text), hypothesis.text


# --------------------------------------------------------------------------
# Les confusions prouvées du modèle ne peuvent plus sortir du décodeur
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("intruder", "reason"),
    [
        ("so", "le modele ecrit 'so' pour 'sau' (multiplication)"),
        ("ƙaƙƙashi", "le modele ecrit 'ƙaƙƙashi' pour 'kashi' (division)"),
        ("jika", "mot hors grammaire, jamais un nombre"),
        ("shiga", "mot hors grammaire, jamais un nombre"),
    ],
)
def test_out_of_grammar_word_can_never_be_emitted(constraint, tokenizer, intruder, reason):
    """Aucune reparation a posteriori : le mot n'est pas un arc de l'automate."""
    result = run(constraint, tokenizer, f"ashirin {intruder} goma")
    assert result.best is not None
    assert intruder not in result.best.text.split(), reason


def test_ga_kara_collapses_to_the_canonical_operator(constraint, tokenizer, grammar):
    """« arba'in ga ƙara uku » ne peut sortir qu'en « arba'in a ƙara uku »."""
    result = run(constraint, tokenizer, "arba'in ga ƙara uku")
    assert result.best is not None
    assert "ga" not in result.best.text.split()
    assert grammar.accepts(result.best.text)


# --------------------------------------------------------------------------
# Confiance : bornée, et effondrée quand la contrainte a coûté cher
# --------------------------------------------------------------------------


def test_confidence_is_bounded():
    for nll, free, count, free_count in [
        (1.0, 1.0, 1, 1),
        (0.0, 50.0, 3, 3),
        (500.0, 0.1, 2, 2),
        (math.inf, 1.0, 2, 2),
    ]:
        assert 0.0 <= decoding_confidence(nll, free, count, free_count) <= 1.0


def test_confidence_is_one_when_constraint_costs_nothing():
    assert decoding_confidence(4.0, 4.0, 2, 2) == 1.0
    assert decoding_confidence(2.0, 8.0, 2, 2) == 1.0  # contraint meilleur que libre


def test_confidence_collapses_when_constraint_is_expensive():
    cheap = decoding_confidence(2.0, 1.8, 4, 4)
    forced = decoding_confidence(40.0, 1.8, 4, 4)
    assert forced < 0.01 < cheap


def test_degenerate_inputs_give_zero_confidence():
    assert decoding_confidence(1.0, 1.0, 0, 1) == 0.0
    assert decoding_confidence(1.0, 1.0, 2, 0) == 0.0


# --------------------------------------------------------------------------
# Abstention : jamais un nombre inventé
# --------------------------------------------------------------------------


def test_decoder_abstains_below_threshold(constraint, tokenizer):
    """Un chemin acoustiquement coûteux est refusé plutôt que retourné."""
    result = run(constraint, tokenizer, "jika biyar debe goma", threshold=0.9, free_nll=0.0)
    assert result.rejected


def test_decoder_does_not_abstain_by_default(constraint, tokenizer):
    """Seuil a 0 : le decodeur expose le signal, il ne decide pas seul."""
    result = run(constraint, tokenizer, "ashirin kashi goma", threshold=0.0)
    assert not result.rejected


# --------------------------------------------------------------------------
# Automate de tokens
# --------------------------------------------------------------------------


def test_end_of_text_only_allowed_on_accepting_state(constraint, grammar, tokenizer):
    config = constraint.initial()
    assert EOT not in constraint.allowed(config), "un enonce vide n'est pas un nombre"


def test_multi_token_word_walk_does_not_stall(constraint, tokenizer):
    """Regression : la marche cassait au 2e token d'un mot (mot initial vs suivant)."""
    config = constraint.initial()
    ids = tokenizer.encode("ashirin")
    assert len(ids) > 1, "le tokenizer de test doit produire des mots multi-tokens"
    for token in ids:
        assert token in constraint.allowed(config)
        config = constraint.step(config, token)
    assert config, "l'automate ne doit pas se vider apres un mot complet"
    assert constraint.allowed(config), "des continuations doivent rester possibles"
