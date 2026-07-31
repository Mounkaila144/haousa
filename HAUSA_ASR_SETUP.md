# Installation du service Hausa ASR

Le modele officiel configure est `NCAIR1/Hausa-ASR` (Whisper Small). Son depot
Hugging Face est gate : se connecter, accepter les conditions et creer un jeton
de lecture. Ne jamais committer ce jeton.

## Installation et démarrage

```bash
uv venv asrenv
uv pip install --python asrenv/bin/python -e services/asr
HF_TOKEN=hf_... asrenv/bin/python -m uvicorn app.main:app \
  --app-dir services/asr --host 127.0.0.1 --port 8001
```

`ffmpeg` doit également être disponible dans le `PATH`.

## Chargement depuis Hugging Face

```env
HAUSA_ASR_MODEL=NCAIR1/Hausa-ASR
HAUSA_ASR_LOCAL_PATH=
HF_TOKEN=hf_...
ASR_DEVICE=auto
```

## Copie locale

Apres un telechargement autorise, placer tous les fichiers du modele dans un
repertoire serveur et definir `HAUSA_ASR_LOCAL_PATH`. Cette option est
prioritaire et active `local_files_only=True`; aucun acces reseau n'est tente.

`ASR_DEVICE=auto` choisit CUDA si disponible, sinon CPU. `cuda` refuse de
demarrer sans GPU; `cpu` force le processeur.

## Audio

WAV, MP3, M4A, AAC, OGG et FLAC sont convertis par `ffmpeg` en PCM16 mono
16 kHz. `ASR_MAX_AUDIO_SECONDS` borne la duree (30 s par defaut). Les fichiers
temporaires sont detruits apres chaque requete et ne sont jamais archives.

## Erreurs frequentes

- `MODEL_LOAD_FAILED` : conditions non acceptees, jeton absent/invalide ou
  poids incomplets ;
- `FFMPEG_MISSING` : installer `ffmpeg` ;
- `UNSUPPORTED_AUDIO`/`INVALID_AUDIO` : extension ou conteneur invalide ;
- `AUDIO_TOO_LONG` : raccourcir l'enregistrement ou changer la limite ;
- `CUDA_UNAVAILABLE` : choisir `auto`/`cpu` ou installer CUDA correctement.
