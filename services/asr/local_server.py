#!/usr/bin/env python
"""Serveur local du modele NCAIR1/Hausa-ASR, contrat POST /transcribe."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from typing import Annotated

from app.hausa_asr import HausaAsrError, HausaAsrService, HausaAsrSettings
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

settings = HausaAsrSettings()
service = HausaAsrService(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Le modele gate peut ne pas etre accessible sur une machine non configuree.
    # Le serveur reste observable; /transcribe renverra alors une erreur 503.
    try:
        service.load()
    except HausaAsrError:
        pass
    yield


app = FastAPI(title="Hausa ASR", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok" if service._pipeline is not None else "degraded",
        "language": "hausa",
        "model": service.model_source,
        "model_loaded": service._pipeline is not None,
        "load_error": service.load_error,
    }


@app.post("/transcribe")
async def transcribe(audio: Annotated[UploadFile, File()]) -> JSONResponse:
    try:
        result = service.transcribe(await audio.read(), audio.filename or "audio.wav")
    except HausaAsrError as exc:
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
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
