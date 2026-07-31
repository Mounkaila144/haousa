"""Point d'extension pour brancher un fournisseur TTS Hausa."""

from __future__ import annotations

from typing import Protocol


class TtsUnavailableError(RuntimeError):
    pass


class HausaTtsProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    def synthesize(self, text: str) -> bytes:
        """Retourne un WAV Hausa; ``text`` provient toujours du generateur canonique."""
        ...
