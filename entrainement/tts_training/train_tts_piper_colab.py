"""Affinage Piper (VITS) de la voix hausa, sur Colab T4 — avec reprise après coupure.

À exécuter dans un notebook Colab, comme `train_asr_v1_colab.py` : ce script n'a
aucune dépendance au reste du dépôt et ne tourne pas en local (le M1 8 Go prépare
les données, il n'entraîne pas).

    # 1. sur le Mac : préparer le corpus, puis fabriquer l'archive
    .venv/bin/python entrainement/tts_training/prepare_tts_corpus.py \\
        --source /Users/pc/Downloads/hausa_tts/mounkaila-56k8 \\
        --sortie dataset/tts/corpus
    .venv/bin/python entrainement/tts_training/bundle_tts_for_colab.py

    # 2. déposer `hausa_tts.zip` dans un dossier Drive `hausa_tts`

    # 3. dans Colab (runtime T4) :
    from google.colab import drive; drive.mount('/content/drive')
    %cd /content
    !cp /content/drive/MyDrive/hausa_tts/hausa_tts.zip . && unzip -oq hausa_tts.zip
    !python hausa_tts/train_tts_piper_colab.py --preparer         # installe Piper (~5 min)
    !python hausa_tts/train_tts_piper_colab.py --modele-a-blanc  # valide la chaine (~10 min)
    !python hausa_tts/train_tts_piper_colab.py --epoques 300     # premier essai court
    !python hausa_tts/train_tts_piper_colab.py --exporter

Deux etapes distinctes, et il vaut mieux les separer : APPRENDRE la voix coute
des heures de GPU, FABRIQUER le modele coute quelques minutes — mais c'est la
seconde qui echoue sur un detail de format, et rien ne le revele avant d'avoir
tout entraine. `--modele-a-blanc` la valide d'abord, sur une seule epoque. La
voix produite n'est pas la votre ; ce qu'on verifie, c'est la plomberie.

**Relancer la même commande après une coupure suffit** : le script repart du
dernier checkpoint déposé sur Drive, ou du checkpoint français si c'est le
premier tour.


Les décisions, et pourquoi
--------------------------

**Le checkpoint est recopié sur Drive pendant l'entraînement, pas seulement à la
fin.** Un `finally` ne protège que des arrêts propres. Quand Colab recycle la VM,
le processus est tué net : le `finally` ne s'exécute pas, le disque de session
disparaît, et une session entière de calcul est perdue — c'est arrivé. Un fil
démon recopie donc `last.ckpt` toutes les vingt minutes (`--veille`), ce qui borne
la perte à un intervalle. La copie est sautée si le fichier n'a pas changé depuis
la précédente : sans cela on repousserait 850 Mo pour rien entre deux validations.

**Les checkpoints locaux restent locaux, un seul va sur Drive.** Piper garde
**dix** checkpoints par défaut (les 5 meilleurs `val_mel` et les 5 meilleurs
`val_mos`), à ~850 Mo pièce : neuf gigaoctets, sur un Drive gratuit qui en compte
quinze. On laisse donc Piper écrire sur le disque de la session — Colab en offre
largement assez et c'est plus rapide — et l'on ne recopie sur Drive que
`last.ckpt`, celui qui sert à reprendre. Le disque de session disparaît à la
coupure ; Drive, non.

**`--data.trim_silence false`.** Piper élague les silences lui-même avec Silero
VAD. Nos marges ont été mesurées, vérifiées prise par prise et validées à
l'oreille : le laisser repasser derrière avec un critère que nous ne contrôlons
pas défait ce travail.

**`--data.phoneme_type text`.** Vérifié dans `dataset.py` : le texte est découpé
en caractères (`list(unicodedata.normalize("NFD", texte))`), sans phonétiseur.
C'est ce qui rend le hausa faisable, espeak-ng ne le connaissant pas.
`--data.espeak_voice` reste exigé par la CLI mais n'est alors jamais appelé.

⚠️ Ce mode ne fabrique **pas** de table de symboles à partir du corpus : il garde
la table IPA d'espeak (`DEFAULT_PHONEME_ID_MAP`, 166 symboles) et y cherche
chaque caractère. Un caractère absent est **ignoré en silence** — `phonemes_to_ids`
journalise un avertissement puis `continue`. L'entraînement ne planterait donc
pas : il apprendrait un texte amputé, ce qui ne se verrait qu'à l'écoute, des
heures plus tard. Le corpus hausa a été confronté à cette table : **`ƙ` en est
absent** (20 occurrences, dans `a ƙara`), et `prepare_tts_corpus.py` le
translittère donc en `q` — libre dans ce corpus, ce qui préserve la distinction
avec le `k` simple de `jikka`. Les majuscules, elles aussi rejetées, ne posent
plus de problème : elles n'apparaissaient que dans les trois phrases système,
écartées de l'entraînement puisqu'elles se rejouent telles quelles.

Après translittération : 28 caractères distincts, tous présents. `_verifier_caracteres` refait
ce contrôle avant chaque entraînement.

Ce que la table contient, mesuré : les minuscules `a`–`z`, les chiffres et la
ponctuation courante passent tous. Ce qui tombe : **les majuscules** (toutes sauf
`X`), les **lettres accentuées** (`à é è ê î ô û ã ñ` — et la décomposition NFD ne
sauve rien, les accents aigu, grave et circonflexe combinants manquent aussi ;
seuls la cédille et le tilde combinants existent), et `ƴ` parmi les lettres
africaines (`ŋ ɲ ɓ ɗ` sont là, étant de l'IPA). Une évolution du corpus qui
introduirait l'un de ces caractères serait rattrapée par le garde-fou.

Corollaire heureux : `num_symbols` vaut 256 quoi qu'il arrive (ce n'est pas la
taille du vocabulaire du corpus), donc l'embedding a la même forme que celui du
checkpoint français et la reprise ne bute pas sur un désaccord de dimensions.

**Deux portes d'entrée, et surtout pas la même.** Amorcer depuis le checkpoint
français passe par `--model.warmstart_ckpt` ; reprendre notre propre entraînement
après une coupure passe par `--ckpt_path`. Les confondre coûte cher :

*`--ckpt_path` sur un checkpoint étranger échoue.* Lightning relit les
hyperparamètres enregistrés dans le checkpoint et les réinjecte dans son parseur
(`_parse_ckpt_path`). Le checkpoint français a été produit par une version de
Piper dont le modèle avait un `sample_bytes` que la version actuelle ne connaît
plus : `error: Subcommand 'fit' does not accept option 'model.sample_bytes'`. Et
même si les options concordaient, la restauration est *stricte* — elle bute sur
les clés du MRD, module absent à l'époque.

*`--model.warmstart_ckpt` est fait pour ça*, Piper le dit dans son propre code :
il recopie tout paramètre de forme identique, laisse les modules neufs
s'initialiser, et repart d'un optimiseur vierge. Pas de relecture
d'hyperparamètres, donc pas de collision de versions.

**Le warmstart est neutralisé à la reprise, et il le faut.** `warmstart_ckpt` est
un hyperparamètre : `save_hyperparameters()` l'enregistre dans *chaque* checkpoint
que nous produirons ensuite. Or `on_fit_start` — qui applique le warmstart —
s'exécute **après** que Lightning a restauré les poids (`trainer.py` : restauration
ligne ~1052, `on_fit_start` ligne ~1064). À la première reprise, les poids français
seraient donc recopiés par-dessus tout ce qui a été appris. Sans erreur, sans
avertissement : on croirait entraîner pendant des jours sans jamais dépasser le
premier tour. Le contournement ne peut pas passer par la ligne de commande —
`_parse_ckpt_path` fait `parse_object(hparams, self.config)`, où les
hyperparamètres du checkpoint *écrasent* les arguments passés. On neutralise donc
`on_fit_start` dans le préambule, quand et seulement quand `--ckpt_path` est
présent.

**`max_epochs` est calculé, pas fixé.** Le warmstart repart d'un compteur à zéro :
`--epoques 300` vaut alors 300 époques. La reprise, elle, restaure le compteur ;
on lit l'époque atteinte et l'on vise `depart + epoques`.


⚠️ Ce script n'a pas pu être exécuté de bout en bout depuis le Mac : il faut un
GPU. Ce qui est vérifiable localement l'a été (format des CSV, présence des
fichiers, options réellement acceptées par la CLI de Piper, lues dans son code).
Le reste demande un premier tour court — d'où `--epoques 300` avant tout le
reste : mieux vaut découvrir une option refusée en dix minutes qu'en six heures.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import threading
from pathlib import Path

#: Dossier Drive où vivent l'archive, le checkpoint de reprise et le modèle final.
#: Modifiable par `--drive` : le nom du dossier est celui que tu as créé à la
#: main, et rien ne garantit qu'il soit écrit comme ici. Le script vérifie qu'il
#: existe plutôt que de le créer en silence — un dossier créé tout seul à côté du
#: bon est la panne qu'on ne voit pas venir, on cherche le modèle là où il n'est pas.
DRIVE = Path("/content/drive/MyDrive/hausa_tts")

#: Disque de la session : rapide, vaste, et perdu à la coupure.
LOCAL = Path("/content/piper_run")

#: Point de départ de l'affinage. Français : l'orthographe « au son » du projet
#: en est proche (« ou » = /u/), et c'est une voix `medium` à 22,05 kHz — la
#: seule qualité que Piper affine sans toucher au reste de la configuration.
CHECKPOINT_FR = (
    "https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/main/"
    "fr/fr_FR/siwis/medium/epoch%3D3304-step%3D2050940.ckpt"
)
NOM_CHECKPOINT_FR = "fr_FR-siwis-medium.ckpt"

VOIX = "hausa-nombres"
FREQUENCE = 22_050

#: La veille et le `finally` écrivent le même fichier : on sérialise, et l'on
#: retient ce qui a déjà été copié pour ne pas repousser 850 Mo inchangés.
_VERROU_SAUVEGARDE = threading.Lock()
_EMPREINTE_SAUVEE: tuple[float, int] | None = None


def _exiger_drive() -> None:
    """Le dossier Drive doit exister — jamais le créer à la place de l'utilisateur."""
    if DRIVE.is_dir():
        return
    parent = DRIVE.parent
    voisins = sorted(d.name for d in parent.iterdir() if d.is_dir()) if parent.is_dir() else []
    raise SystemExit(
        f"dossier Drive introuvable : {DRIVE}\n"
        + (f"dossiers présents dans {parent} : {', '.join(voisins)}\n" if voisins else "")
        + "Drive est-il monté ? sinon, passer le bon chemin avec --drive"
    )


