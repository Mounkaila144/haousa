#!/usr/bin/env python
"""Serveur local du modele NCAIR1/Hausa-ASR, contrat POST /transcribe."""

from __future__ import annotations

import argparse
import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated

from app.hausa_asr import HausaAsrError, HausaAsrService, HausaAsrSettings
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

settings = HausaAsrSettings()
service = HausaAsrService(settings)
logger = logging.getLogger("hausa_asr")

#: Un seul passage modèle à la fois. Le modèle est un objet partagé et le calcul
#: est purement CPU : deux inférences simultanées ne vont pas deux fois plus
#: vite, elles se disputent les mêmes 2 fils et doublent la latence des deux.
_inference_lock = asyncio.Semaphore(1)

#: Requêtes tolérées en attente derrière l'inférence en cours. Au-delà, on
#: répond BUSY tout de suite : accepter une requête qu'on sait déjà condamnée à
#: dépasser le délai de l'appelant ne fait qu'allonger la file pour les
#: suivantes. Deux workers API × une requête chacun = 2.
_MAX_QUEUE = 2
_queue_depth = 0


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Le modele gate peut ne pas etre accessible sur une machine non configuree.
    # Le serveur reste observable; /transcribe renverra alors une erreur 503.
    try:
        service.load()
    except HausaAsrError:
        logger.exception("Echec du chargement initial du modele Hausa ASR")
    yield


app = FastAPI(title="Hausa ASR", version="1.0.0", lifespan=lifespan)


def authorize(authorization: Annotated[str | None, Header()] = None) -> None:
    """Protège le service interne avec le secret partagé API ↔ ASR."""
    token = settings.ASR_ENDPOINT_TOKEN
    if token and not hmac.compare_digest(authorization or "", f"Bearer {token}"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@app.get("/health")
def health(_authorized: Annotated[None, Depends(authorize)]) -> dict[str, object]:
    return {
        "status": "ok" if service._pipeline is not None else "degraded",
        "language": "hausa",
        "model": service.model_source,
        "model_loaded": service._pipeline is not None,
        "load_error": service.load_error,
        # Version du lexique **réellement chargé** par ce processus. Annoncer une
        # constante que le service n'a pas lue rendait la garde de dérive de
        # grammaire côté API structurellement incapable de détecter une dérive.
        "grammar_version": service.grammar_version,
        "queue_depth": _queue_depth,
    }


@app.post("/transcribe")
async def transcribe(
    audio: Annotated[UploadFile, File()],
    _authorized: Annotated[None, Depends(authorize)],
) -> JSONResponse:
    global _queue_depth

    if _queue_depth >= _MAX_QUEUE:
        # Surcharge explicite plutôt que file sans fond : l'appelant peut
        # réessayer, et la latence des requêtes en cours reste bornée.
        return JSONResponse(
            {
                "success": False,
                "language": "hausa",
                "error": "BUSY",
                "message": "Le service de reconnaissance est saturé.",
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    payload = await audio.read()
    filename = audio.filename or "audio.wav"
    _queue_depth += 1
    queued_at = perf_counter()
    try:
        async with _inference_lock:
            queue_wait_ms = int((perf_counter() - queued_at) * 1_000)
            # L'inférence est synchrone et CPU-bound : l'exécuter dans la boucle
            # événementielle bloquerait tout le serveur, y compris /health.
            result = await asyncio.to_thread(service.transcribe, payload, filename)
    except HausaAsrError as exc:
        logger.warning("Echec de transcription Hausa ASR (%s)", exc.code)
        return JSONResponse(
            {"success": False, "language": "hausa", "error": exc.code, "message": str(exc)},
            status_code=exc.status_code,
        )
    finally:
        _queue_depth -= 1

    logger.info(
        "transcribe ok queue_wait_ms=%d decode_ms=%d inference_ms=%d "
        "original_s=%.2f kept_s=%.2f trimmed_s=%.2f score=%.3f",
        queue_wait_ms,
        result.decode_ms,
        result.inference_ms,
        result.original_seconds,
        result.kept_seconds,
        result.trimmed_seconds,
        result.acoustic_score,
    )
    return JSONResponse(
        {
            "success": True,
            "language": "hausa",
            "text": result.text,
            "acoustic_score": result.acoustic_score,
            "candidates": [{"text": text, "score": score} for text, score in result.candidates],
            "latency_ms": result.latency_ms,
            "model_version": result.model_version,
            "grammar_version": result.grammar_version,
            "queue_wait_ms": queue_wait_ms,
            "decode_ms": result.decode_ms,
            "inference_ms": result.inference_ms,
            "trimmed_seconds": round(result.trimmed_seconds, 3),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
