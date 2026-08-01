#!/usr/bin/env python
"""Serveur local du modele NCAIR1/Hausa-ASR, contrat POST /transcribe."""

from __future__ import annotations

import argparse
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from app.hausa_asr import HausaAsrError, HausaAsrService, HausaAsrSettings
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

settings = HausaAsrSettings()
service = HausaAsrService(settings)
logger = logging.getLogger("hausa_asr")


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
        "grammar_version": "2.0.0-hausa",
    }


@app.post("/transcribe")
async def transcribe(
    audio: Annotated[UploadFile, File()],
    _authorized: Annotated[None, Depends(authorize)],
) -> JSONResponse:
    try:
        result = service.transcribe(await audio.read(), audio.filename or "audio.wav")
    except HausaAsrError as exc:
        logger.exception("Echec de transcription Hausa ASR (%s)", exc.code)
        return JSONResponse(
            {"success": False, "language": "hausa", "error": exc.code, "message": str(exc)},
            status_code=exc.status_code,
        )
    return JSONResponse(
        {
            "success": True,
            "language": "hausa",
            "text": result.text,
            "acoustic_score": 1.0,
            "candidates": [],
            "latency_ms": result.latency_ms,
            "model_version": result.model_version,
            "grammar_version": "2.0.0-hausa",
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
