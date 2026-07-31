# Prompt Codex — Dupliquer la calculatrice Zarma et créer la version Haousa

Tu travailles dans le dépôt de mon application de **calculatrice vocale en zarma** que j'ai copier et renomer haousa.

Ta mission est de créer une nouvelle version complète de cette application pour la langue **hausa**, en modifier cette version zarma.

---

## 1. Objectif fonctionnel

Créer une calculatrice vocale en hausa avec le pipeline suivant :

```text
Voix de l’utilisateur en hausa
    ↓
Transcription automatique de la parole en texte hausa
    ↓
Normalisation du texte
    ↓
Détection des nombres et des opérateurs en hausa
    ↓
Conversion des nombres hausa en valeurs numériques
    ↓
Exécution du calcul
    ↓
Conversion du résultat numérique en mots hausa
    ↓
Synthèse vocale du résultat en hausa
    ↓
Lecture audio du résultat dans l’application
```

L’application doit reprendre les fonctionnalités déjà présentes dans la calculatrice Zarma :

- enregistrement vocal ;
- envoi de l’audio au backend ;
- transcription ;
- analyse linguistique ;
- calcul ;
- affichage du résultat ;
- réponse vocale ;
- gestion des erreurs ;
- historique, s’il existe déjà ;
- interface mobile existante ;
- API existante ;
- tests existants ;
- configuration existante.

Toute la logique linguistique Zarma doit être supprimée et remplacée par la logique hausa.

---

## 2. Règles impératives

2. Commence par inspecter toute l’architecture du projet.
3. Identifie :
   - le frontend Flutter /Users/pc/project/haousa/apps/mobile ;
   - le backend FastAPI ou Python ;
   - les fichiers de configuration ;
   - les services ASR ;
   - les services TTS ;
   - le parseur des nombres ;
   - le moteur de calcul ;
   - les tests ;
   - les ressources audio ;
   - les variables d’environnement ;
   - les scripts de lancement ;
   - les fichiers Docker, s’ils existent.
6. Ne supprime aucune fonctionnalité utile.
7. N’effectue aucune réécriture inutile de l’architecture.
8. Conserve autant que possible les mêmes API, interfaces, routes et contrats JSON.
9. Remplace toutes les références visibles ou techniques à :
   - Zarma ;
   - Zarma IA ;
   - zarma ;
   - zarma_asr ;
   - vocabulaire zarma ;
   - nombres zarma ;
   - voix zarma ;
   - fichiers audio zarma.
10. Utilise les nouveaux noms appropriés :
   - Hausa ;
   - Haousa pour le nom du dossier demandé ;
   - Hausa Calculator ou Calculatrice Hausa pour l’application ;
   - `hausa` pour les identifiants techniques ;
   - `hausa_asr` pour les modules de transcription ;
   - `hausa_numbers` pour les modules de numération.

Avant tout remplacement global, vérifie le contexte afin de ne pas casser les chemins, les dépendances ou les noms de classes.

---

## 3. Première étape : audit du projet Zarma

Avant de modifier quoi que ce soit, produis un résumé dans le terminal contenant :

```text
- dossier racine détecté ;
- technologies utilisées ;
- structure du frontend ;
- structure du backend ;
- emplacement du parseur Zarma ;
- emplacement du service ASR ;
- emplacement du service TTS ;
- emplacement du moteur de calcul ;
- emplacement des tests ;
- fichiers qui devront être modifiés ;
- fichiers qui devront être copiés sans modification ;
- éventuels risques détectés.
```

Ensuite, réalise la duplication.

Exemple attendu, à adapter au dépôt réel :

```bash
cp -a CalculatriceZarma Haousa
```

Ne lance cette commande qu’après avoir identifié le bon dossier source.

---

## 4. Transcription vocale hausa

La nouvelle version doit utiliser le modèle spécialisé suivant :

```text
NCAIR1/Hausa-ASR
```

Le modèle est accessible depuis Hugging Face et doit pouvoir être chargé soit :

- depuis Hugging Face avec un jeton `HF_TOKEN` ;
- soit depuis une copie locale installée sur le serveur.

Prévois une configuration de ce type :

```env
HAUSA_ASR_MODEL=NCAIR1/Hausa-ASR
HAUSA_ASR_LOCAL_PATH=
HF_TOKEN=
ASR_DEVICE=auto
```

Le code doit choisir automatiquement :

