"""Tests d'intégration du pipeline POST /api/v1/recognize (story 2.3)."""

from __future__ import annotations

import wave
from io import BytesIO
from time import sleep
from uuid import UUID

import hausa_numbers
import pytest
from app.asr.base import AsrResult, AudioInput, Candidate, SpeechRecognizer
from app.asr.factory import get_recognizer
from app.asr.mock import MockRecognizer
from app.config import get_settings
from app.main import app
from app.pipeline.audio import MAX_AUDIO_SIZE
from fastapi.testclient import TestClient

client = TestClient(app)
ANON_ID = "00000000-0000-4000-8000-000000000001"


def make_wav(
    *,
    frame_count: int = 1_600,
    channels: int = 1,
    sample_rate: int = 16_000,
) -> bytes:
    """Construit un WAV PCM16 silencieux valide entièrement en mémoire."""

    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(b"\x00\x00" * frame_count * channels)
    return output.getvalue()


@pytest.fixture
def mock_recognizer() -> MockRecognizer:
    recognizer = MockRecognizer()
    app.dependency_overrides[get_recognizer] = lambda: recognizer
    try:
        yield recognizer
    finally:
        app.dependency_overrides.pop(get_recognizer, None)


def post_audio(
    *,
    audio: bytes | None = None,
    mime_type: str = "audio/wav",
    anon_id: str = ANON_ID,
) -> object:
    return client.post(
        "/api/v1/recognize",
        files={"audio": ("test.wav", make_wav() if audio is None else audio, mime_type)},
        data={"anon_id": anon_id},
    )


class CandidateRecognizer(MockRecognizer):
    def transcribe(self, audio: AudioInput) -> AsrResult:
        result = super().transcribe(audio)
        return result.model_copy(
            update={
                "candidates": [
                    Candidate(
                        number=450,
                        text=hausa_numbers.format_money(450),
                        score=0.7,
                    )
                ]
            }
        )


class FailingRecognizer:
    @property
    def model_version(self) -> str:
        return "failing-1.0.0"

    def transcribe(self, audio: AudioInput) -> AsrResult:
        raise RuntimeError(f"private audio: {audio.data!r}")


class SlowRecognizer(MockRecognizer):
    def transcribe(self, audio: AudioInput) -> AsrResult:
        sleep(0.05)
        return super().transcribe(audio)


class TestRecognizePipeline:
    def test_valid_number_recognition(self, mock_recognizer: MockRecognizer) -> None:
        canonical = hausa_numbers.format_money(500)
        mock_recognizer.set_text(canonical, acoustic_score=0.95)

        response = post_audio()

        assert response.status_code == 200
        body = response.json()
        # `ɗari` vaut 500 F : la reconnaissance rend un MONTANT, pas un numeral.
        assert body["recognized_number"] == 500
        assert body["hausa_text"] == canonical
        assert body["normalized_text"] == canonical
        assert body["confidence"] == pytest.approx(0.9825)
        assert body["decision"] == "accept"
        assert body["alternatives"] == []
        assert body["model_version"] == "mock-1.0.0"
        assert body["grammar_version"] == hausa_numbers.load_lexicon().grammar_version
        assert body["latency_asr_ms"] == 50
        assert body["latency_total_ms"] >= body["latency_asr_ms"]
        # `ɗari` se prononce comme il s'écrit : rien à substituer.
        assert body["spoken_text"] == ""

    def test_lone_number_carries_its_spoken_form(self, mock_recognizer: MockRecognizer) -> None:
        """Un « nombre seul » expose sa forme parlée (régression : champ absent).

        Sans ``spoken_text`` au niveau racine, la forme calculée par le pipeline
        n'avait aucun moyen d'atteindre le mobile — seules les opérations, qui
        portent leur propre champ, étaient prononcées correctement. L'écran
        Résultat lisait alors ``jikka`` tel quel, que la synthèse rend « jika ».
        """
        canonical = hausa_numbers.format_money(1_000)
        mock_recognizer.set_text(canonical, acoustic_score=0.95)

        response = post_audio()

        assert response.status_code == 200
        body = response.json()
        assert body["recognized_number"] == 1_000
        assert body["hausa_text"] == "jikka"
        # Le CHAMP doit exister : c'est lui qui manquait, et la forme parlée
        # calculée par le pipeline n'avait alors aucun moyen d'atteindre le
        # mobile. Sa valeur est vide aujourd'hui parce que le lexique ne
        # déclare plus aucune forme parlée : la voix est entraînée sur la forme
        # écrite, `jikka` part donc tel quel à la synthèse.
        assert "spoken_text" in body
        assert body["spoken_text"] == ""

    def test_non_numeric_text_never_invents_number(self, mock_recognizer: MockRecognizer) -> None:
        mock_recognizer.set_text("salaam", acoustic_score=0.8)

        response = post_audio()

        assert response.status_code == 200
        body = response.json()
        assert body["recognized_number"] is None
        assert body["hausa_text"] == ""
        assert body["normalized_text"] == "salaam"
        assert 0.0 < body["confidence"] < 0.5
        assert body["decision"] == "repeat"

    @pytest.mark.parametrize("amount", [0, 5, 15, 25, 210, 500, 4_995])
    def test_multiple_valid_numbers(self, mock_recognizer: MockRecognizer, amount: int) -> None:
        """Montants en francs CFA, tous multiples de l'unite de compte de 5 F."""
        mock_recognizer.set_text(hausa_numbers.format_money(amount))

        response = post_audio()

        assert response.status_code == 200
        assert response.json()["recognized_number"] == amount

    def test_normalization_precedes_parsing(self, mock_recognizer: MockRecognizer) -> None:
        canonical = hausa_numbers.format_money(500)
        mock_recognizer.set_text(f"  {canonical.upper()}! ")

        response = post_audio()

        assert response.status_code == 200
        assert response.json()["normalized_text"] == canonical
        assert response.json()["recognized_number"] == 500

    def test_asr_candidates_are_exposed_as_alternatives(self) -> None:
        recognizer = CandidateRecognizer()
        recognizer.set_text(hausa_numbers.format_money(500))
        app.dependency_overrides[get_recognizer] = lambda: recognizer
        try:
            response = post_audio()
        finally:
            app.dependency_overrides.pop(get_recognizer, None)

        assert response.status_code == 200
        assert response.json()["alternatives"] == [
            {
                # `tasa'in` = 90 unites de 5 F = 450 F.
                "number": 450,
                "hausa_text": hausa_numbers.format_money(450),
                # Se prononce comme il s'écrit : le champ reste vide.
                "spoken_text": "",
                "score": 0.7,
            }
        ]


