"""Service d'inference pour le modele Whisper Hausa de NCAIR."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .decoding import ConstrainedDecoder, DecoderConfig, GrammarConstraint

SUPPORTED_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"})

#: Tokens spéciaux du préfixe forcé. Les expliciter supprime la détection
#: automatique de langue : elle coûtait une passe complète (~40 % de la latence
#: mesurée) pour redécouvrir à chaque requête une langue qu'on connaît.
_PREFIX_TOKENS = ("<|startoftranscript|>", "<|ha|>", "<|transcribe|>", "<|notimestamps|>")


class HausaAsrError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class HausaAsrSettings(BaseSettings):
    HAUSA_ASR_MODEL: str = "NCAIR1/Hausa-ASR"
    HAUSA_ASR_LOCAL_PATH: str = ""
    HF_TOKEN: str = ""
    ASR_ENDPOINT_TOKEN: str = ""
    ASR_DEVICE: str = "auto"
    ASR_SAMPLE_RATE: int = Field(default=16_000, ge=8_000, le=48_000)
    ASR_MAX_AUDIO_SECONDS: float = Field(default=30.0, gt=0.0, le=300.0)
    #: Largeur du faisceau du décodage contraint.
    ASR_BEAM_WIDTH: int = Field(default=4, ge=1, le=16)
    #: Nombre d'hypothèses remontées à l'API (``AsrResult.candidates``).
    ASR_NBEST: int = Field(default=3, ge=1, le=10)
    #: Seuil d'abstention du décodeur. ``0.0`` = ne jamais s'abstenir : le
    #: décodeur expose seulement le signal, et la confiance composite de l'API
    #: tranche. Sur les 10 énoncés réels, 0.40 sépare les opérations réelles
    #: (≥ 0,43) de celles qui contiennent un mot hors grammaire (≤ 0,37) — marge
    #: trop mince pour en faire un défaut sans calibration plus large.
    ASR_REJECT_THRESHOLD: float = Field(default=0.0, ge=0.0, le=1.0)
    #: Élagage des silences de bord avant inférence (le coût du modèle est
    #: linéaire en nombre de trames).
    ASR_ENABLE_VAD: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@dataclass(frozen=True)
class Transcription:
    text: str
    latency_ms: int
    model_version: str
    #: Confiance acoustique **réelle** dans ``[0, 1]`` — plus jamais codée en dur.
    acoustic_score: float = 1.0
    #: Hypothèses alternatives grammaticales ``(texte, score)``.
    candidates: tuple[tuple[str, float], ...] = ()
    #: Version du lexique réellement chargée par ce processus.
    grammar_version: str = ""
    #: Transcription libre (non grammaticale) — diagnostic uniquement.
    free_text: str = ""
    #: Le décodeur s'est-il abstenu faute de ressembler à une opération ?
    rejected: bool = False
    #: Détail des durées, pour la mesure et les journaux.
    decode_ms: int = 0
    inference_ms: int = 0
    original_seconds: float = 0.0
    kept_seconds: float = 0.0

    @property
    def trimmed_seconds(self) -> float:
        return max(0.0, self.original_seconds - self.kept_seconds)


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


class _WhisperLogprobSource:
    """``LogprobSource`` adossée au décodeur Whisper, avec cache clé/valeur.

    Sans ce cache, chaque pas rejouerait tout le préfixe **et** la
    cross-attention sur les 1 500 trames d'encodeur, pour chaque faisceau :
    mesuré à 30–60 s par énoncé, contre 5–9 s ici. C'est la différence entre un
    décodage contraint inutilisable et un décodage plus rapide que l'existant.
    """

    def __init__(self, model: Any, encoder_outputs: Any, prefix_ids: list[int]) -> None:
        import torch
        from transformers.cache_utils import DynamicCache, EncoderDecoderCache

        self._torch = torch
        self._model = model
        self._encoder_outputs = encoder_outputs
        cache = EncoderDecoderCache(DynamicCache(), DynamicCache())
        with torch.no_grad():
            output = model(
                decoder_input_ids=torch.tensor([prefix_ids]),
                encoder_outputs=type(encoder_outputs)(
                    last_hidden_state=encoder_outputs.last_hidden_state
                ),
                past_key_values=cache,
                use_cache=True,
            )
        self._cache = output.past_key_values
        self._logprobs = torch.log_softmax(output.logits[:, -1].float(), dim=-1)

    def start(self):
        return self._logprobs[0]

    def extend(self, parents, tokens):
        torch = self._torch
        self._cache.reorder_cache(torch.tensor(list(parents)))
        expanded = type(self._encoder_outputs)(
            last_hidden_state=self._encoder_outputs.last_hidden_state.expand(len(tokens), -1, -1)
        )
        with torch.no_grad():
            output = self._model(
                decoder_input_ids=torch.tensor([[int(t)] for t in tokens]),
                encoder_outputs=expanded,
                past_key_values=self._cache,
                use_cache=True,
            )
        self._cache = output.past_key_values
        return torch.log_softmax(output.logits[:, -1].float(), dim=-1)


class HausaAsrService:
    """Modele et processeur charges une seule fois par processus serveur."""

    def __init__(self, settings: HausaAsrSettings | None = None) -> None:
        self.settings = settings or HausaAsrSettings()
        self._model: Any | None = None
        self._processor: Any | None = None
        self._decoder: ConstrainedDecoder | None = None
        self._prefix_ids: list[int] = []
        self._eot_id: int = 0
        self.grammar_version: str = ""
        self.load_error: str | None = None

    @property
    def _pipeline(self) -> Any | None:
        """Compatibilité : l'état « modèle chargé » consulté par ``/health``."""
        return self._model

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
            import hausa_numbers
            from hausa_numbers.grammar import build_calculator_grammar
            from transformers import WhisperForConditionalGeneration, WhisperProcessor

            source = local or self.settings.HAUSA_ASR_MODEL
            options: dict[str, Any] = {}
            # Un chemin local, combine a HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE
            # dans l'unite systemd, suffit a interdire tout telechargement.
            if not local and self.settings.HF_TOKEN:
                options["token"] = self.settings.HF_TOKEN
            self._processor = WhisperProcessor.from_pretrained(source, **options)
            self._model = WhisperForConditionalGeneration.from_pretrained(source, **options)
            self._model.eval()
            if _device_index(self.settings.ASR_DEVICE) >= 0:
                self._model.to("cuda")

            tokenizer = self._processor.tokenizer
            self._prefix_ids = [tokenizer.convert_tokens_to_ids(t) for t in _PREFIX_TOKENS]
            self._eot_id = tokenizer.convert_tokens_to_ids("<|endoftext|>")

            # La version de grammaire est celle du lexique **réellement chargé**
            # par ce processus — jamais une constante recopiée dans le service.
            self.grammar_version = hausa_numbers.load_lexicon().grammar_version
            grammar = build_calculator_grammar()
            constraint = GrammarConstraint(
                grammar,
                lambda text: tokenizer.encode(text, add_special_tokens=False),
                eot_id=self._eot_id,
            )
            self._decoder = ConstrainedDecoder(
                constraint,
                DecoderConfig(
                    beam_width=self.settings.ASR_BEAM_WIDTH,
                    nbest=self.settings.ASR_NBEST,
                    reject_threshold=self.settings.ASR_REJECT_THRESHOLD,
                ),
            )
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

    def _free_greedy(self, encoder_outputs: Any) -> tuple[str, float, int]:
        """Décodage **libre** : référence de comparaison pour la confiance.

        C'est la borne de ce que le modèle sait faire sur cet audio sans
        contrainte. L'écart avec le chemin contraint mesure ce que la grammaire
        a coûté — donc à quel point l'énoncé s'écarte d'une opération.
        """
        import torch

        source = _WhisperLogprobSource(self._model, encoder_outputs, self._prefix_ids)
        logprobs = source.start()
        ids: list[int] = []
        nll = 0.0
        for _ in range(self._decoder.config.max_steps):
            token = int(torch.argmax(logprobs))
            nll -= float(logprobs[token])
            if token == self._eot_id:
                break
            ids.append(token)
            logprobs = source.extend([0], [token])[0]
        text = self._processor.tokenizer.decode(ids, skip_special_tokens=True).strip()
        return text, nll, max(1, len(ids))

    def transcribe(self, raw: bytes, filename: str) -> Transcription:
        decode_started = perf_counter()
        samples = _decode_audio(raw, filename, self.settings)
        decode_ms = int((perf_counter() - decode_started) * 1_000)
        if self._model is None:
            self.load()

        sample_rate = self.settings.ASR_SAMPLE_RATE
        original_seconds = len(samples) / sample_rate if sample_rate else 0.0
        kept_seconds = original_seconds
        if self.settings.ASR_ENABLE_VAD:
            from .vad import analyse

            trim = analyse(samples, sample_rate)
            if trim.is_silent:
                raise HausaAsrError("Aucune parole Hausa comprise.", code="EMPTY_TRANSCRIPTION")
            samples, kept_seconds = trim.samples, trim.kept_seconds

        transcription = self._run_inference(samples)
        return replace(
            transcription,
            decode_ms=decode_ms,
            original_seconds=original_seconds,
            kept_seconds=kept_seconds,
        )

    def _run_inference(self, samples: np.ndarray) -> Transcription:
        """Encodeur, chemin libre, puis décodage contraint. Sans I/O audio."""
        started = perf_counter()
        try:
            import torch

            features = self._processor(
                samples, sampling_rate=self.settings.ASR_SAMPLE_RATE, return_tensors="pt"
            ).input_features
            with torch.no_grad():
                encoder_outputs = self._model.model.encoder(features)
            free_text, free_nll, free_count = self._free_greedy(encoder_outputs)
            result = self._decoder.decode(
                _WhisperLogprobSource(self._model, encoder_outputs, self._prefix_ids),
                lambda ids: self._processor.tokenizer.decode(
                    list(ids), skip_special_tokens=True
                ).strip(),
                free_neg_log_likelihood=free_nll,
                free_token_count=free_count,
                free_text=free_text,
            )
        except HausaAsrError:
            raise
        except Exception as exc:
            raise HausaAsrError(
                "Echec de transcription Hausa.", code="INFERENCE_FAILED", status_code=503
            ) from exc

        inference_ms = int((perf_counter() - started) * 1_000)
        best = result.best
        # Aucun chemin grammatical, ou coût acoustique au-delà du seuil : on
        # s'abstient comme un ASR en échec. Le pipeline en déduira ``repeat``
        # plutôt qu'un faux calcul (FR21/NFR14).
        if best is None or result.rejected:
            raise HausaAsrError("Aucune parole Hausa comprise.", code="EMPTY_TRANSCRIPTION")

        return Transcription(
            text=best.text,
            latency_ms=inference_ms,
            model_version=self.model_source,
            acoustic_score=best.confidence,
            candidates=tuple(
                (hypothesis.text, hypothesis.confidence) for hypothesis in result.hypotheses[1:]
            ),
            grammar_version=self.grammar_version,
            free_text=free_text,
            rejected=result.rejected,
            inference_ms=inference_ms,
        )


__all__ = [
    "HausaAsrError",
    "HausaAsrService",
    "HausaAsrSettings",
    "SUPPORTED_AUDIO_EXTENSIONS",
    "Transcription",
]
