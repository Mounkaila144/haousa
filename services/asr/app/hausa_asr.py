"""Service d'inference pour le modele Whisper Hausa de NCAIR."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"})


class HausaAsrError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class HausaAsrSettings(BaseSettings):
    HAUSA_ASR_MODEL: str = "NCAIR1/Hausa-ASR"
    HAUSA_ASR_LOCAL_PATH: str = ""
    HF_TOKEN: str = ""
    ASR_DEVICE: str = "auto"
    ASR_SAMPLE_RATE: int = Field(default=16_000, ge=8_000, le=48_000)
    ASR_MAX_AUDIO_SECONDS: float = Field(default=30.0, gt=0.0, le=300.0)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@dataclass(frozen=True)
class Transcription:
    text: str
    latency_ms: int
    model_version: str


def _device_index(requested: str) -> int:
    """CUDA si disponible, sinon CPU, comme exige par la configuration."""
    if requested not in {"auto", "cuda", "cpu"}:
        raise HausaAsrError(
            "ASR_DEVICE doit valoir auto, cuda ou cpu.", code="BAD_DEVICE", status_code=500
        )
    if requested == "cpu":
        return -1
    try:
        import torch
    except ImportError as exc:
        if requested == "cuda":
            raise HausaAsrError(
                "CUDA demande mais PyTorch est absent.",
                code="CUDA_UNAVAILABLE",
                status_code=500,
            ) from exc
        return -1
    if torch.cuda.is_available():
        return 0
    if requested == "cuda":
        raise HausaAsrError(
            "CUDA demande mais indisponible.", code="CUDA_UNAVAILABLE", status_code=500
        )
    return -1


def _decode_audio(raw: bytes, filename: str, settings: HausaAsrSettings) -> np.ndarray:
    if not raw:
        raise HausaAsrError("Le fichier audio est vide.", code="EMPTY_AUDIO", status_code=400)
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HausaAsrError(
            "Format audio non pris en charge.", code="UNSUPPORTED_AUDIO", status_code=415
        )
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise HausaAsrError(
            "ffmpeg est requis pour convertir l'audio.", code="FFMPEG_MISSING", status_code=503
        )

    # Le repertoire temporaire est detruit dans tous les cas. Aucun audio n'est
    # conserve par ce service, meme si l'inference ou le decodage echoue.
    with tempfile.TemporaryDirectory(prefix="hausa-asr-") as temporary:
        source = Path(temporary) / f"input{suffix}"
        target = Path(temporary) / "audio.wav"
        source.write_bytes(raw)
        process = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-i",
                str(source),
                "-ac",
                "1",
                "-ar",
                str(settings.ASR_SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                str(target),
            ],
            capture_output=True,
            check=False,
            timeout=max(15.0, settings.ASR_MAX_AUDIO_SECONDS * 2),
        )
        if process.returncode != 0 or not target.exists():
            raise HausaAsrError("Impossible de decoder l'audio.", code="INVALID_AUDIO")
        try:
            with wave.open(str(target), "rb") as reader:
                frames = reader.getnframes()
                duration = frames / reader.getframerate() if reader.getframerate() else 0.0
                if frames == 0 or duration <= 0:
                    raise HausaAsrError(
                        "Le fichier audio est vide.", code="EMPTY_AUDIO", status_code=400
                    )
                if duration > settings.ASR_MAX_AUDIO_SECONDS:
                    raise HausaAsrError(
                        "La duree audio depasse la limite configuree.",
                        code="AUDIO_TOO_LONG",
                        status_code=413,
                    )
                pcm = reader.readframes(frames)
        except (wave.Error, EOFError) as exc:
            raise HausaAsrError("Audio WAV converti invalide.", code="INVALID_AUDIO") from exc
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0


class HausaAsrService:
    """Modele et processeur charges une seule fois par processus serveur."""

    def __init__(self, settings: HausaAsrSettings | None = None) -> None:
        self.settings = settings or HausaAsrSettings()
        self._pipeline: Any | None = None
        self.load_error: str | None = None

    @property
    def model_source(self) -> str:
        return self.settings.HAUSA_ASR_LOCAL_PATH or self.settings.HAUSA_ASR_MODEL

    def load(self) -> None:
        local = self.settings.HAUSA_ASR_LOCAL_PATH.strip()
        if local and not Path(local).is_dir():
            raise HausaAsrError(
                "HAUSA_ASR_LOCAL_PATH est introuvable.",
                code="MODEL_NOT_FOUND",
                status_code=503,
            )
        try:
            from transformers import pipeline

            options: dict[str, Any] = {
                "task": "automatic-speech-recognition",
                "model": local or self.settings.HAUSA_ASR_MODEL,
                "device": _device_index(self.settings.ASR_DEVICE),
            }
            if local:
                options["local_files_only"] = True
            elif self.settings.HF_TOKEN:
                options["token"] = self.settings.HF_TOKEN
            self._pipeline = pipeline(**options)
            self.load_error = None
        except HausaAsrError:
            raise
        except Exception as exc:
            self.load_error = type(exc).__name__
            raise HausaAsrError(
                "Impossible de charger le modele Hausa ASR.",
                code="MODEL_LOAD_FAILED",
                status_code=503,
            ) from exc

    def transcribe(self, raw: bytes, filename: str) -> Transcription:
        samples = _decode_audio(raw, filename, self.settings)
        if self._pipeline is None:
            self.load()
        started = perf_counter()
        try:
            result = self._pipeline(
                {"array": samples, "sampling_rate": self.settings.ASR_SAMPLE_RATE}
            )
            text = str(result.get("text", "")).strip()
        except Exception as exc:
            raise HausaAsrError(
                "Echec de transcription Hausa.", code="INFERENCE_FAILED", status_code=503
            ) from exc
        if not text:
            raise HausaAsrError("Aucune parole Hausa comprise.", code="EMPTY_TRANSCRIPTION")
        return Transcription(
            text=text,
            latency_ms=int((perf_counter() - started) * 1_000),
            model_version=self.model_source,
        )


__all__ = [
    "HausaAsrError",
    "HausaAsrService",
    "HausaAsrSettings",
    "SUPPORTED_AUDIO_EXTENSIONS",
    "Transcription",
]