class TestInputValidation:
    def test_missing_audio_file(self, mock_recognizer: MockRecognizer) -> None:
        response = client.post("/api/v1/recognize", data={"anon_id": ANON_ID})
        assert response.status_code == 422

    def test_missing_anon_id(self, mock_recognizer: MockRecognizer) -> None:
        response = client.post(
            "/api/v1/recognize",
            files={"audio": ("test.wav", b"audio", "audio/wav")},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("anon_id", ["", "not-a-uuid", "123"])
    def test_invalid_anon_id_is_rejected(
        self, mock_recognizer: MockRecognizer, anon_id: str
    ) -> None:
        response = post_audio(anon_id=anon_id)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert "traceback" not in response.text.lower()

    def test_anon_id_is_a_valid_uuid(self, mock_recognizer: MockRecognizer) -> None:
        mock_recognizer.set_text(hausa_numbers.generate(1))
        response = post_audio()
        assert response.status_code == 200
        assert UUID(ANON_ID)

    def test_file_too_large(self, mock_recognizer: MockRecognizer) -> None:
        response = post_audio(audio=b"x" * (2_000_001))
        assert response.status_code == 413
        assert "too large" in response.text.lower()

    def test_empty_file(self, mock_recognizer: MockRecognizer) -> None:
        response = post_audio(audio=b"")
        assert response.status_code == 422
        assert "empty" in response.text.lower()

    @pytest.mark.parametrize("mime_type", ["audio/mpeg", "application/octet-stream", "text/plain"])
    def test_invalid_mime_type(self, mock_recognizer: MockRecognizer, mime_type: str) -> None:
        response = post_audio(mime_type=mime_type)
        assert response.status_code == 422
        assert "invalid audio format" in response.text.lower()

    @pytest.mark.parametrize("mime_type", ["audio/wav", "audio/x-wav"])
    def test_accepted_mime_types(self, mock_recognizer: MockRecognizer, mime_type: str) -> None:
        mock_recognizer.set_text(hausa_numbers.generate(1))
        response = post_audio(mime_type=mime_type)
        assert response.status_code == 200

    def test_boundary_file_size(self, mock_recognizer: MockRecognizer) -> None:
        mock_recognizer.set_text(hausa_numbers.generate(1))
        boundary_wav = make_wav(frame_count=(MAX_AUDIO_SIZE - 44) // 2)
        assert len(boundary_wav) == MAX_AUDIO_SIZE

        response = post_audio(audio=boundary_wav)
        assert response.status_code == 200


class TestErrorHandling:
    def test_internal_error_is_safe_and_structured(self) -> None:
        recognizer: SpeechRecognizer = FailingRecognizer()
        app.dependency_overrides[get_recognizer] = lambda: recognizer
        try:
            response = post_audio()
        finally:
            app.dependency_overrides.pop(get_recognizer, None)

        assert response.status_code == 500
        body = response.json()
        assert set(body) == {"error"}
        assert body["error"]["code"] == "INTERNAL"
        assert UUID(body["error"]["request_id"])
        assert body["error"]["timestamp"].endswith("Z")
        serialized = response.text.lower()
        assert "secret-audio-content" not in serialized
        assert "runtimeerror" not in serialized
        assert "traceback" not in serialized

    def test_timeout_is_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        recognizer = SlowRecognizer()
        recognizer.set_text(hausa_numbers.generate(1))
        app.dependency_overrides[get_recognizer] = lambda: recognizer
        monkeypatch.setattr(get_settings(), "ASR_TIMEOUT_SECONDS", 0.001)
        try:
            response = post_audio()
        finally:
            app.dependency_overrides.pop(get_recognizer, None)

        assert response.status_code == 504
        assert response.json()["error"]["code"] == "TIMEOUT"
        assert UUID(response.json()["error"]["request_id"])

    def test_validation_error_has_no_stack_trace(self, mock_recognizer: MockRecognizer) -> None:
        response = client.post("/api/v1/recognize", data={})
        assert response.status_code == 422
        assert "traceback" not in response.text.lower()
