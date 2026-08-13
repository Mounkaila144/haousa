# Voix hausa (Piper / sherpa-onnx)

**Ce dossier est volontairement vide.** Le modèle n'est pas dans le dépôt : il
est produit par la chaîne d'entraînement et déposé ici.

Tant qu'il manque, `HausaTtsEngine` échoue proprement à l'initialisation et
l'application reste muette. C'est un état transitoire assumé, le temps que la
voix soit entraînée sur les enregistrements du locuteur.

## Ce qu'il faut déposer

```text
model.onnx           le réseau exporté puis annoté pour sherpa-onnx
model.onnx.json      sa configuration Piper
tokens.txt           la table de symboles
asset_manifest.json  tailles attendues, contrôlées à l'installation
```

`model.onnx` est ignoré par git (plusieurs dizaines de Mo) ; les trois autres
sont versionnés.

## Comment l'obtenir

Voir `entrainement/tts_training/README.md`. En résumé : préparer le corpus,
entraîner sur Colab, exporter en ONNX, puis convertir avec
`convert_tts_for_sherpa.py`.

## Contraintes que le moteur vérifie au chargement

- `num_speakers` vaut **1** — la voix est mono-locuteur. Un modèle
  multi-locuteurs est refusé plutôt que d'en choisir un au hasard.
- `phoneme_type` vaut **`text`** : le texte est lu en caractères, sans
  phonémiseur. espeak-ng ne connaît pas le hausa.
- Chaque caractère envoyé à la synthèse doit exister dans `phoneme_id_map`,
  sinon il serait ignoré en silence.
