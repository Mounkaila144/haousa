"""Application ASR Hausa deployable par Uvicorn/ASGI."""

from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
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
        "grammar_version": service.grammar_version,
    }


@app.post("/transcribe")
async def transcribe(
    audio: Annotated[UploadFile, File()],
    _authorized: Annotated[None, Depends(authorize)],
) -> JSONResponse:
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
            "acoustic_score": result.acoustic_score,
            "candidates": [{"text": text, "score": score} for text, score in result.candidates],
            "latency_ms": result.latency_ms,
            "model_version": result.model_version,
            "grammar_version": result.grammar_version,
        }
    )


__all__ = ["app", "health", "service", "settings", "transcribe"]
