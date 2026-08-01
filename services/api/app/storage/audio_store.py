"""Stockage filesystem privé et borné des contributions audio."""

from __future__ import annotations

import asyncio
import os
import wave
from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.config import get_settings
from app.pipeline.audio import DecodedAudio


class AudioStorageError(Exception):
    """Erreur de stockage contrôlée, sans détail de chemin exposable."""


class AudioStore(Protocol):
    """Interface injectable du stockage audio consenti."""

    async def save(self, audio: DecodedAudio) -> str:
        """Stocke un WAV canonique et retourne sa référence opaque."""

    async def delete(self, audio_ref: str) -> None:
        """Supprime une référence de façon idempotente."""


class FilesystemAudioStore:
    """Stocke des WAV privés sous une racine dédiée."""

    def __init__(self, root: Path) -> None:
        try:
            self._root = Path(root).expanduser().resolve(strict=False)
        except (OSError, RuntimeError, ValueError) as exc:
            raise AudioStorageError("invalid audio storage root") from exc

    def local_path(self, audio_ref: str) -> Path:
        """Résout une référence opaque sans permettre de sortir de la racine."""

        return self._safe_target(audio_ref)

    async def save(self, audio: DecodedAudio) -> str:
        """Écrit atomiquement un WAV PCM avec des permissions restrictives."""

        audio_ref = f"{uuid4().hex}.wav"
        target = self._safe_target(audio_ref)
        temporary = self._root / f".{audio_ref}.{uuid4().hex}.tmp"

        def write() -> None:
            payload = BytesIO()
            try:
                with wave.open(payload, "wb") as writer:
                    writer.setnchannels(audio.channels)
                    writer.setsampwidth(audio.sample_width)
                    writer.setframerate(audio.sample_rate)
                    writer.writeframes(audio.pcm)

                self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
                os.chmod(self._root, 0o700)
                descriptor = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(payload.getvalue())
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
                os.chmod(target, 0o600)
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                target.unlink(missing_ok=True)
                raise AudioStorageError("audio write failed") from exc

        await asyncio.to_thread(write)
        return audio_ref

    async def delete(self, audio_ref: str) -> None:
        """Supprime un fichier absent ou présent, sans suivre de chemin client."""

        target = self._safe_target(audio_ref)

        def unlink() -> None:
            try:
                target.unlink(missing_ok=True)
            except OSError as exc:
                raise AudioStorageError("audio deletion failed") from exc

        await asyncio.to_thread(unlink)

    def _safe_target(self, audio_ref: str) -> Path:
        try:
            reference = Path(audio_ref)
        except (TypeError, ValueError) as exc:
            raise AudioStorageError("invalid audio reference") from exc
        if (
            not audio_ref
            or reference.is_absolute()
            or reference.name != audio_ref
            or reference.suffix.lower() != ".wav"
        ):
            raise AudioStorageError("invalid audio reference")
        return self._root / reference.name


def get_audio_store() -> AudioStore:
    """Construit le stockage configuré pour l'injection FastAPI."""

    return FilesystemAudioStore(get_settings().AUDIO_STORAGE_DIR)


__all__ = [
    "AudioStorageError",
    "AudioStore",
    "FilesystemAudioStore",
    "get_audio_store",
]