```text
GPU CUDA si disponible
sinon CPU
```

Le service ASR doit :

- accepter WAV, MP3, M4A, AAC, OGG et FLAC ;
- convertir l’audio en WAV ;
- utiliser un seul canal ;
- utiliser une fréquence de 16 000 Hz ;
- supprimer les fichiers temporaires après traitement ;
- retourner une transcription propre ;
- gérer les erreurs de modèle ;
- gérer les erreurs de format audio ;
- gérer les audios vides ;
- avoir une durée maximale configurable ;
- ne pas conserver l’audio sans consentement explicite.

Exemple de réponse API :

```json
{
  "success": true,
  "language": "hausa",
  "text": "ashirin da uku a kara goma sha biyar"
}
```

Le code doit fonctionner avec la version locale du modèle si un chemin est fourni :

```python
local_files_only=True
```

Le modèle ne doit pas être rechargé à chaque requête. Charge-le une seule fois au démarrage du serveur.

---

## 5. Numération hausa à implémenter

Supprime le dictionnaire et les règles de numération Zarma dans la copie Haousa.

Crée un module dédié, par exemple :

```text
hausa_numbers.py
```

ou, selon l’architecture existante :

```text
services/hausa_numbers.py
linguistics/hausa_numbers.py
domain/hausa_numbers.py
```

### 5.1 Chiffres et nombres de base

Utilise les formes canoniques suivantes :

```text
0  = sifili
1  = ɗaya
2  = biyu
3  = uku
4  = huɗu
5  = biyar
6  = shida
7  = bakwai
8  = takwas
9  = tara
10 = goma
```

### 5.2 Nombres de 11 à 19

La structure canonique est :

```text
goma sha + unité
```

Exemples :

```text
11 = goma sha ɗaya
12 = goma sha biyu
13 = goma sha uku
14 = goma sha huɗu
15 = goma sha biyar
16 = goma sha shida
17 = goma sha bakwai
18 = goma sha takwas
19 = goma sha tara
```

Le parseur doit aussi accepter les formes orales abrégées :

```text
sha ɗaya
sha biyu
sha uku
sha huɗu
sha biyar
sha shida
sha bakwai
sha takwas
sha tara
```

### 5.3 Dizaines

Utilise les formes suivantes :

```text
20 = ashirin
30 = talatin
40 = arba'in
50 = hamsin
60 = sittin
70 = saba'in
80 = tamanin
90 = tasa'in
```

**Important : la forme canonique de 90 dans ce projet est obligatoirement :**

```text
tasa'in
```

Ne remplace pas cette forme canonique par `casa'in`, `tisa'in` ou une autre variante.

Le parseur peut accepter les variantes suivantes uniquement comme alias de reconnaissance :

```text
tasa in
tasa’in
tasain
tisa'in
casa'in
```

Mais toute génération de texte et toute réponse vocale doivent utiliser :

```text
tasa'in
```

### 5.4 Nombres composés de 21 à 99

La structure est :

```text
dizaine + da + unité
```

Exemples :

```text
21 = ashirin da ɗaya
24 = ashirin da huɗu
35 = talatin da biyar
48 = arba'in da takwas
56 = hamsin da shida
67 = sittin da bakwai
72 = saba'in da biyu
89 = tamanin da tara
94 = tasa'in da huɗu
99 = tasa'in da tara
```

### 5.5 Centaines

Utilise :

```text
100 = ɗari
100 = ɗari ɗaya
200 = ɗari biyu
300 = ɗari uku
400 = ɗari huɗu
500 = ɗari biyar
600 = ɗari shida
700 = ɗari bakwai
800 = ɗari takwas
900 = ɗari tara
```

Avec un reste :

```text
101 = ɗari da ɗaya
105 = ɗari da biyar
110 = ɗari da goma
115 = ɗari da goma sha biyar
120 = ɗari da ashirin
125 = ɗari da ashirin da biyar
201 = ɗari biyu da ɗaya
250 = ɗari biyu da hamsin
299 = ɗari biyu da tasa'in da tara
```

### 5.6 Milliers

Utilise :

```text
1 000 = dubu
1 000 = dubu ɗaya
2 000 = dubu biyu
3 000 = dubu uku
4 000 = dubu huɗu
5 000 = dubu biyar
6 000 = dubu shida
7 000 = dubu bakwai
8 000 = dubu takwas
9 000 = dubu tara
10 000 = dubu goma
20 000 = dubu ashirin
100 000 = dubu ɗari
200 000 = dubu ɗari biyu
```

