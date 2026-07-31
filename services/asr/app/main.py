"""Application ASR Hausa deployable par Uvicorn/ASGI."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from .hausa_asr import HausaAsrError, HausaAsrService, HausaAsrSettings

settings = HausaAsrSettings()
service = HausaAsrService(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        service.load()
    except HausaAsrError:
        # Un modele gate mal configure rend l'inference indisponible, pas la
        # sonde. Cela permet de diagnostiquer HF_TOKEN sans boucle de restart.
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


__all__ = ["app", "health", "service", "settings", "transcribe"]