def _run(commande: list[str], **kwargs) -> None:
    print("+", " ".join(str(c) for c in commande), flush=True)
    subprocess.run(commande, check=True, **kwargs)


def preparer() -> None:
    """Installe Piper et son extension Cython. À faire une fois par session."""
    _run(["apt-get", "-qq", "install", "-y", "build-essential", "cmake", "ninja-build"])
    if not Path("/content/piper1-gpl").exists():
        _run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/OHF-voice/piper1-gpl.git",
                "/content/piper1-gpl",
            ]
        )
    _run(
        [sys.executable, "-m", "pip", "-q", "install", "-e", ".[train]"],
        cwd="/content/piper1-gpl",
    )
    # L'extra [train] de Piper ne le déclare pas, mais `torch.onnx.export` en a
    # besoin depuis PyTorch 2.6 : il importe `onnxscript` quoi qu'il arrive. On
    # l'installe ici plutôt qu'à l'export, où le manque se découvre après des
    # heures d'entraînement, au pire moment.
    _run([sys.executable, "-m", "pip", "-q", "install", "onnxscript"])
    # L'alignement monotone est du Cython : sans cette compilation, l'entraînement
    # échoue au premier pas, après avoir mis en cache tout le corpus.
    _run(["bash", "build_monotonic_align.sh"], cwd="/content/piper1-gpl")
    print("\nPiper installé.")