Exemples composés :

```text
1 001 = dubu ɗaya da ɗaya
1 025 = dubu ɗaya da ashirin da biyar
1 500 = dubu ɗaya da ɗari biyar
2 523 = dubu biyu da ɗari biyar da ashirin da uku
25 750 = dubu ashirin da biyar da ɗari bakwai da hamsin
```

### 5.7 Millions, milliards et milliers de milliards

Utilise :

```text
1 000 000 = miliyan ɗaya
2 000 000 = miliyan biyu
10 000 000 = miliyan goma
100 000 000 = miliyan ɗari

1 000 000 000 = biliyan ɗaya
2 000 000 000 = biliyan biyu
10 000 000 000 = biliyan goma

1 000 000 000 000 = tiriliyan ɗaya
2 000 000 000 000 = tiriliyan biyu
```

Exemples :

```text
2 500 000
= miliyan biyu da dubu ɗari biyar

12 345 000
= miliyan goma sha biyu da dubu ɗari uku da arba'in da biyar

```

---

## 6. Dictionnaire minimal sans répétition

Le module doit utiliser au minimum les mots uniques suivants :

```text
sifili
ɗaya
biyu
uku
huɗu
biyar
shida
bakwai
takwas
tara
goma
sha
ashirin
talatin
arba'in
hamsin
sittin
saba'in
tamanin
tasa'in
da
ɗari
dubu
miliyan
```

Ces mots doivent permettre de construire tous les nombres utiles sans créer une liste contenant chaque nombre séparément.

---

## 7. Normalisation du texte ASR

Crée une fonction claire :

```python
normalize_hausa_text(text: str) -> str
```

Elle doit :

- convertir en minuscules ;
- supprimer les espaces multiples ;
- normaliser les apostrophes ;
- supprimer la ponctuation inutile ;
- conserver les caractères hausa importants ;
- corriger les variantes fréquentes produites par l’ASR ;
- ne jamais modifier arbitrairement un mot inconnu ;
- permettre de tracer le texte original et le texte normalisé en mode debug.

Ajoute au minimum les alias suivants :

```python
HAUSA_NORMALIZATION_ALIASES = {
    "daya": "ɗaya",
    "d aya": "ɗaya",
    "d'aya": "ɗaya",
    "hudu": "huɗu",
    "hu du": "huɗu",
    "dari": "ɗari",
    "d'ari": "ɗari",
    "sifiri": "sifili",
    "ishirin": "ashirin",
    "tasa in": "tasa'in",
    "tasa’in": "tasa'in",
    "tasain": "tasa'in",
    "tisa'in": "tasa'in",
    "casa'in": "tasa'in",
    "million": "miliyan",
    "milliyan": "miliyan",
    "billiyan": "biliyan",
    "triliyan": "tiriliyan"
}
```

Traite les remplacements par mots ou expressions complètes afin d’éviter les remplacements accidentels à l’intérieur d’autres mots.

---

## 8. Conversion texte hausa vers nombre

Crée ou adapte une fonction :

```python
hausa_words_to_number(text: str) -> int | float
```

Elle doit reconnaître :

- les unités ;
- les nombres de 11 à 19 ;
- les dizaines ;
- les dizaines avec unités ;
- les centaines ;
- les milliers ;
- les millions ;
- les milliards ;
- les tiriliyan ;
- les formes composées ;
- les variantes normalisées ;
- les espaces supplémentaires ;
- les apostrophes différentes ;
- les caractères hausa sans diacritiques ;
- les formes `ɗari` et `ɗari ɗaya` pour 100 ;
- les formes `dubu` et `dubu ɗaya` pour 1 000.

Utilise un parseur déterministe, pas une traduction vers le français ou l’anglais.

Le parseur doit travailler par groupes :

```text
miliyan
dubu
ɗari
dizaines
unités
```

Il doit éviter les calculs ambigus et lever une erreur explicite en cas de phrase impossible.

Exemples obligatoires :

```python
assert hausa_words_to_number("ɗaya") == 1
assert hausa_words_to_number("goma sha biyar") == 15
assert hausa_words_to_number("ashirin da uku") == 23
assert hausa_words_to_number("tasa'in") == 90
assert hausa_words_to_number("tasa'in da tara") == 99
assert hausa_words_to_number("ɗari biyu da hamsin") == 250
assert hausa_words_to_number("dubu biyu da ɗari biyar da ashirin da uku") == 2523
assert hausa_words_to_number("miliyan biyu da dubu ɗari biyar") == 2500000
```

