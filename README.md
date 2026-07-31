# Calculatrice Hausa

Application mobile de calcul vocal en Hausa. Elle enregistre une phrase, la
transcrit avec `NCAIR1/Hausa-ASR`, analyse les nombres et l'operateur de facon
deterministe, calcule le resultat et produit sa forme Hausa canonique.

## Architecture

- `apps/mobile` : Flutter, Riverpod, Dio et TTS Piper/Sherpa-ONNX embarqué.
- `services/api` : FastAPI, orchestration, historique, consentement et stockage.
- `services/asr` : service Whisper Hausa, conversion audio par `ffmpeg`.
- `packages/hausa_numbers` : normalisation, nombres, operations et generation.

L'audio de calcul reste temporaire sauf consentement explicite gere par l'API.
Le service ASR ne conserve jamais les fichiers qu'il convertit.

## Prerequis

- Python 3.11 et `uv` ;
- `ffmpeg` pour WAV, MP3, M4A, AAC, OGG et FLAC ;
- Flutter 3.44+, Android SDK 36 et JDK 17 ;
- acces accepte au modele gate Hugging Face et `HF_TOKEN`, ou copie locale.

## Installation et configuration

```bash
uv sync
cp .env.example .env
uv venv asrenv
uv pip install --python asrenv/bin/python -e services/asr
flutter pub get --directory apps/mobile
```

Accepter les conditions de `NCAIR1/Hausa-ASR` sur Hugging Face, puis renseigner
`HF_TOKEN`. Pour un serveur hors ligne, placer les poids localement et definir
`HAUSA_ASR_LOCAL_PATH`; le chargeur impose alors `local_files_only=True`.

## Demarrage

```bash
# ASR Hausa sur le port 8001 (apres installation dans asrenv, voir ci-dessous)
asrenv/bin/python -m uvicorn app.main:app --app-dir services/asr \
  --host 127.0.0.1 --port 8001

# API sur le port 8000
ASR_MODE=ctc ASR_ENDPOINT_URL=http://127.0.0.1:8001 \
  uv run uvicorn app.main:app --app-dir services/api --host 0.0.0.0 --port 8000

# Mobile, depuis apps/mobile
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
```

Pour developper sans modele, utiliser `ASR_MODE=mock` et `ASR_MOCK_TEXT`.

## Tests

```bash
uv run pytest
uv run ruff check .
uv run black --check .
cd apps/mobile && flutter analyze && flutter test
```

Voir [HAUSA_NUMBER_RULES.md](HAUSA_NUMBER_RULES.md),
[HAUSA_ASR_SETUP.md](HAUSA_ASR_SETUP.md) et [TESTING.md](TESTING.md).

## Limites connues

- Le modele est gate et sa licence impose de verifier l'usage envisage.
- Le modèle TTS embarqué ajoute environ 73 Mio au paquet mobile. Il fonctionne
  sans réseau et utilise exclusivement la voix M3 ; le texte n'est jamais
  envoyé au backend pour être prononcé.
- Certaines constructions tres grandes avec plusieurs `da` peuvent etre
  linguistiquement ambigues; le parseur donne la priorite au multiplicateur de
  l'echelle. Cette convention doit etre validee par des locuteurs Hausa.
