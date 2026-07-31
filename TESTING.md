# Tests

## Python

```bash
uv sync
uv run pytest
uv run ruff check .
uv run black --check .
```

La suite couvre toutes les valeurs demandees, les alias de 90, les grandes
echelles, les quatre operations, la division par zero, les phrases incompletes,
les operateurs multiples et la securite audio. Le vrai modele n'est pas
telecharge en CI; son smoke test necessite un `HF_TOKEN` et un fichier Hausa
consenti.

## Flutter

```bash
cd apps/mobile
flutter pub get
flutter analyze
flutter test
```

## Verification manuelle

1. demarrer ASR puis API ;
2. verifier `curl http://127.0.0.1:8001/health` et
   `curl http://127.0.0.1:8000/health` ;
3. essayer les quatre phrases de `HAUSA_NUMBER_RULES.md`/tests ;
4. confirmer qu'aucun audio non consenti ne reste dans les repertoires
   temporaires ou `storage/audio`.