---

## 9. Conversion nombre vers texte hausa

Crée ou adapte une fonction :

```python
number_to_hausa(value: int | float) -> str
```

Elle doit :

- produire la forme canonique hausa ;
- utiliser `tasa'in` pour 90 ;
- ne jamais produire les mots Zarma ;
- gérer zéro ;
- gérer les nombres négatifs si l’application Zarma les gérait ;
- gérer les décimales si l’application Zarma les gérait ;
- gérer au minimum jusqu’à la limite déjà supportée par la version Zarma ;
- idéalement gérer jusqu’à `tiriliyan`.

Exemples obligatoires :

```python
assert number_to_hausa(0) == "sifili"
assert number_to_hausa(15) == "goma sha biyar"
assert number_to_hausa(23) == "ashirin da uku"
assert number_to_hausa(90) == "tasa'in"
assert number_to_hausa(99) == "tasa'in da tara"
assert number_to_hausa(250) == "ɗari biyu da hamsin"
assert number_to_hausa(2523) == "dubu biyu da ɗari biyar da ashirin da uku"
```

Si des décimales sont supportées, crée une convention cohérente et documentée pour le séparateur oral.

---

## 10. Opérateurs mathématiques en hausa

Remplace les expressions Zarma par un dictionnaire hausa configurable.

Prévois au minimum les opérations suivantes :

```text
addition
soustraction
multiplication
division
```

Crée des alias souples afin d’accepter plusieurs formulations orales.

Exemple de structure :

```python
HAUSA_OPERATORS = {
    "add": [
        "a ƙara",
        "ƙara",
        "a kara",
        "kara",
        "da"
    ],
    "subtract": [
        "a hidda",
        "hidda",
        "debe",
        "a debe"
    ],
    "multiply": [
        "sau",
    ],
    "divide": [
        "a raba chi sau",
        "raba chi sau ",
        "kashi"
    ]
}
```

Attention : le mot `da` sert aussi à construire les nombres.

Ne considère donc pas automatiquement chaque `da` comme un opérateur d’addition.

Le parseur doit d’abord reconnaître les nombres complets, puis identifier l’opérateur entre deux expressions numériques.

Exemples de phrases à reconnaître :

```text
ashirin da uku a ƙara goma sha biyar
ɗari biyar a hidda ɗari biyu
goma sau biyar
ɗari ɗaya a raba chi sau biyu
```

Résultats attendus :

```text
23 + 15 = 38
500 - 200 = 300
10 × 5 = 50
100 ÷ 2 = 50
```

Pour les divisions par zéro, retourne une erreur vocale et textuelle claire.

---

## 11. Analyse complète d’une opération

Crée une fonction centrale, selon l’architecture existante :

```python
parse_hausa_operation(text: str) -> ParsedOperation
```

Exemple de résultat interne :

```json
{
  "original_text": "ashirin da uku a kara goma sha biyar",
  "normalized_text": "ashirin da uku a ƙara goma sha biyar",
  "left_text": "ashirin da uku",
  "left_value": 23,
  "operator": "add",
  "right_text": "goma sha biyar",
  "right_value": 15
}
```

Le moteur doit ensuite produire :

```json
{
  "expression": "23 + 15",
  "result": 38,
  "result_text_hausa": "talatin da takwas"
}
```

---

## 12. Réponse vocale hausa

Inspecte le fonctionnement TTS de la version Zarma.

Dans la copie Haousa :

1. supprime les références aux voix et audios Zarma ;
2. crée un service TTS hausa ;
3. rends le moteur TTS configurable ;
4. si un TTS hausa est déjà prévu dans l’architecture, adapte-le ;
5. si aucun moteur hausa local n’est disponible, crée une interface de service permettant d’en brancher un ultérieurement ;
6. conserve un mode de secours avec des fichiers audio préenregistrés pour les mots numériques de base, si cette stratégie existe déjà dans le projet.

Le texte envoyé au TTS doit toujours utiliser la forme canonique :

```text
tasa'in
```

Prévois des messages vocaux en hausa pour :