def _checkpoint_depart() -> tuple[Path, bool]:
    """Checkpoint de départ, et vrai si c'est une reprise de notre entraînement.

    La reprise passe par Drive et non par le disque de session : c'est
    précisément la coupure qu'on veut survivre. Le booléen décide de la porte
    d'entrée — `--ckpt_path` pour un checkpoint que nous avons écrit,
    `--model.warmstart_ckpt` pour le checkpoint français, dont les
    hyperparamètres appartiennent à une autre version de Piper.
    """
    reprise = DRIVE / "last.ckpt"
    if reprise.exists():
        print(f"reprise depuis {reprise} ({reprise.stat().st_size / 1e6:.0f} Mo)")
        return reprise, True

    fr = DRIVE / NOM_CHECKPOINT_FR
    if not fr.exists():
        # Sur Drive, pas dans /content : une session coupée ne doit pas obliger
        # à retélécharger 846 Mo.
        print("premier tour — téléchargement du checkpoint français…")
        _run(["wget", "-q", "--show-progress", "-O", str(fr), CHECKPOINT_FR])
    print(f"amorce depuis {fr} (warmstart : poids recopiés, optimiseur neuf)")
    return fr, False


def _epoque_de(checkpoint: Path) -> int:
    """Époque enregistrée dans le checkpoint (0 si illisible)."""
    import torch

    try:
        etat = torch.load(checkpoint, map_location="cpu", weights_only=False)
        return int(etat.get("epoch", 0))
    except Exception as erreur:  # pragma: no cover - dépend du checkpoint
        print(f"époque illisible ({erreur}), on repart de 0")
        return 0


