# Studio vocal hausa TTS

Application Android Flutter indépendante pour enregistrer la voix unique d’un
modèle Piper hausa à vocabulaire fermé.

Elle embarque une copie de
`dataset/tts/tts_prompts.csv` : **378 consignes exactes**, de 1 à 12 mots,
générées depuis le moteur linguistique par `scripts/generate_tts_prompts.py`.

Le corpus n'est jamais édité à la main. Après régénération, le recopier dans
l'asset :

```sh
python scripts/generate_tts_prompts.py --output dataset/tts/tts_prompts.csv
cp dataset/tts/tts_prompts.csv entrainement/tts_recorder/assets/tts_prompts.csv
``` Le collecteur ASR `corpus_recorder` n’est ni importé ni
modifié.

## Format master

Chaque appui produit directement :

```text
WAV PCM · 24 000 Hz · mono · 16 bits
```

Le gain automatique, l’annulation d’écho et la suppression de bruit sont
explicitement désactivés. Il n’y a aucun découpage, filtre, réencodage,
rééchantillonnage ou envoi réseau dans l’application.

Le profil audio est paramétré : TTS utilise 24 kHz et ASR reste défini à
16 kHz. Les deux applications demeurent indépendantes.

## Compiler

```sh
cd entrainement/tts_recorder
flutter pub get
flutter analyze
flutter test
flutter build apk --release
```

APK :

```text
entrainement/tts_recorder/build/app/outputs/flutter-apk/app-release.apk
```

Paquet Android : `ne.hausa.tts_recorder`.

## Enregistrer

1. Créer une voix, par exemple `Mounkaila`.
2. Utiliser toujours la même personne, le même téléphone ou microphone, la
   même distance et la même pièce calme.
3. Les exemples audio sont facultatifs. Un ZIP complet peut être importé si la
   personne a besoin d’entendre chaque phrase.
4. Lire exactement le texte hausa affiché en grand, avec un ton naturel.
5. Maintenir le bouton pendant toute la phrase puis relâcher. Le post-roll
   conserve 400 ms après le relâchement.
6. Pendant la prise, viser la bande verte RMS 0,10–0,20 et ne jamais dépasser
   le trait rouge de pic 0,70. Le repère noir montre la moyenne de la séance.
7. Écouter et refaire immédiatement les prises signalées. Une dérive de plus
   de 3 dB par rapport aux prises précédentes déclenche une proposition de
   réenregistrement.
8. S’arrêter après 20 prises pour le premier pilote et faire contrôler ce ZIP
   avant d’enregistrer les 380 autres.

Une prise rouge ou orange reste exportable afin que l’humain garde la décision,
mais la revue permet de les filtrer.

## Contrôles TTS

Rouge :

- format différent de WAV PCM 24 kHz mono 16 bits ;
- saturation à partir de 0,98 ;
- RMS inférieur à 0,015 ;
- durée inférieure à 0,35 s ou supérieure à 12 s.

Orange :

- début ou fin possiblement coupés ;
- silence de début ou de fin supérieur à 1 s ;
- bruit de fond final RMS supérieur à 0,02 ;
- niveau moyen très élevé, décalage continu ou durée incohérente ;
- RMS hors de la cible TTS 0,10–0,20 ou pic supérieur à 0,70 ;
- dérive supérieure à 3 dB par rapport à la moyenne de la séance ;
- arrêt automatique à 15 s.

Le VU-mètre convertit les dBFS du flux Android en estimation RMS. Après chaque
prise, il compare cette estimation au RMS réellement mesuré dans le WAV et
mémorise une calibration robuste pour la voix et le téléphone. Ces mesures
n’altèrent jamais les échantillons.

## Export Piper

Le ZIP d’une voix contient :

```text
hausa_tts/
  mounkaila-ab12/
    metadata.csv
    manifest.csv
    wavs/
      tts_1.wav
      tts_1%2F5.wav
      ...
```

`metadata.csv` suit le format mono-locuteur Piper :

```text
tts_1.wav|afo
tts_1%2F5.wav|afo kan ifaysor igou
```

`manifest.csv` conserve les identifiants originaux, dates et mesures de qualité.
Le caractère `/`, impossible dans un nom de fichier plat, est échappé en
`%2F`, tandis que l’identifiant original reste intact dans le manifest.

Documentation Piper :
<https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/TRAINING.md>.

## Limite volontaire

Cette campagne vise uniquement les 378 textes embarqués. Le modèle pourra être
évalué et utilisé sur ce vocabulaire fermé ; aucune qualité n’est promise sur
une phrase extérieure à cette liste.
