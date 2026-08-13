"""Cœur **pur** du pipeline de reconnaissance (ASR → nombre → décision).

Cette fonction est **sans I/O, sans persistance, sans FastAPI** : à partir d'un
``AsrResult`` déjà obtenu et des ``Settings`` effectifs, elle rejoue l'exact
enchaînement de décision de ``/api/v1/recognize`` — normalisation, parsing,
candidats numériques, confiance composite, politique accept/confirm/repeat.

Elle est la **source unique** de cet enchaînement : la route API *et* le harnais
de benchmark (Epic 5) l'appellent, de sorte qu'aucune règle de décision n'est
dupliquée (isolation du moteur linguistique).

Story 6.1 — un énoncé peut aussi être une **opération**. L'extension est
volontairement additive :

- on tente d'abord un **nombre seul**, exactement comme avant ;
- ce n'est que si aucun nombre n'est reconnu qu'on tente une **expression**.
  Les deux langues sont disjointes (aucun mot d'opérateur n'appartient à un
  nombre, cf. ``build_expression_grammar``), donc cet ordre n'introduit aucune
  ambiguïté : un texte ne peut pas être les deux.

Conséquence recherchée : le chemin « nombre seul » des epics 1–5 est
**inchangé**, jusque dans les valeurs de confiance et la décision.
"""

from __future__ import annotations

from dataclasses import dataclass

import hausa_numbers

from app.asr.base import AsrResult
from app.config import Settings
from app.pipeline.confidence import (
    ConfidenceResult,
    NumericCandidate,
    composite_confidence,
    expression_candidates_from_asr,
    numeric_candidates_from_asr,
)
from app.pipeline.policy import Decision, decide


@dataclass(frozen=True, slots=True)
class RecognitionOutcome:
    """Résultat déterministe du cœur de décision (aucune donnée d'I/O)."""

    normalized_text: str
    number: int | None
    hausa_text: str
    numeric_candidates: list[NumericCandidate]
    confidence: ConfidenceResult
    decision: Decision
    #: Opération reconnue, si l'énoncé en était une (story 6.1).
    expression: hausa_numbers.Expression | None = None
    #: Résultat exact de cette opération, ``None`` si elle sort du domaine.
    expression_result: hausa_numbers.ExpressionResult | None = None
    #: Forme hausa du resultat (avec ``saura`` pour une division a reste).
    result_hausa_text: str = ""
    #: Forme **à prononcer** du résultat, quand elle diffère de l'écrite.
    #:
    #: C'est le résultat, et non l'opération relue, qui est prononcé après un
    #: calcul : sans cette forme, la seule sortie qui atteigne un utilisateur
    #: non lecteur resterait mal prononcée.
    result_spoken_text: str = ""
    #: Code de refus arithmétique (``NEGATIVE_RESULT``…) — jamais un résultat approché.
    refusal_code: str | None = None
    #: Forme hausa **à prononcer**, quand elle diffère de ``hausa_text``.
    #:
    #: Variante a prononcer lorsqu'un fournisseur vocal en exige une autre.
    spoken_text: str = ""


def _recognize_expression(
    normalized_text: str,
) -> tuple[hausa_numbers.Expression | None, hausa_numbers.ExpressionResult | None, str | None]:
    """Analyse et évalue une expression. Refus explicite plutôt que résultat inventé."""
    expression = hausa_numbers.parse_expression(normalized_text)
    if expression is None:
        return None, None, None
    try:
        return expression, hausa_numbers.evaluate(expression), None
    except hausa_numbers.DomainError as exc:
        # L'énoncé est compris, mais la réponse n'existe pas dans le domaine :
        # ce n'est PAS un échec de reconnaissance (FR21). L'utilisateur doit
        # l'apprendre, pas se voir demander de répéter.
        return expression, None, exc.code


def run_recognition_pipeline(
    asr_result: AsrResult,
    settings: Settings,
    naming: hausa_numbers.ThousandNaming = hausa_numbers.DEFAULT_THOUSAND_NAMING,
) -> RecognitionOutcome:
    """Exécute normalisation → parsing → confiance → politique sur un ``AsrResult``.

    Aucun nombre n'est inventé : un texte ni numérique ni arithmétique reste
    ``number is None`` et conduit à ``repeat`` (FR21). Comportement identique à
    la route.

    ``naming`` ne touche qu'à la **restitution** : `jika` et `dubu` restent
    tous deux compris à l'entrée quelle que soit sa valeur. Les montants
    calculés, eux, ne dépendent jamais de ce réglage.
    """

    normalized_text = hausa_numbers.normalize(asr_result.text)
    number = hausa_numbers.parse_money(normalized_text)

    expression = expression_result = refusal_code = None
    if number is None:
        expression, expression_result, refusal_code = _recognize_expression(normalized_text)

    expression_recognized = expression is not None
    numeric_candidates = (
        expression_candidates_from_asr(asr_result)
        if expression_recognized
        else numeric_candidates_from_asr(asr_result)
    )
    confidence = composite_confidence(
        asr=asr_result,
        normalized_text=normalized_text,
        number=number,
        numeric_candidates=numeric_candidates,
        settings=settings,
        expression_recognized=expression_recognized,
    )
    decision = decide(
        score=confidence.score,
        number=number,
        numeric_candidates=numeric_candidates,
        settings=settings,
        expression_recognized=expression_recognized,
    )
    hausa_text = hausa_numbers.format_money(number, naming) if number is not None else ""
    spoken_text = ""
    if expression is not None:
        hausa_text = hausa_numbers.render_expression(expression, naming)
        parle = hausa_numbers.render_spoken(expression, naming)
        # Renseigné seulement s'il apporte quelque chose : un champ toujours
        # présent inviterait à s'en servir partout, y compris là où c'est
        # l'identité qui compte.
        spoken_text = parle if parle != hausa_text else ""
    result_hausa_text = (
        hausa_numbers.render_result(expression_result, naming)
        if expression_result is not None
        else ""
    )
    # Un nombre seul est lui aussi prononcé : la forme parlée ne concerne donc
    # pas que les opérations.
    spoken_hausa = hausa_numbers.to_spoken(hausa_text)
    if not spoken_text and spoken_hausa != hausa_text:
        spoken_text = spoken_hausa
    spoken_result = hausa_numbers.to_spoken(result_hausa_text)
    result_spoken_text = spoken_result if spoken_result != result_hausa_text else ""

    return RecognitionOutcome(
        normalized_text=normalized_text,
        number=number,
        hausa_text=hausa_text,
        numeric_candidates=numeric_candidates,
        confidence=confidence,
        decision=decision,
        expression=expression,
        expression_result=expression_result,
        result_hausa_text=result_hausa_text,
        result_spoken_text=result_spoken_text,
        refusal_code=refusal_code,
        spoken_text=spoken_text,
    )


__all__ = ["RecognitionOutcome", "run_recognition_pipeline"]