#: Préambule posé devant `piper.train`, parce que PyTorch a changé sous ses pieds.
#:
#: PyTorch 2.6 a inversé le défaut de `torch.load` (`weights_only` passe de False
#: à True). Lightning lit le checkpoint avec `weights_only=True` **explicitement**
#: — un simple défaut ne suffirait donc pas à le contourner — et les checkpoints
#: Piper publiés contiennent un `pathlib.PosixPath` dans leurs hyperparamètres,
#: type que ce mode refuse. Piper a été écrit avant ce changement ; on lui rend la
#: sémantique qu'il attend, pour lui seul et le temps de l'entraînement.
#:
#: Deux niveaux, du plus prudent au moins : on autorise d'abord les types
#: `pathlib`, ce qui suffit à l'erreur connue et laisse la vérification en place
#: pour tout le reste ; on ne repasse en `weights_only=False` qu'en rattrapage,
#: si un autre type non autorisé se présentait. Acceptable ici et nulle part
#: ailleurs : le checkpoint vient du dépôt officiel `rhasspy/piper-checkpoints`,
#: par HTTPS, et c'est le contournement que PyTorch documente lui-même.
_PREAMBULE = '''"""Lance un module Piper, en réparant trois pièges de ses dépendances.

Usage : python _lancer_piper.py <module> [arguments...]
"""
import inspect
import pathlib
import pickle
import runpy
import sys

import torch

_charger = torch.load


def _charger_tolerant(*args, **kwargs):
    try:
        return _charger(*args, **kwargs)
    except pickle.UnpicklingError:
        kwargs["weights_only"] = False
        return _charger(*args, **kwargs)


torch.serialization.add_safe_globals(
    [pathlib.PosixPath, pathlib.PurePosixPath, pathlib.WindowsPath, pathlib.PurePath]
)
torch.load = _charger_tolerant

# Piège n° 2 : PyTorch a fait de son nouvel exportateur ONNX (dynamo) le défaut de
# `torch.onnx.export`. Il ne digère pas VITS, dont le prédicteur de durée a un
# contrôle de flux dynamique. Piper appelle la fonction sans rien préciser : on
# lui rend l'exportateur historique, celui pour lequel il a été écrit.
_exporter_onnx = torch.onnx.export

if "dynamo" in inspect.signature(_exporter_onnx).parameters:

    def _exporter_historique(*args, **kwargs):
        kwargs.setdefault("dynamo", False)
        return _exporter_onnx(*args, **kwargs)

    torch.onnx.export = _exporter_historique

# Piège n° 3 : `warmstart_ckpt` est un hyperparamètre, donc réenregistré dans
# chaque checkpoint que nous produisons. Comme `on_fit_start` s'exécute APRÈS la
# restauration des poids, une reprise réappliquerait les poids d'amorce par-dessus
# tout ce qui a été appris — sans rien dire. On ne peut pas le corriger par la
# ligne de commande : les hyperparamètres du checkpoint écrasent les arguments.
if "--ckpt_path" in sys.argv:
    from piper.train.vits.lightning import VitsModel

    _demarrer = VitsModel.on_fit_start

    def _demarrer_sans_warmstart(self):
        self._warmstart_ckpt = None
        self._vocoder_warmstart_ckpt = None
        return _demarrer(self)

    VitsModel.on_fit_start = _demarrer_sans_warmstart
    print("[reprise] warmstart neutralisé — les poids restaurés sont conservés")

module = sys.argv.pop(1)
sys.argv[0] = module
runpy.run_module(module, run_name="__main__")
'''