- résultat ;
- audio non compris ;
- nombre non reconnu ;
- opérateur non reconnu ;
- opération incomplète ;
- division par zéro ;
- erreur du serveur ;
- absence de connexion ;
- demande de répétition.

Centralise tous les messages dans un fichier de traduction hausa.

---

## 13. Adaptation Flutter

Dans le frontend Flutter de la copie Haousa :

- remplace le nom de l’application ;
- remplace les textes Zarma par les textes hausa ;
- remplace les codes de langue ;
- remplace les chemins vers les ressources audio ;
- remplace les éventuelles références visuelles à Zarma IA ;
- conserve le design et le fonctionnement existants ;
- conserve Riverpod, Dio et les choix techniques existants ;
- adapte les endpoints uniquement si nécessaire ;
- affiche la transcription hausa ;
- affiche l’expression numérique ;
- affiche le résultat ;
- lance automatiquement la réponse audio ;
- conserve les permissions microphone ;
- conserve les indicateurs de chargement ;
- conserve la gestion hors ligne si elle existe.

Ne change pas le thème ou l’ergonomie sans nécessité.

---

## 14. Configuration et variables d’environnement

Crée un fichier d’exemple, sans exposer de secret :

```text
.env.example
```

Il doit contenir au minimum :

```env
APP_LANGUAGE=hausa
APP_NAME=Calculatrice Hausa

HAUSA_ASR_MODEL=NCAIR1/Hausa-ASR
HAUSA_ASR_LOCAL_PATH=
HF_TOKEN=
ASR_DEVICE=auto
ASR_SAMPLE_RATE=16000
ASR_MAX_AUDIO_SECONDS=30

TTS_PROVIDER=
TTS_MODEL=
TTS_VOICE=
TTS_API_KEY=

API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
```

N’enregistre jamais un vrai jeton Hugging Face dans Git.

---

## 15. Tests obligatoires

Adapte les tests Zarma et crée une suite dédiée au hausa.

### 15.1 Tests des nombres

Teste au minimum :

```text
0
1 à 10
11 à 19
20
21
29
30
40
50
60
70
80
90
91
99
100
101
110
115
120
125
200
250
299
999
1 000
1 001
1 025
1 500
2 523
10 000
25 750
100 000
1 000 000
2 500 000
1 000 000 000
1 000 000 000 000
```

### 15.2 Tests spécifiques à 90

Ces tests sont obligatoires :

```python
assert normalize_hausa_text("tasa in") == "tasa'in"
assert normalize_hausa_text("tasa’in") == "tasa'in"
assert normalize_hausa_text("tasain") == "tasa'in"
assert normalize_hausa_text("tisa'in") == "tasa'in"
assert normalize_hausa_text("casa'in") == "tasa'in"

assert hausa_words_to_number("tasa'in") == 90
assert hausa_words_to_number("tasa'in da ɗaya") == 91
assert hausa_words_to_number("tasa'in da tara") == 99

assert number_to_hausa(90) == "tasa'in"
assert number_to_hausa(91) == "tasa'in da ɗaya"
assert number_to_hausa(99) == "tasa'in da tara"
```

### 15.3 Tests d’opérations

Teste au minimum :

```text
ashirin da uku a ƙara goma sha biyar
ɗari biyar a hidda ɗari biyu
goma sau biyar
ɗari ɗaya a raba chi sau biyu
tasa'in da tara a ƙara ɗaya
dubu biyu a hidda ɗari biyar
```

### 15.4 Tests d’erreurs

Teste :

- audio vide ;
- texte vide ;
- nombre inconnu ;
- opérateur inconnu ;
- opération incomplète ;
- division par zéro ;
- deux opérateurs ;
- plusieurs nombres sans opérateur ;
- caractères inattendus ;
- transcription avec apostrophe typographique ;
- transcription sans lettres spéciales hausa.

---

## 16. Nettoyage complet des références Zarma

Après adaptation, cherche dans tout le dossier `Haousa` les références suivantes :

```text
zarma
Zarma
ZARMA
Zarma IA
zarma_asr
zarma_numbers
```

Utilise par exemple :

```bash
grep -RniE "zarma|Zarma|ZARMA|Zarma IA|zarma_asr|zarma_numbers" Haousa
```

Pour chaque résultat :

- décide s’il doit être remplacé ;
- ne conserve une référence Zarma que dans une documentation expliquant l’origine du fork ;
- ne laisse aucun mot Zarma dans les dictionnaires numériques ou opérateurs hausa ;
- ne laisse aucun chemin de modèle Zarma actif ;
- ne laisse aucune ressource audio Zarma active.

