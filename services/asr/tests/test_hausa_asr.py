from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "hausa_asr.py"
SPEC = importlib.util.spec_from_file_location("hausa_asr_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
hausa_asr = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = hausa_asr
SPEC.loader.exec_module(hausa_asr)

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
def test_loaded_pipeline_is_reused():
    service = HausaAsrService(HausaAsrSettings())
    calls = []

    def fake_pipeline(value):
        calls.append(value)
        return {"text": "ashirin da uku a kara goma sha biyar"}

    service._pipeline = fake_pipeline
    first = service.transcribe(wav_bytes(), "one.wav")
    second = service.transcribe(wav_bytes(), "two.wav")
    assert first.text == second.text
    assert len(calls) == 2
    assert service._pipeline is fake_pipeline