def _ecrire_preambule() -> Path:
    """Écrit le lanceur, à côté des artefacts de la session."""
    LOCAL.mkdir(parents=True, exist_ok=True)
    chemin = LOCAL / "_lancer_piper.py"
    chemin.write_text(_PREAMBULE, encoding="utf-8")
    return chemin


def _verifier_caracteres(corpus: Path) -> None:
    """Refuse de partir si un caractère du corpus manque à la table de Piper.

    En mode « text », Piper ne construit pas de table depuis le corpus : il garde
    la table IPA d'espeak et *saute sans broncher* tout caractère qu'il n'y trouve
    pas. Sans cette vérification, l'entraînement réussirait sur un texte amputé et
    l'erreur ne se manifesterait qu'à l'écoute. Autant la voir en deux secondes.
    """
    import unicodedata

    try:
        from piper.phoneme_ids import DEFAULT_PHONEME_ID_MAP as carte
    except ModuleNotFoundError:
        # Le disque de session s'efface à chaque recyclage de la VM, Piper avec
        # lui. Le dossier `hausa_tts/` peut très bien avoir survécu sur Drive et
        # être revenu par le `unzip` — leur présence ne prouve donc rien.
        raise SystemExit(
            "Piper n'est pas installé dans cette session.\n"
            "  !python hausa_tts/train_tts_piper_colab.py --preparer\n"
            "puis relancer cette commande. À refaire après chaque redémarrage de "
            "la VM Colab : l'installation vit sur le disque de session, pas sur Drive."
        ) from None

    manquants: dict[str, int] = {}
    for nom in ("train.csv", "val.csv"):
        fichier = corpus / nom
        if not fichier.exists():
            continue
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if "|" not in ligne:
                continue
            for caractere in unicodedata.normalize("NFD", ligne.split("|", 1)[1]):
                if caractere not in carte:
                    manquants[caractere] = manquants.get(caractere, 0) + 1

    if not manquants:
        print(f"caractères : tous présents dans la table Piper ({len(carte)} symboles)")
        return

    detail = "\n".join(
        f"  U+{ord(c):04X} {unicodedata.name(c, '?')} — {n} occurrences"
        for c, n in sorted(manquants.items(), key=lambda paire: -paire[1])
    )
    raise SystemExit(
        "ces caractères du corpus sont absents de la table de Piper et seraient\n"
        f"supprimés en silence du texte appris :\n{detail}\n"
        "corriger le corpus (voir prepare_tts_corpus.py) avant d'entraîner."
    )


