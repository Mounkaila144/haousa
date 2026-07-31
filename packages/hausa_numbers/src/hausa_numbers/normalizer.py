"""Normalisation explicite et non floue des transcriptions hausa."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

HAUSA_NORMALIZATION_ALIASES = {
    "daya": "ɗaya",
    "d aya": "ɗaya",
    "d'aya": "ɗaya",
    "hudu": "huɗu",
    "hu du": "huɗu",
    "dari": "ɗari",
    "d'ari": "ɗari",
    "sifiri": "sifili",
    "ishirin": "ashirin",
    "tasa in": "tasa'in",
    "tasa'in": "tasa'in",
    "tasain": "tasa'in",
    "tisa'in": "tasa'in",
    "casa'in": "tasa'in",
    "million": "miliyan",
    "milliyan": "miliyan",
    "billiyan": "biliyan",
    "triliyan": "tiriliyan",
    "a kara": "a ƙara",
}

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'"})
_PUNCTUATION = re.compile(r"[^\w\s'ɗƙƄɓ]", re.UNICODE)
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class Transformation:
    source: str
    target: str
    kind: str = "hausa_alias"

    def as_dict(self) -> dict[str, str]:
        return {"from": self.source, "to": self.target, "type": self.kind}


@dataclass(frozen=True)
class NormalizationResult:
    raw: str
    normalized: str
    transformations: list[Transformation] = field(default_factory=list)


def _clean(text: str) -> str:
    cleaned = unicodedata.normalize("NFC", text).translate(_APOSTROPHES).lower()
    cleaned = _PUNCTUATION.sub(" ", cleaned).replace("_", " ")
    return _SPACES.sub(" ", cleaned).strip()


def normalize_with_trace(text: str) -> NormalizationResult:
    if not isinstance(text, str):
        raise TypeError("normalize_hausa_text() attend une chaine.")
    value = _clean(text)
    changes: list[Transformation] = []
    # Les expressions les plus longues sont traitees en premier et uniquement
    # sur des frontieres de mots. Les mots inconnus restent inchanges.
    for source in sorted(HAUSA_NORMALIZATION_ALIASES, key=len, reverse=True):
        target = HAUSA_NORMALIZATION_ALIASES[source]
        pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)")
        if pattern.search(value):
            value = pattern.sub(target, value)
            changes.append(Transformation(source, target))
    return NormalizationResult(text, _SPACES.sub(" ", value).strip(), changes)


def normalize_hausa_text(text: str) -> str:
    return normalize_with_trace(text).normalized


normalize = normalize_hausa_text

__all__ = [
    "HAUSA_NORMALIZATION_ALIASES",
    "NormalizationResult",
    "Transformation",
    "normalize",
    "normalize_hausa_text",
    "normalize_with_trace",
]
