"""Décodage Whisper **contraint** à la grammaire des nombres et opérations hausa.

Pourquoi ce module existe
-------------------------

Le service décodait librement : Whisper produisait un texte quelconque, que la
grammaire tentait ensuite de rattraper. Sur le corpus réel, 9 énoncés sur 10
finissaient en ``repeat`` parce que le modèle écrivait ``so`` au lieu de ``sau``,
``ƙaƙƙashi`` au lieu de ``kashi``, ``ga ƙara`` au lieu de ``a ƙara``. Réparer ces
formes après coup est sans fin : chaque nouvelle voix invente une nouvelle faute.

On inverse donc la contrainte, comme le fait le service zarma
(``/opt/zarma/services/asr/app/decoding.py``) : le décodeur **ne peut émettre que
des mots qui font avancer l'automate de** ``hausa_numbers.grammar``. ``so`` n'est
pas un arc de cet automate, donc ``so`` ne peut pas sortir. Toute transcription
produite ici est parseable **par construction** — ce n'est plus une propriété
qu'on espère, c'est une propriété de l'algorithme.

Le décodeur zarma est un *prefix beam search* CTC : il masque des arcs sur des
logits par trame. Whisper est autorégressif, on ne peut donc pas reprendre ce
code ; on en reprend le principe, transposé au niveau des tokens émis.

Ce que ce module refuse de faire
--------------------------------

Contraindre ne veut pas dire deviner. Si l'audio ne contient aucune opération,
le décodeur trouvera quand même *un* chemin dans l'automate — c'est la limite de
toute contrainte. Le garde-fou est la **confiance** : le coût acoustique moyen,
par token émis, payé pour rester dans la grammaire, comparé au meilleur chemin
libre. Sur le corpus réel, les énoncés réellement arithmétiques restent à
0,43–0,98 tandis que ceux qui contiennent un mot hors grammaire tombent à
0,00–0,37. En dessous du seuil, le décodeur **s'abstient** : le pipeline en
déduit ``number is None`` donc ``repeat``, jamais un faux calcul (FR21/NFR14).

Testabilité
-----------

Le cœur (automate de tokens, sélection du faisceau, confiance) est **sans
torch** : il consomme une ``LogprobSource`` abstraite. La CI peut donc l'exercer
sur des log-probs en fixtures, sans modèle ni GPU — exactement comme
``services/asr/tests`` le fait côté zarma.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

__all__ = [
    "ConstrainedDecoder",
    "DecodeResult",
    "DecoderConfig",
    "GrammarConstraint",
    "Hypothesis",
    "LogprobSource",
    "decoding_confidence",
]


# ---------------------------------------------------------------------------
# Automate au niveau des tokens
# ---------------------------------------------------------------------------


class GrammarConstraint:
    """Tokens autorisés à chaque pas, dérivés de l'automate de la grammaire.

    Une **configuration** est un ensemble de triplets
    ``(état_grammaire, préfixe_partiel, mot_initial)``. L'ensemble est
    nécessaire : un même token BPE peut à la fois terminer une orthographe et en
    continuer une autre, donc la marche est non déterministe au niveau des
    tokens même si la grammaire l'est au niveau des mots.

    ``mot_initial`` doit être porté par la configuration, et non déduit d'un
    préfixe vide : le premier mot d'un énoncé s'encode sans espace initial, les
    suivants avec. Confondre les deux coupe la marche dès le deuxième token —
    le décodeur n'émet plus qu'une syllabe (``'ash'``, ``'sh'``) puis s'arrête.
    """

    def __init__(
        self,
        grammar,
        encode: Callable[[str], Sequence[int]],
        *,
        eot_id: int,
    ) -> None:
        self._grammar = grammar
        self._encode = encode
        self._eot = eot_id
        self._cache: dict[tuple[str, bool], tuple[tuple[int, ...], ...]] = {}

    @property
    def eot_id(self) -> int:
        return self._eot

    def _encodings(self, word: str, initial: bool) -> tuple[tuple[int, ...], ...]:
        """Encodages de **toutes** les orthographes connues d'un mot canonique.

        Plusieurs encodages mènent au même mot émis : c'est le mécanisme de
        convergence des variantes (``dari`` → ``ɗari``), obtenu sans aucune
        correction en aval.
        """
        key = (word, initial)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        spellings = self._grammar.pronunciations.get(word, (word,))
        encoded: list[tuple[int, ...]] = []
        for spelling in spellings:
            ids = tuple(int(i) for i in self._encode(spelling if initial else " " + spelling))
            if ids and ids not in encoded:
                encoded.append(ids)
        self._cache[key] = tuple(encoded)
        return self._cache[key]

    def initial(self) -> frozenset[tuple[int, tuple[int, ...], bool]]:
        return frozenset({(self._grammar.start, (), True)})

    def allowed(self, config: frozenset) -> set[int]:
        """Ids émettables depuis ``config`` (fin de séquence comprise)."""
        ids: set[int] = set()
        for state, partial, initial in config:
            for word in self._grammar.transitions(state):
                for encoding in self._encodings(word, initial):
                    if len(encoding) > len(partial) and encoding[: len(partial)] == partial:
                        ids.add(encoding[len(partial)])
            # Terminer n'est permis qu'entre deux mots, sur un état acceptant :
            # une transcription tronquée au milieu d'un mot ne serait pas une
            # forme de la langue.
            if not partial and self._grammar.is_accepting(state):
                ids.add(self._eot)
        return ids

    def step(self, config: frozenset, token: int) -> frozenset:
        """Configurations atteintes en consommant ``token``."""
        reached: set[tuple[int, tuple[int, ...], bool]] = set()
        for state, partial, initial in config:
            extended = partial + (token,)
            for word, target in self._grammar.transitions(state).items():
                for encoding in self._encodings(word, initial):
                    if len(encoding) < len(extended) or encoding[: len(extended)] != extended:
                        continue
                    if len(encoding) == len(extended):
                        reached.add((target, (), False))  # mot terminé → transition
                    else:
                        reached.add((state, extended, initial))  # mot en cours
        return frozenset(reached)

    def is_accepting(self, config: frozenset) -> bool:
        return any(
            not partial and self._grammar.is_accepting(state) for state, partial, _ in config
        )


# ---------------------------------------------------------------------------
# Configuration, résultats, confiance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecoderConfig:
    """Paramètres du décodeur — aucun n'est codé en dur dans la logique."""

    #: Largeur du faisceau. Mesuré sur ce VPS : 4 suffit (les mêmes hypothèses
    #: qu'à 8 sur les énoncés réellement arithmétiques), et la latence reste
    #: sous celle du décodage libre actuel.
    beam_width: int = 4
    #: Nombre d'hypothèses retournées (alimente ``AsrResult.candidates``).
    nbest: int = 3
    #: Borne de sécurité sur la longueur émise (une opération hausa dépasse
    #: rarement 15 mots ; au-delà, c'est que la recherche divague).
    max_steps: int = 48
    #: En dessous de cette confiance, le décodeur **s'abstient**. ``0.0`` =
    #: ne jamais s'abstenir (le décodeur ne fait qu'exposer le signal).
    #: À recalibrer sur un corpus plus large que les 10 énoncés actuels.
    reject_threshold: float = 0.0


