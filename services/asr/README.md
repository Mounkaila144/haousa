# Service Hausa ASR

Service ASGI pour `NCAIR1/Hausa-ASR`. Le modele Whisper est charge une fois au
demarrage. Si l'acces au depot gate echoue, `/health` indique `degraded` et les
transcriptions renvoient une erreur explicite sans faire tomber le processus.

```bash
uv venv asrenv
uv pip install --python asrenv/bin/python -e services/asr
HF_TOKEN=... asrenv/bin/python -m uvicorn app.main:app \
  --app-dir services/asr --host 127.0.0.1 --port 8001
```

Variables : `HAUSA_ASR_MODEL`, `HAUSA_ASR_LOCAL_PATH`, `HF_TOKEN`,
`ASR_DEVICE`, `ASR_SAMPLE_RATE` et `ASR_MAX_AUDIO_SECONDS`. Voir
`../../HAUSA_ASR_SETUP.md`.

`POST /transcribe` recoit un champ multipart `audio`. La reponse conserve les
champs attendus par l'API (`text`, `acoustic_score`, `candidates`,
`latency_ms`, `model_version`, `grammar_version`) et ajoute `success` et
`language=hausa`.