def entrainer(epoques: int, lot: int, corpus: Path, minutes: int = 20) -> None:
    _verifier_caracteres(corpus)
    depart, est_reprise = _checkpoint_depart()
    LOCAL.mkdir(parents=True, exist_ok=True)

    if est_reprise:
        # Reprendre restaure le compteur d'époques : viser un nombre absolu trop
        # bas ferait s'arrêter l'entraînement avant d'avoir fait un seul pas.
        debut = _epoque_de(depart)
        cible = debut + epoques
        print(f"époque de départ {debut} → cible {cible}")
    else:
        # Le warmstart ne restaure rien d'autre que les poids : le compteur part
        # de zéro, et le nombre demandé est le nombre réellement parcouru.
        cible = epoques
        print(f"amorce → {cible} époques")

    commande = [
        sys.executable,
        str(_ecrire_preambule()),
        "piper.train",
        "fit",
        "--data.voice_name",
        VOIX,
        "--data.csv_path",
        str(corpus / "train.csv"),
        "--data.audio_dir",
        str(corpus / "wavs"),
        "--data.cache_dir",
        str(LOCAL / "cache"),
        "--data.config_path",
        str(DRIVE / f"{VOIX}.onnx.json"),
        "--data.batch_size",
        str(lot),
        # Graphèmes : le texte EST la suite de phonèmes (vérifié dans dataset.py).
        "--data.phoneme_type",
        "text",
        # Exigé par la CLI, jamais appelé quand phoneme_type vaut « text ».
        "--data.espeak_voice",
        "fr",
        # Nos marges sont mesurées et validées ; on ne les fait pas retailler.
        "--data.trim_silence",
        "false",
        "--model.sample_rate",
        str(FREQUENCE),
        "--trainer.default_root_dir",
        str(LOCAL),
        "--trainer.max_epochs",
        str(cible),
    ]
    # La porte d'entrée : `--ckpt_path` ne vaut que pour un checkpoint que nous
    # avons écrit nous-mêmes. Voir l'en-tête du fichier.
    commande += (
        ["--ckpt_path", str(depart)]
        if est_reprise
        else ["--model.warmstart_ckpt", str(depart)]
    )
    arret = threading.Event()
    veilleur = threading.Thread(target=_veiller, args=(arret, minutes), daemon=True)
    veilleur.start()
    try:
        _run(commande)
    finally:
        arret.set()
        # Même si l'entraînement s'interrompt proprement, ce qui a été appris doit
        # atteindre Drive : c'est tout l'objet de la manœuvre.
        _sauver_sur_drive()


def _veiller(arret: threading.Event, minutes: int) -> None:
    """Recopie `last.ckpt` vers Drive à intervalle régulier, pendant l'entraînement.

    Le `finally` ne suffit pas, et l'expérience l'a montré : quand Colab recycle
    la VM, le processus est tué net — aucun `finally` ne s'exécute — et le disque
    de session part avec ses checkpoints. Seul ce qui est déjà sur Drive survit.
    Une veille périodique borne donc la perte à la durée d'un intervalle au lieu
    de la totalité de la session.

    Fil démon : il ne retarde pas la sortie du script, et meurt avec la VM.
    """
    while not arret.wait(minutes * 60):
        try:
            _sauver_sur_drive(silencieux_si_absent=True)
        except Exception as erreur:  # pragma: no cover - dépend de Drive
            # Une copie ratée ne doit jamais interrompre l'entraînement : Drive
            # peut être momentanément indisponible, on retentera au tour suivant.
            print(f"[veille] sauvegarde échouée ({erreur}), on retentera")