@dataclass(frozen=True)
class Hypothesis:
    """Une hypothèse du faisceau : forme grammaticale + scores."""

    #: Texte émis — accepté par l'automate, donc parseable par construction.
    text: str
    token_ids: tuple[int, ...]
    #: ``-log P(token_ids)`` sous le modèle.
    neg_log_likelihood: float
    #: Confiance de décodage dans ``[0, 1]`` (cf. ``decoding_confidence``).
    confidence: float


@dataclass(frozen=True)
class DecodeResult:
    """Sortie du décodeur : hypothèses classées et signal d'abstention."""

    hypotheses: tuple[Hypothesis, ...]
    #: ``-log P`` du meilleur chemin **libre** (référence de comparaison).
    free_neg_log_likelihood: float
    #: Texte du chemin libre — journalisé pour le diagnostic, jamais retourné
    #: à l'utilisateur : il n'est pas grammatical.
    free_text: str
    reject_threshold: float

    @property
    def best(self) -> Hypothesis | None:
        return self.hypotheses[0] if self.hypotheses else None

    @property
    def confidence(self) -> float:
        best = self.best
        return best.confidence if best is not None else 0.0

    @property
    def rejected(self) -> bool:
        """L'énoncé doit-il être refusé faute de ressembler à un nombre ?

        Le décodeur s'abstient comme le ferait un ASR en échec ; c'est le
        pipeline API qui en tire ``repeat``. Aucune décision parallèle ici.
        """
        return self.best is None or self.confidence < self.reject_threshold


