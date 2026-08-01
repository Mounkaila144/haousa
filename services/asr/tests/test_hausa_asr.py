from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import types
import wave
from pathlib import Path

import numpy as np
import pytest

# Le module est chargé sous un nom de paquet **synthétique** : le nom `app`
# entrerait en collision avec le paquet `app` de services/api, mais un chargement
# à plat casserait les imports relatifs (`from .decoding import …`). On recrée
# donc un paquet minimal pointant sur services/asr/app.
PACKAGE = "hausa_asr_under_test"
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
_load("vad")
hausa_asr = _load("hausa_asr")

HausaAsrError = hausa_asr.HausaAsrError
HausaAsrService = hausa_asr.HausaAsrService
HausaAsrSettings = hausa_asr.HausaAsrSettings
SUPPORTED_AUDIO_EXTENSIONS = hausa_asr.SUPPORTED_AUDIO_EXTENSIONS
_decode_audio = hausa_asr._decode_audio
_device_index = hausa_asr._device_index


def wav_bytes(seconds: float = 0.05, sample_rate: int = 16_000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(np.zeros(int(seconds * sample_rate), dtype="<i2").tobytes())
    return output.getvalue()


def test_required_defaults():
    settings = HausaAsrSettings()
    assert settings.HAUSA_ASR_MODEL == "NCAIR1/Hausa-ASR"
    assert settings.ASR_SAMPLE_RATE == 16_000
    assert settings.ASR_MAX_AUDIO_SECONDS == 30
    assert SUPPORTED_AUDIO_EXTENSIONS == {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}


def test_empty_and_unknown_audio_are_explicit():
    settings = HausaAsrSettings()
    with pytest.raises(HausaAsrError) as empty:
        _decode_audio(b"", "audio.wav", settings)
    assert empty.value.code == "EMPTY_AUDIO"
    with pytest.raises(HausaAsrError) as unsupported:
        _decode_audio(b"data", "audio.txt", settings)
    assert unsupported.value.code == "UNSUPPORTED_AUDIO"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_wav_is_converted_to_mono_16khz_and_duration_checked():
    samples = _decode_audio(wav_bytes(), "audio.wav", HausaAsrSettings())
    assert samples.dtype == np.float32
    assert len(samples) == 800
    with pytest.raises(HausaAsrError) as too_long:
        _decode_audio(
            wav_bytes(seconds=0.2),
            "audio.wav",
            HausaAsrSettings(ASR_MAX_AUDIO_SECONDS=0.1),
        )
    assert too_long.value.code == "AUDIO_TOO_LONG"


def test_cpu_can_be_forced():
    assert _device_index("cpu") == -1


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_loaded_model_is_reused(monkeypatch):
    """Le modèle est chargé une fois par processus, jamais par requête.

    Recharger 967 Mo de poids à chaque appel ajouterait ~17 s à chaque requête ;
    le test garde donc la garantie que ``transcribe`` ne rappelle pas ``load``.
    """
    # VAD desactive : ce test porte sur la reutilisation du modele, et le WAV
    # de test est un silence numerique que le VAD refuserait a juste titre.
    service = HausaAsrService(HausaAsrSettings(ASR_ENABLE_VAD=False))
    loads = []

    def fake_load():
        loads.append(1)
        service._model = object()

    monkeypatch.setattr(service, "load", fake_load)
    monkeypatch.setattr(
        service,
        "_run_inference",
        lambda samples: hausa_asr.Transcription(
            text="ashirin da uku",
            latency_ms=1,
            model_version=service.model_source,
            acoustic_score=0.9,
        ),
    )

    first = service.transcribe(wav_bytes(), "one.wav")
    second = service.transcribe(wav_bytes(), "two.wav")
    assert first.text == second.text == "ashirin da uku"
    assert len(loads) == 1  # chargé au premier appel, réutilisé ensuite
