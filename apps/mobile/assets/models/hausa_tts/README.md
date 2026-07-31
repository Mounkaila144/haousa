# Modèle TTS hausa embarqué

- Source : `adab-tech/murya-piper-hausa-tts`
- Révision figée : `7eccd91ec0dc154c789b778c924b89f59a0dbccb`
- Licence du modèle : MIT
- Voix obligatoire : `M3` (résolue dynamiquement dans `speaker_id_map`)
- Runtime mobile : `sherpa_onnx`

Le modèle Piper a été entraîné avec `phoneme_type: text` (graphèmes hausa). Il
n'utilise donc ni eSpeak, ni lexique phonétique. `tokens.txt` est dérivé de
`phoneme_id_map` et l'ONNX reçoit le frontend Sherpa `characters`. Embarquer
`espeak-ng-data` serait à la fois inutile et incorrect pour ce modèle ; eSpeak
ne fournit par ailleurs pas de voix hausa utilisée par cet entraînement.

`model.onnx.json` reste le fichier amont intact et constitue la source de vérité
pour les locuteurs et les jetons. `asset_manifest.json` permet à l'application
de ne recopier le modèle de 73 Mio dans son stockage privé que lorsqu'il change.

La préparation est reproductible depuis `apps/mobile/` :

```sh
uv run --with onnx==1.17.0 python tool/prepare_hausa_tts_model.py
```