def _sauver_sur_drive(silencieux_si_absent: bool = False) -> None:
    """Recopie le dernier checkpoint local vers Drive, s'il a changé."""
    global _EMPREINTE_SAUVEE

    candidats = sorted(LOCAL.rglob("last.ckpt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidats:
        if not silencieux_si_absent:
            print("aucun last.ckpt local à sauver — l'entraînement n'a pas atteint la validation")
        return

    with _VERROU_SAUVEGARDE:
        source = candidats[0]
        empreinte = (source.stat().st_mtime, source.stat().st_size)
        if empreinte == _EMPREINTE_SAUVEE:
            return  # rien de neuf depuis la dernière copie ; 850 Mo pour rien
        cible = DRIVE / "last.ckpt"
        # Écriture sous un nom temporaire puis renommage : une coupure pendant la
        # copie laisserait sinon un checkpoint tronqué à la place du bon.
        provisoire = DRIVE / "last.ckpt.partiel"
        shutil.copy2(source, provisoire)
        provisoire.replace(cible)
        _EMPREINTE_SAUVEE = empreinte
        print(f"checkpoint sauvé : {cible} ({cible.stat().st_size / 1e6:.0f} Mo)", flush=True)


def exporter() -> None:
    """Exporte le checkpoint de Drive en ONNX, prêt pour `sherpa-onnx`."""
    checkpoint = DRIVE / "last.ckpt"
    if not checkpoint.exists():
        raise SystemExit(f"pas de checkpoint à exporter : {checkpoint}")
    sortie = DRIVE / f"{VOIX}.onnx"
    _run(
        [
            sys.executable,
            str(_ecrire_preambule()),
            "piper.train.export_onnx",
            "--checkpoint",
            str(checkpoint),
            "--output-file",
            str(sortie),
        ]
    )
    print(
        f"\nexporté : {sortie}\n"
        f"le fichier de configuration écrit à l'entraînement est {DRIVE / f'{VOIX}.onnx.json'} —\n"
        "les deux voyagent ensemble, le runtime attend ce couple de noms."
    )


def modele_a_blanc(lot: int, corpus: Path) -> None:
    """Fabrique un modèle installable **sans attendre l'entraînement**.

    Deux étapes se suivent dans cette chaîne : apprendre la voix, puis fabriquer
    le modèle. La première coûte des heures de GPU ; la seconde, quelques
    minutes — et c'est elle qui peut échouer sur un détail de format que rien ne
    révèle avant d'avoir tout entraîné.

    On la valide donc d'abord, sur **une seule époque**. Le fichier produit passe
    par exactement le même chemin que le modèle final : Piper écrit lui-même la
    configuration (`--data.config_path`), l'export ONNX tourne, la conversion
    sherpa annote, et l'application peut charger le résultat.

    ⚠️ **La voix sera fausse.** Une époque ne fait qu'effleurer les poids repris
    du checkpoint français : le modèle prononcera un charabia à consonance
    française. C'est voulu — ce qu'on vérifie ici, c'est la plomberie :
    l'export passe, `frontend=characters` est bien posé, l'application accepte
    le jeu de caractères, et du son sort du téléphone.
    """
    print(
        "chaîne à blanc : 1 époque, uniquement pour valider export et "
        "conversion.\nla voix produite ne sera PAS la vôtre.\n"
    )
    entrainer(epoques=1, lot=lot, corpus=corpus, minutes=10_000)
    exporter()

    config = DRIVE / f"{VOIX}.onnx.json"
    modele = DRIVE / f"{VOIX}.onnx"
    if not config.exists():
        raise SystemExit(
            f"configuration absente : {config}\n"
            "Piper l'écrit pendant `fit` — l'entraînement d'une époque a-t-il abouti ?"
        )

    sortie = DRIVE / "sherpa"
    _run(
        [
            sys.executable,
            str(Path(__file__).with_name("convert_tts_for_sherpa.py")),
            "--modele",
            str(modele),
            "--config",
            str(config),
            "--sortie",
            str(sortie),
        ]
    )
    print(
        f"\nmodèle à blanc prêt : {sortie}\n"
        "à copier dans apps/mobile/assets/models/hausa_tts/ pour vérifier que\n"
        "l'application le charge et parle. La voix, elle, viendra de "
        "l'entraînement."
    )


def main() -> int:
    global DRIVE

    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--preparer", action="store_true", help="installer Piper")
    parseur.add_argument("--exporter", action="store_true", help="exporter en ONNX")
    parseur.add_argument(
        "--modele-a-blanc",
        action="store_true",
        dest="modele_a_blanc",
        help="1 époque puis export + conversion : valide la chaîne sans entraîner",
    )
    parseur.add_argument("--epoques", type=int, default=300, help="époques à ajouter")
    parseur.add_argument("--lot", type=int, default=16, help="taille de lot (T4 : 16)")
    parseur.add_argument(
        "--corpus",
        type=Path,
        # Nom du dossier tel que l'archive le depose : `bundle_tts_for_colab.py`
        # conserve le nom reel du repertoire source (`dataset/tts/corpus`).
        default=Path("/content/hausa_tts/corpus"),
    )
    parseur.add_argument(
        "--drive",
        type=Path,
        default=DRIVE,
        help="dossier Drive contenant l'archive (défaut : %(default)s)",
    )
    parseur.add_argument(
        "--veille",
        type=int,
        default=20,
        help="minutes entre deux sauvegardes vers Drive (défaut : %(default)s)",
    )
    args = parseur.parse_args()
    DRIVE = args.drive

    if args.preparer:
        preparer()
        return 0
    _exiger_drive()
    if args.exporter:
        exporter()
        return 0
    if not args.corpus.exists():
        raise SystemExit(f"corpus introuvable : {args.corpus}")
    if args.modele_a_blanc:
        modele_a_blanc(args.lot, args.corpus)
        return 0
    entrainer(args.epoques, args.lot, args.corpus, args.veille)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
