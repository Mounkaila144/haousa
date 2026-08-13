# Entraînement de la voix hausa (Piper / VITS)

Chaîne reprise de celle du zarma, qui fonctionne, et adaptée au contexte hausa.
Les scripts sont dans ce dossier ; le corpus préparé et l'archive Colab
atterrissent dans `dataset/tts/`.

## Sur le Mac

```sh
# 1. préparer le corpus (élagage, 22 050 Hz, gain, découpage train/val)
.venv/bin/python entrainement/tts_training/prepare_tts_corpus.py \
    --source /Users/pc/Downloads/hausa_tts/mounkaila-56k8 \
    --sortie dataset/tts/corpus

# 2. fabriquer l'archive à téléverser
.venv/bin/python entrainement/tts_training/bundle_tts_for_colab.py
```

Produit `dataset/tts/hausa_tts.zip` — 32 Mo, corpus **et** scripts ensemble, donc
toujours cohérents.

## Sur Colab (runtime T4)

Déposer `hausa_tts.zip` dans un dossier Drive nommé `hausa_tts`, puis :

```python
from google.colab import drive; drive.mount('/content/drive')
%cd /content
!cp /content/drive/MyDrive/hausa_tts/hausa_tts.zip . && unzip -oq hausa_tts.zip

!python hausa_tts/train_tts_piper_colab.py --preparer         # installe Piper (~5 min)
!python hausa_tts/train_tts_piper_colab.py --modele-a-blanc  # valide la chaîne (~10 min)
!python hausa_tts/train_tts_piper_colab.py --epoques 300     # tour court
!python hausa_tts/train_tts_piper_colab.py --exporter
```

### Deux étapes, à ne pas mener ensemble

**Apprendre la voix** coûte des heures de GPU. **Fabriquer le modèle** coûte
quelques minutes — mais c'est cette seconde étape qui échoue sur un détail de
format, et rien ne le révèle avant d'avoir tout entraîné.

`--modele-a-blanc` la valide d'abord, sur **une seule époque**. Le fichier
produit passe par exactement le même chemin que le modèle final : Piper écrit
lui-même la configuration, l'export ONNX tourne, la conversion sherpa annote, et
l'application peut charger le résultat.

⚠️ **La voix produite ne sera pas la vôtre.** Une époque effleure à peine les
poids repris du checkpoint français : le modèle prononcera un charabia à
consonance française. Ce qu'on vérifie, c'est la plomberie — l'export passe,
`frontend=characters` est bien posé, l'application accepte le jeu de caractères,
et du son sort du téléphone.

**Relancer la même commande après une coupure suffit** : le script repart du
dernier checkpoint déposé sur Drive. `--preparer` est en revanche à refaire après
chaque redémarrage de la VM — Piper vit sur le disque de session, pas sur Drive.

Faire le tour court à 300 époques avant tout le reste : mieux vaut découvrir une
option refusée en dix minutes qu'en six heures.

## Ce que contient le corpus préparé

| | |
|---|---|
| Clips | 375 (356 entraînement / 19 validation) |
| Durée | 14,0 min après élagage (17,4 min brutes) |
| Format | WAV PCM 22 050 Hz mono 16 bits |
| Caractères | 28 distincts, tous présents dans la table de Piper |

Le découpage train/val **préserve la couverture** : un clip ne part en validation
que si chaque mot, position et jonction qu'il porte reste vu à l'entraînement.

## Trois décisions propres au hausa

### `ƙ` est translittéré en `q`

En mode `phoneme_type text`, Piper ne construit aucune table depuis le corpus :
il garde la table IPA d'espeak (166 symboles) et **saute en silence** tout
caractère absent. `ɗ` et `ɓ` y sont, étant des implosives IPA. `ƙ` n'y est pas.

Sans substitution, `a ƙara` aurait été appris « a ara » — et cela ne se serait
entendu que des heures plus tard. `q` est retenu plutôt que `k` parce qu'il est
libre dans ce corpus : la distinction entre le `k` simple de `jikka` et
l'éjective de `ƙara` est préservée.

⚠️ **Cette translittération devra être appliquée à l'inférence.** Le mobile envoie
aujourd'hui `a ƙara` au synthétiseur. Le jour où ce modèle remplace l'actuel,
`normalizeHausaTtsText` devra faire la même substitution, sinon le caractère sera
refusé par la table du nouveau modèle.

### Les trois phrases système sont écartées

`sys_confirm`, `sys_cannot_answer` et `sys_repeat` sont des énoncés **fixes** :
l'application peut rejouer leur WAV tel quel. Les faire apprendre au modèle
serait payer une généralisation dont on n'a aucun besoin — alors que les
montants, eux, sont combinatoires et n'ont pas d'autre voie que la synthèse.

Effet de bord heureux : ces trois phrases portaient les seules majuscules du
corpus, que la table de Piper rejette toutes sauf `X`. Les écarter retire le
problème au lieu de le contourner.

Leurs trois WAV restent dans `/Users/pc/Downloads/hausa_tts/mounkaila-56k8/wavs/`
et sont à embarquer comme ressources audio dans l'application.

### Un gain global de +5 dB

Les prises ont été enregistrées bas : RMS moyen 0,064 pour une bande visée de
0,10–0,20, et le studio les a toutes marquées « douteux ». Rien n'est abîmé pour
autant — aucune saturation, crête maximale à 0,551, fond très bas. C'est un
simple déficit de niveau.

Un gain est une multiplication : il n'invente aucun échantillon et ne crée aucun
artefact. C'est ce qui le sépare d'un débruitage, que cette chaîne refuse
justement parce qu'il remplacerait un bruit décorrélé par des artefacts corrélés
à la parole.

Le facteur est **global** (×1,775, calculé sur la crête la plus haute), et non
par fichier : normaliser chaque prise séparément effacerait les écarts
d'intensité entre énoncés, et le modèle apprendrait une voix plate. Après gain :
RMS moyen 0,128, 337/375 prises dans la bande, zéro écrêtage.

## Après l'entraînement

1. `convert_tts_for_sherpa.py` produit le modèle au format attendu par le mobile.
2. Supprimer `spoken_forms` du lexique (`jikka` → `jikk ka`) : ce contournement
   n'existe que parce que le modèle **actuel** perd la gémination. Le nouveau
   l'aura apprise de votre voix.
3. Ajouter la translittération `ƙ` → `q` à `normalizeHausaTtsText`.

Ces trois points vont ensemble : les faire séparément casserait la synthèse entre
deux étapes.