def decoding_confidence(
    neg_log_likelihood: float, free_neg_log_likelihood: float, token_count: int, free_count: int
) -> float:
    """Rapport de vraisemblance **par token émis** entre chemin contraint et libre.

    ``exp(-(nll/n - nll_libre/n_libre))`` ∈ ``[0, 1]`` : coût acoustique moyen,
    par symbole, payé pour rester dans la grammaire. 1,0 = la contrainte n'a rien
    coûté (l'audio *est* une opération) ; proche de 0 = il a fallu forcer.

    Normaliser **par token** et non par durée est repris de zarma, pour la même
    raison : rapporter le coût à la durée dilue une courte insertion dans un long
    silence et fait accepter n'importe quoi.

    Ce n'est pas un second mécanisme de décision : c'est le signal acoustique qui
    alimente la confiance composite existante, laquelle converge vers la
    politique ``accept | confirm | repeat`` déjà en place.
    """
    if token_count <= 0 or not math.isfinite(neg_log_likelihood):
        return 0.0
    if free_count <= 0 or not math.isfinite(free_neg_log_likelihood):
        return 0.0
    gap = neg_log_likelihood / token_count - free_neg_log_likelihood / free_count
    if gap <= 0.0:  # le chemin contraint ne peut pas battre le chemin libre
        return 1.0
    return float(math.exp(-gap))


# ---------------------------------------------------------------------------
# Source de log-probabilités (frontière avec le modèle)
# ---------------------------------------------------------------------------


class LogprobSource(Protocol):
    """Fournit les log-probs du prochain token — seule dépendance au modèle.

    Isoler cette frontière permet d'exercer tout le décodage sur des fixtures,
    sans torch ni poids : c'est ce qui rend le module testable en CI.
    """

    def start(self) -> Sequence[float]:
        """Log-probs après le préfixe forcé (``<|ha|><|transcribe|>``…)."""

    def extend(self, parents: Sequence[int], tokens: Sequence[int]) -> Sequence[Sequence[float]]:
        """Log-probs après extension de chaque faisceau ``parents[i]`` par ``tokens[i]``."""


# ---------------------------------------------------------------------------
# Recherche en faisceau contrainte
# ---------------------------------------------------------------------------


class ConstrainedDecoder:
    """Beam search restreint à l'automate de la grammaire."""

    def __init__(self, constraint: GrammarConstraint, config: DecoderConfig | None = None) -> None:
        self._constraint = constraint
        self._config = config or DecoderConfig()

    @property
    def config(self) -> DecoderConfig:
        return self._config

    def decode(
        self,
        source: LogprobSource,
        decode_text: Callable[[Sequence[int]], str],
        *,
        free_neg_log_likelihood: float,
        free_token_count: int,
        free_text: str = "",
    ) -> DecodeResult:
        cfg = self._config
        constraint = self._constraint
        eot = constraint.eot_id

        logprobs: Sequence[Sequence[float]] = [source.start()]
        # faisceau : (nll, ids émis, configuration d'automate)
        live: list[tuple[float, tuple[int, ...], frozenset]] = [(0.0, (), constraint.initial())]
        finished: list[tuple[float, tuple[int, ...]]] = []

        for _ in range(cfg.max_steps):
            pool: list[tuple[float, tuple[int, ...], frozenset, int]] = []
            for row, (nll, ids, config) in enumerate(live):
                row_logprobs = logprobs[row]
                for token in constraint.allowed(config):
                    extended_nll = nll - float(row_logprobs[token])
                    if token == eot:
                        finished.append((extended_nll, ids))
                    else:
                        pool.append(
                            (extended_nll, ids + (token,), constraint.step(config, token), row)
                        )
            if not pool:
                break
            pool.sort(key=lambda item: item[0])
            pool = pool[: cfg.beam_width]
            # Poursuivre des chemins déjà plus coûteux qu'une fin connue ne peut
            # plus rien améliorer : la NLL est croissante le long d'un chemin.
            if finished and pool[0][0] > min(score for score, _ in finished):
                break
            logprobs = source.extend([item[3] for item in pool], [item[1][-1] for item in pool])
            live = [(nll, ids, config) for nll, ids, config, _ in pool]

        hypotheses: list[Hypothesis] = []
        for nll, ids in sorted(finished, key=lambda item: item[0])[: cfg.nbest]:
            hypotheses.append(
                Hypothesis(
                    text=decode_text(ids),
                    token_ids=ids,
                    neg_log_likelihood=nll,
                    confidence=decoding_confidence(
                        nll, free_neg_log_likelihood, len(ids), free_token_count
                    ),
                )
            )
        return DecodeResult(
            hypotheses=tuple(hypotheses),
            free_neg_log_likelihood=free_neg_log_likelihood,
            free_text=free_text,
            reject_threshold=cfg.reject_threshold,
        )
