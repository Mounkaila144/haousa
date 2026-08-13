# Corpus d'enregistrement TTS hausa

`tts_prompts.csv` — **378 consignes**, de 1 à 12 mots, à enregistrer par une
seule et même personne pour entraîner la voix de la calculatrice.

Le fichier est **généré**, jamais édité à la main :

```sh
python scripts/generate_tts_prompts.py --output dataset/tts/tts_prompts.csv
```

## Pourquoi généré

Le modèle doit savoir dire ce que l'application **dit**, ni plus ni moins — et
ces deux ensembles ne coïncident pas. `ɗari uku` est *compris* (1 500 F) mais
n'est jamais *prononcé* : `format_money(1500)` rend `jikka da ɗari`. Enregistrer
la liste des formes comprises ferait perdre du temps sur des phrases inutiles,
tout en laissant des trous sur celles qui servent.

Le corpus est donc reconstruit depuis `hausa_numbers`. La graine aléatoire est
fixe : deux exécutions donnent le même fichier, donc les mêmes identifiants que
les prises déjà faites.

## Couverture vérifiée

Les **45 mots** que le moteur peut prononcer sont tous présents, et le corpus
n'en contient aucun autre. 2 105 mots enregistrés au total.

| Catégorie | Contenu |
|---|---|
| Consignes système | les 3 phrases parlées de l'interface |
| Montants < 1 000 F | zéro, unités, `goma sha X`, dizaines, `dizaine da unité`, `ɗari`, `ɗari da X` |
| Milliers | `jikka` **et** `dubu`, de 1 à 999 milliers |
| Milliers + reste | `jikka biyar da ɗari` |
| Opérations relues | les 4 opérateurs, opérandes variés |
| Reste de division | `saura` |

`miliyan` est volontairement absent : le plus grand montant exprimable est
999 995 F, la calculatrice ne prononce jamais le million.

Les deux appellations du millier sont **toutes deux** nécessaires : le choix
Niger/Nigeria est un réglage utilisateur. N'enregistrer que `jikka` rendrait la
voix muette pour la moitié des utilisateurs.

## Enregistrement

Format identique à la chaîne zarma, qui fonctionne :

```text
WAV PCM · 24 000 Hz · mono · 16 bits
```

Gain automatique, annulation d'écho et suppression de bruit **désactivés**.
Aucun découpage, filtre ni rééchantillonnage.

L'en-tête du CSV est `id,texte_zarma,affichage` : c'est le contrat exact
qu'impose le Studio vocal (`entrainement/tts_recorder/lib/csv_codec.dart` du
projet zarma). Le nom de la colonne vient de l'outil, pas de la langue — le
fichier s'y dépose sans modifier l'application.

Protocole, repris du zarma :

1. Toujours la même personne, le même micro, la même distance, la même pièce.
2. Lire exactement le texte affiché, ton naturel.
3. Viser la bande RMS 0,10–0,20, ne jamais dépasser le pic 0,70.
4. S'arrêter après 20 prises, faire contrôler ce premier lot, puis continuer.

## Important — à faire après l'entraînement

Le lexique contient aujourd'hui un contournement :

```yaml
spoken_forms:
  jikka: "jikk ka"
```

Il existe **uniquement** parce que le modèle Piper actuel lit des caractères et
perd la gémination `kk` : il disait « jika » là où il faut entendre « jikk ka ».

Le corpus fait enregistrer `jikka`, la forme écrite correcte. Une fois la
nouvelle voix entraînée sur votre propre prononciation, la gémination sera
apprise directement — et `spoken_forms` devra être **supprimé**. Sinon
l'application enverra `jikk ka` à un modèle qui n'a jamais vu cette graphie, et
la prononciation se dégradera au lieu de s'améliorer.

C'est le seul endroit du système où un contournement du modèle actuel est
inscrit dans les données.