---

## 17. Documentation à créer

Dans le dossier `Haousa`, crée ou adapte :

```text
README.md
MIGRATION_ZARMA_TO_HAUSA.md
HAUSA_NUMBER_RULES.md
HAUSA_ASR_SETUP.md
TESTING.md
.env.example
```

### README.md

Il doit expliquer :

- l’objectif de l’application ;
- l’architecture ;
- les prérequis ;
- l’installation ;
- le téléchargement du modèle ;
- la configuration de `HF_TOKEN` ;
- l’exécution du backend ;
- l’exécution de Flutter ;
- les tests ;
- les limites connues.

### MIGRATION_ZARMA_TO_HAUSA.md

Il doit contenir :

- les fichiers copiés ;
- les fichiers modifiés ;
- les fichiers supprimés dans la copie ;
- les nouvelles classes ;
- les nouveaux services ;
- les changements d’API ;
- les migrations de données éventuelles ;
- les éléments restant à valider.

### HAUSA_NUMBER_RULES.md

Il doit documenter :

- toutes les formes canoniques ;
- les alias ;
- les règles de construction ;
- les exemples ;
- le traitement de `da` ;
- le traitement de `sha` ;
- la règle spéciale imposée pour `tasa'in`.

### HAUSA_ASR_SETUP.md

Il doit documenter :

- l’acceptation de l’accès au modèle Hugging Face ;
- la création du jeton ;
- le téléchargement local ;
- le chargement depuis Hugging Face ;
- le chargement local ;
- l’utilisation CPU ;
- l’utilisation GPU ;
- le format audio ;
- les erreurs courantes.

---

## 18. Validation finale

À la fin :

1. installe les dépendances ;
2. lance le linter ;
3. lance les tests Python ;
4. lance les tests Flutter ;
5. lance le backend ;
6. vérifie l’endpoint de santé ;
7. teste une transcription si un audio de test est disponible ;
8. teste au minimum quatre opérations hausa ;
9. vérifie qu’aucun fichier du projet Zarma original n’a été modifié ;
10. vérifie que le nouveau dossier s’appelle exactement `Haousa`.

Affiche un rapport final contenant :

```text
- dossier créé ;
- fichiers créés ;
- fichiers modifiés ;
- modèle ASR configuré ;
- parseur hausa ajouté ;
- conversion nombre vers hausa ajoutée ;
- opérateurs ajoutés ;
- TTS adapté ;
- tests exécutés ;
- résultats des tests ;
- erreurs restantes ;
- commandes exactes pour lancer le frontend ;
- commandes exactes pour lancer le backend.
```

---

## 19. Critères d’acceptation

Le travail est considéré comme terminé uniquement si :

- le projet Zarma original est intact ;
- le dossier `Haousa` existe ;
- le projet Haousa démarre ;
- le modèle `NCAIR1/Hausa-ASR` est configurable ;
- la transcription hausa fonctionne ;
- le parseur transforme correctement les nombres hausa en nombres ;
- le moteur reconnaît les quatre opérateurs ;
- le calcul est correct ;
- le résultat est reconverti en mots hausa ;
- le résultat est prêt à être prononcé en hausa ;
- la forme canonique de 90 est toujours `tasa'in` ;
- aucune logique numérique Zarma active ne subsiste dans la copie ;
- les tests passent ;
- la documentation est complète.

---

## 20. Méthode de travail attendue

Travaille directement sur le projet et ne te contente pas de fournir des extraits théoriques.

Procède dans cet ordre :

```text
1. audit ;
2. sauvegarde de sécurité ;
3. duplication ;
4. renommage ;
5. remplacement de la logique linguistique ;
6. adaptation ASR ;
7. adaptation du parseur ;
8. adaptation du calcul ;
9. adaptation nombre vers texte ;
10. adaptation TTS ;
11. adaptation Flutter ;
12. tests ;
13. documentation ;
14. rapport final.
```

En cas d’ambiguïté dans l’architecture, inspecte le code existant et choisis la solution qui conserve le mieux le fonctionnement de la version Zarma.

Ne demande pas de confirmation pour chaque fichier. Prends les décisions techniques raisonnables, documente-les et signale clairement les points qui nécessitent une validation linguistique par un locuteur hausa.
