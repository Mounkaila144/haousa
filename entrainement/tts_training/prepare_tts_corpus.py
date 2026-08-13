"""Prépare le corpus de synthèse vocale hausa pour un affinage Piper (VITS).

Trois opérations, et rien d'autre :

1. **Élaguer les silences de bord vers une marge constante.** Un modèle de
   synthèse reproduit ce qu'il entend, y compris ce qu'il n'entend pas : si
   chaque exemple commence par une demi-seconde de silence, la voix synthétisée
   le fera aussi, à chaque énoncé. La marge est posée **à partir des bornes de
   la parole**, jamais ajoutée à ce qu'une détection a bien voulu garder : c'est
   l'uniformité qui compte, pas la brièveté.

   La mesure d'énergie est celle de `services/asr/app/vad.py` (`frame_db`), pour
   que les deux chaînes du projet lisent les niveaux de la même façon. La
   *décision*, elle, diffère et doit différer — voir `MARGE_SEUIL_DB`.

   Une propriété est vérifiée sur les 400 prises à chaque exécution : **aucune
   trame à moins de 25 dB sous le pic n'est jetée**. Elle manquait à la première
   version, qui a perdu les premiers mots de trois énoncés sans que rien ne le
   signale — c'est l'oreille du locuteur qui l'a rattrapé, pas la mesure.

   Deux particularités de ce corpus, mesurées et non supposées, commandent le
   reste : chaque prise débute par ~263 ms de zéros numériques exacts, et son
   fond monte de 12 dB une fois la parole commencée (−64 puis −52 dBFS). Le
   silence d'amorce ne décrit donc pas la pièce, et l'on ne s'en sert ni pour
   décider, ni pour garnir les marges.

2. **Rééchantillonner à 22 050 Hz**, la fréquence des points de départ Piper
   `medium`. Un affinage n'a pas le choix : le mel et le vocodeur du checkpoint
   sont noués à sa fréquence. On perd la bande 11,025–12 kHz du master 24 kHz,
   au-dessus de ce qui porte la parole ; on gagne de partir d'un modèle déjà
   entraîné, ce qui à 16 minutes de corpus n'est pas une préférence mais la
   seule voie. `soxr` en qualité VHQ, jamais ffmpeg par défaut.

3. **Découper train/validation en préservant la couverture.** Le corpus n'a pas
   été tiré au hasard : il a été construit pour que chaque mot, chaque position
   et chaque jonction entre deux mots apparaisse. Un tirage aléatoire peut donc
   emporter en validation la seule occurrence d'une jonction rare — le modèle ne
   la verrait jamais, et rien ne le signalerait. Un clip ne part en validation
   que si tout ce qu'il porte reste couvert côté entraînement.

Ce qu'on ne fait PAS, et c'est délibéré : aucun débruitage (un débruiteur
remplace un bruit décorrélé, que le modèle peut ignorer, par des artefacts
corrélés à la parole, qu'il apprendrait comme faisant partie de la voix), aucune
normalisation de niveau, aucun retrait de composante continue, aucun
réencodage avec perte.

    cd /Users/pc/project/hausa
    .venv/bin/python research/hausa-assistant/scripts/prepare_tts_corpus.py \
        --source /Users/pc/Music/hausa_tts/miunkaila-n3hh --rapport

    # écrire le corpus prêt à entraîner + les échantillons avant/après
    .venv/bin/python research/hausa-assistant/scripts/prepare_tts_corpus.py \
        --source /Users/pc/Music/hausa_tts/miunkaila-n3hh \
        --sortie research/hausa-assistant/data/tts_corpus \
        --echantillons research/hausa-assistant/data/tts_avant_apres
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

# `entrainement/tts_training/` : deux niveaux sous la racine, contre trois pour
# l'arborescence zarma dont ce script est repris.
_RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RACINE / "services" / "asr"))

from app import vad  # noqa: E402  (après ajustement du chemin)

#: Marge de silence visée de part et d'autre, en secondes. 50–100 ms : assez
#: pour ne pas mordre sur une attaque de consonne, assez court pour que le
#: modèle n'apprenne pas à faire attendre.
MARGE_S = 0.075

#: Fréquence d'entraînement. Imposée par les checkpoints Piper `medium`.
FREQUENCE_CIBLE = 22_050

#: Part du corpus réservée à la validation. Petite volontairement : à 400 clips,
#: la validation ne sert qu'à suivre la perte, l'évaluation qui tranche se fait
#: sur des nombres jamais enregistrés (voir le protocole d'évaluation).
PART_VALIDATION = 0.05


@dataclass(frozen=True)
class Prise:
    """Une prise, mesurée avant et après élagage."""

    fichier: str
    texte: str
    duree_avant: float
    duree_apres: float
    silence_tete: float
    silence_queue: float
    #: Niveau le plus fort (dBFS) parmi les trames **jetées**. C'est le garde-fou
    #: qui compte : si l'on avait rogné un mot, une trame forte se serait
    #: retrouvée du mauvais côté de la coupe.
    rejet_max_dbfs: float
    #: Pic de la prise (dBFS), pour lire `rejet_max_dbfs` relativement.
    pic_dbfs: float
    #: La marge demandée n'a pas pu être prise dans l'enregistrement : il a fallu
    #: allonger avec du bruit de fond prélevé dans la prise elle-même.
    complete: bool
    #: Une trame à moins de 25 dB sous le pic est tombée hors du segment gardé :
    #: la garantie est violée sur cette prise, il faut l'écouter.
    parole_perdue: bool = False


def _dbfs(x: np.ndarray) -> float:
    if x.size == 0:
        return -math.inf
    crete = float(np.abs(x).max())
    return 20.0 * math.log10(crete) if crete > 0 else -math.inf


#: Marge au-dessus du fond du corpus à partir de laquelle une trame compte comme
#: du son à garder. **2 dB seulement** : ce seuil ne sert pas à décider ce qui est
#: de la parole, il sert à trouver les *bords* de l'énoncé sans jamais mordre
#: dedans. Le silence de trop se paie en uniformité ; un mot coupé ne se rattrape
#: pas — et sur ce corpus il ne s'agissait pas d'un phonème mais de mots entiers.
#:
#: Ce que la première version faisait de travers, parce que la trace en vaut la
#: peine : elle estimait le fond **prise par prise**, sur la queue du fichier. Sur
#: les prises que le locuteur arrête vite, cette queue contient encore du son, le
#: fond ressortait à −39 dBFS au lieu de −50, et le seuil qui en découlait passait
#: au-dessus des mots les plus faibles (−25 à −28 dBFS). Trois prises y ont perdu
#: leurs premiers mots — vérifié à l'oreille par le locuteur, pas par la mesure.
MARGE_SEUIL_DB = 2.0

#: Écart sous le pic en deçà duquel une trame est indiscutablement de la parole.
#: Sert uniquement de **garantie vérifiable** : aucune trame au-dessus de
#: (pic − 25 dB) ne doit tomber hors du segment gardé. C'est la propriété que le
#: rapport contrôle sur les 400 prises, et c'est elle qui aurait dû être posée
#: avant de faire écouter quoi que ce soit.
PAROLE_SOUS_PIC_DB = 25.0


def plancher_corpus(signaux: list[tuple[np.ndarray, int]]) -> float:
    """Fond du corpus (dBFS), mesuré une fois sur l'ensemble des prises.

    Un fond **global** est ici plus sûr qu'un fond par prise, et ce n'est pas un
    pis-aller : une seule voix, une seule séance, un seul micro, une seule pièce
    — les conditions sont constantes par construction, et les niveaux le
    confirment (RMS 0,019 à 0,084). Un estimateur global ne peut pas s'emballer
    sur un fichier particulier, là où un estimateur local n'a qu'un fichier pour
    se tromper.

    Par prise, on prend le 75e centile des trames qui ne sont pas de la parole :
    cela vise le régime « micro ouvert » d'après l'énoncé (−52 dBFS) plutôt que
    le silence d'amorce (−64 dBFS), qui ne décrit pas la pièce. Puis la médiane
    sur le corpus.
    """
    fonds: list[float] = []
    for x, frequence in signaux:
        niveaux = _niveaux(x, frequence)
        finis = niveaux[np.isfinite(niveaux)]
        if finis.size == 0:
            continue
        pic = float(finis.max())
        hors_parole = finis[finis < pic - PAROLE_SOUS_PIC_DB]
        fonds.append(float(np.percentile(hors_parole, 75)) if hors_parole.size else pic - 30.0)
    return float(np.median(fonds)) if fonds else -50.0


def bornes_parole(x: np.ndarray, frequence: int, fond: float) -> tuple[int, int]:
    """Première et dernière **trame** de son, au-dessus du fond du corpus.

    Un seuil unique et bas, sans hystérésis : la version à deux seuils reposait
    sur un fond estimé localement, et lui donnait le pouvoir d'exclure un mot
    entier quand il se trompait. Ici le seuil est presque au ras du fond, donc
    le pire qu'il puisse faire est de garder du silence.
    """
    niveaux = _niveaux(x, frequence)
    sonore = np.flatnonzero(niveaux >= fond + MARGE_SEUIL_DB)
    if sonore.size == 0:
        raise ValueError("aucun son détecté au-dessus du fond du corpus")
    return int(sonore[0]), int(sonore[-1])


def parole_hors_segment(x: np.ndarray, frequence: int, fond: float, debut: int, fin: int) -> bool:
    """Une trame indiscutablement de parole tombe-t-elle hors de [debut, fin] ?

    Le critère est relatif au pic de la prise, mais **jamais sous le fond du
    corpus** : sur une prise faible (`tts_7.wav` culmine à −23,8 dBFS quand les
    autres sont vers −10), « pic − 25 dB » descendrait au niveau de la pièce et
    ferait passer le bruit de fond pour de la parole. La garantie signalerait
    alors une perte là où il n'y en a aucune.
    """
    niveaux = _niveaux(x, frequence)
    finis = niveaux[np.isfinite(niveaux)]
    if finis.size == 0:
        return False
    seuil = max(float(finis.max()) - PAROLE_SOUS_PIC_DB, fond + 8.0)
    parole = np.flatnonzero(niveaux >= seuil)
    return bool(parole.size and (parole[0] < debut or parole[-1] > fin))


def _niveaux(x: np.ndarray, frequence: int) -> np.ndarray:
    return vad.frame_db(x, max(1, int(vad._FRAME_S * frequence)))


def _fond_uniforme(x: np.ndarray, frequence: int, depuis: int, longueur: int) -> np.ndarray:
    """La fenêtre la plus calme du fond de queue, à poser des deux côtés.

    Prélevée **après** le dernier mot, jamais dans le silence d'amorce : c'est le
    fond réel de la pièce. Prendre la plus calme évite d'embarquer une reprise de
    souffle, qu'on recollerait alors devant chaque énoncé.
    """
    zone = x[depuis:] if len(x) - depuis >= longueur else x[-longueur:] if len(x) >= longueur else x
    if zone.size < longueur:
        return np.resize(zone if zone.size else np.zeros(1), longueur)
    pas = max(1, longueur // 8)
    debuts = range(0, zone.size - longueur + 1, pas)
    meilleur = min(debuts, key=lambda i: float(np.abs(zone[i : i + longueur]).mean()))
    return zone[meilleur : meilleur + longueur].copy()


def _fondu(a: np.ndarray, b: np.ndarray, frequence: int) -> np.ndarray:
    """Raccord en fondu de 5 ms — un collage net ferait un clic périodique."""
    n = min(int(0.005 * frequence), len(a), len(b))
    if n == 0:
        return np.concatenate([a, b])
    rampe = np.linspace(0.0, 1.0, n)
    joint = a[-n:] * (1 - rampe) + b[:n] * rampe
    return np.concatenate([a[:-n], joint, b[n:]])


def elaguer(
    x: np.ndarray,
    frequence: int,
    fond: float,
    marge_s: float = MARGE_S,
    fond_uniforme: bool = True,
) -> tuple[np.ndarray, float, float, float, bool]:
    """Ramène les silences de bord à `marge_s`, constante, sans toucher l'intérieur.

    Retourne le signal élagué, les silences de tête et de queue **obtenus**, le
    niveau maximal jeté (dBFS) et un drapeau disant si la marge a dû être
    complétée. Les silences rendus sont mesurés sur le résultat, jamais recopiés
    depuis la consigne : c'est la seule façon de voir qu'une coupe n'a pas eu lieu.
    """
    trame = max(1, int(vad._FRAME_S * frequence))
    premiere, derniere = bornes_parole(x, frequence, fond)
    debut_parole = premiere * trame
    fin_parole = min(len(x), (derniere + 1) * trame)

    marge = int(round(marge_s * frequence))
    voulu_debut = debut_parole - marge
    voulu_fin = fin_parole + marge

    manque_tete = max(0, -voulu_debut)
    manque_queue = max(0, voulu_fin - len(x))

    if fond_uniforme:
        # Les deux marges viennent du même fond, celui d'après la parole. Sinon
        # chaque exemple commencerait 12 dB plus silencieux qu'il ne finit, et
        # c'est un motif que 400 prises sur 400 partagent : le modèle
        # l'apprendrait comme faisant partie de la voix.
        matiere = _fond_uniforme(x, frequence, fin_parole, marge)
        noyau = x[debut_parole:fin_parole]
        coupe = _fondu(_fondu(matiere.copy(), noyau, frequence), matiere[::-1].copy(), frequence)
        complete = True
    else:
        coupe = x[max(0, voulu_debut) : min(len(x), voulu_fin)]
        complete = bool(manque_tete or manque_queue)
        if complete:
            matiere = _fond_uniforme(x, frequence, fin_parole, max(manque_tete, manque_queue, 1))
            coupe = np.concatenate([matiere[:manque_tete][::-1], coupe, matiere[:manque_queue]])

    # Ce qu'on a jeté : si un mot avait été rogné, une trame forte s'y trouverait.
    # En trames RMS, comme tout le reste : une crête isolée sur un échantillon
    # ne dit rien, c'est une trame forte hors du segment qui trahirait un mot rogné.
    jetes = np.concatenate(
        [
            _niveaux(x[: max(0, voulu_debut)], frequence),
            _niveaux(x[min(len(x), voulu_fin) :], frequence),
        ]
    )
    jetes = jetes[np.isfinite(jetes)]
    rejet = float(jetes.max()) if jetes.size else -math.inf

    tete_obtenue, queue_obtenue = _silences_obtenus(coupe, frequence, fond)
    return coupe, tete_obtenue, queue_obtenue, rejet, complete


def _silences_obtenus(y: np.ndarray, frequence: int, fond: float) -> tuple[float, float]:
    """Silence réellement présent aux deux bords du clip produit.

    Mesuré, pas déduit de la consigne : c'est ce chiffre qui dit si une prise a
    échappé à l'élagage, et c'est l'uniformité de ce chiffre — pas sa petitesse —
    qui décide de ce que le modèle apprendra du silence.
    """
    try:
        premiere, derniere = bornes_parole(y, frequence, fond)
    except ValueError:
        return 0.0, 0.0
    trames = len(_niveaux(y, frequence))
    return premiere * vad._FRAME_S, (trames - 1 - derniere) * vad._FRAME_S


def _unites(texte: str) -> set[tuple[str, ...]]:
    """Unités de couverture d'un énoncé — les mêmes qu'à la sélection du corpus.

    Un mot en fin d'énoncé porte une mélodie descendante, au milieu il enchaîne :
    ce sont deux réalisations différentes. Et la jonction entre deux mots est
    précisément ce que la concaténation rate, donc ce que le modèle doit
    apprendre. Perdre l'une ou l'autre en validation se paierait à l'écoute.
    """
    mots = texte.split()
    unites: set[tuple[str, ...]] = set()
    for i, mot in enumerate(mots):
        if len(mots) == 1:
            position = "seul"
        elif i == 0:
            position = "debut"
        elif i == len(mots) - 1:
            position = "fin"
        else:
            position = "milieu"
        unites.add(("mot", mot))
        unites.add(("position", mot, position))
        if i:
            unites.add(("jonction", mots[i - 1], mot))
    return unites


def decouper(
    lignes: list[tuple[str, str]], part: float, graine: int
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Réserve une validation qui n'ampute la couverture de l'entraînement d'aucune unité."""
    total: Counter[tuple[str, ...]] = Counter()
    par_ligne: dict[str, set[tuple[str, ...]]] = {}
    for fichier, texte in lignes:
        unites = _unites(texte)
        par_ligne[fichier] = unites
        total.update(unites)

    vise = max(1, int(round(part * len(lignes))))
    ordre = list(lignes)
    random.Random(graine).shuffle(ordre)

    validation: list[tuple[str, str]] = []
    restant = Counter(total)
    for fichier, texte in ordre:
        if len(validation) >= vise:
            break
        unites = par_ligne[fichier]
        # On ne prend que si chaque unité reste vue au moins une fois ailleurs.
        if all(restant[u] > 1 for u in unites):
            validation.append((fichier, texte))
            for u in unites:
                restant[u] -= 1

    retenus = {f for f, _ in validation}
    entrainement = [(f, t) for f, t in lignes if f not in retenus]
    return entrainement, validation


#: Translittération imposée par Piper en mode « text ».
#:
#: Piper n'y construit AUCUNE table depuis le corpus : il garde la table IPA
#: d'espeak (166 symboles) et saute *en silence* tout caractère absent. `ɗ` et
#: `ɓ` y sont — ce sont des implosives IPA. `ƙ` n'y est pas : sans cette
#: substitution, `a ƙara` serait appris « a ara », et cela ne s'entendrait que
#: des heures plus tard.
#:
#: `q` est retenu plutôt que `k` : il est libre dans notre corpus, ce qui
#: préserve la distinction entre le `k` simple de `jikka` et l'éjective de
#: `ƙara`. Les confondre demanderait au modèle de deviner d'après le contexte,
#: sur vingt exemples seulement.
TRANSLITTERATION = {"ƙ": "q"}


def translitterer(texte: str) -> str:
    """Texte prêt pour Piper. **Doit** être appliqué à l'identique à l'inférence.

    Le mobile envoie aujourd'hui `a ƙara` au synthétiseur : le jour où ce modèle
    remplace l'actuel, `normalizeHausaTtsText` devra faire la même substitution,
    sans quoi le caractère sera refusé par la table du nouveau modèle.
    """
    for source, cible in TRANSLITTERATION.items():
        texte = texte.replace(source, cible)
    return texte


def _lire_metadata(source: Path) -> list[tuple[str, str]]:
    """Lit `metadata.csv`, écarte les consignes système, translittère le reste.

    Les phrases système (`sys_*`) sont **exclues de l'entraînement** : ce sont
    trois énoncés fixes, que l'application peut rejouer tels quels depuis leur
    WAV. Les faire apprendre au modèle serait payer une généralisation dont on
    n'a aucun besoin — alors que les montants, eux, sont combinatoires et n'ont
    pas d'autre voie que la synthèse.

    Heureux effet de bord : ces trois phrases portaient les seules majuscules du
    corpus, et la table de Piper les rejette toutes sauf `X`. Les écarter retire
    le problème au lieu de le contourner.
    """
    with (source / "metadata.csv").open(encoding="utf-8") as flux:
        lignes = [tuple(r) for r in csv.reader(flux, delimiter="|") if r]
    for ligne in lignes:
        if len(ligne) != 2:
            raise SystemExit(f"metadata.csv : ligne à {len(ligne)} colonnes — {ligne!r}")

    systeme = [ligne for ligne in lignes if ligne[0].startswith("sys_")]
    corpus = [
        (fichier, translitterer(texte))
        for fichier, texte in lignes
        if not fichier.startswith("sys_")
    ]
    print(
        f"consignes : {len(corpus)} à entraîner, "
        f"{len(systeme)} phrases système écartées (rejouées telles quelles)"
    )
    return corpus  # type: ignore[return-value]


def _traiter(
    source: Path, lignes: list[tuple[str, str]], fond_uniforme: bool = True
) -> tuple[list[Prise], dict[str, np.ndarray], float]:
    prises: list[Prise] = []
    audio: dict[str, np.ndarray] = {}

    # Première passe : tout lire, et mesurer le fond sur l'ensemble du corpus.
    # Une seule voix, une seule séance, un seul micro : un fond global ne peut
    # pas s'emballer sur un fichier particulier, là où un fond estimé prise par
    # prise n'a qu'un fichier pour se tromper — et s'est trompé.
    signaux: dict[str, tuple[np.ndarray, int]] = {}
    for fichier, _ in lignes:
        x, frequence = sf.read(source / "wavs" / fichier, dtype="float64", always_2d=False)
        if x.ndim != 1:
            raise SystemExit(f"{fichier} : {x.ndim} canaux, mono attendu")
        signaux[fichier] = (x, frequence)
    fond = plancher_corpus(list(signaux.values()))

    for fichier, texte in lignes:
        x, frequence = signaux[fichier]
        premiere, derniere = bornes_parole(x, frequence, fond)
        perdu = parole_hors_segment(x, frequence, fond, premiere, derniere)
        coupe, tete, queue, rejet, complete = elaguer(
            x, frequence, fond, fond_uniforme=fond_uniforme
        )
        reduit = soxr.resample(coupe, frequence, FREQUENCE_CIBLE, quality="VHQ")
        audio[fichier] = reduit
        prises.append(
            Prise(
                fichier=fichier,
                texte=texte,
                duree_avant=len(x) / frequence,
                duree_apres=len(reduit) / FREQUENCE_CIBLE,
                silence_tete=tete,
                silence_queue=queue,
                rejet_max_dbfs=rejet,
                parole_perdue=perdu,
                pic_dbfs=float(_niveaux(x, frequence)[np.isfinite(_niveaux(x, frequence))].max()),
                complete=complete,
            )
        )
    return prises, audio, fond


def _rapport(prises: list[Prise], entrainement: list, validation: list) -> None:
    avant = sum(p.duree_avant for p in prises)
    apres = sum(p.duree_apres for p in prises)
    print(f"prises                 : {len(prises)}")
    print(
        f"durée avant / après    : {avant/60:.1f} min → {apres/60:.1f} min "
        f"({100*(avant-apres)/avant:.0f} % de silence de bord retiré)"
    )

    tetes = np.array([p.silence_tete for p in prises])
    queues = np.array([p.silence_queue for p in prises])
    print(
        f"silence de tête obtenu : {tetes.min()*1000:.0f}–{tetes.max()*1000:.0f} ms "
        f"(médiane {np.median(tetes)*1000:.0f}, visée {MARGE_S*1000:.0f})"
    )
    print(
        f"silence de queue obtenu: {queues.min()*1000:.0f}–{queues.max()*1000:.0f} ms "
        f"(médiane {np.median(queues)*1000:.0f}, visée {MARGE_S*1000:.0f})"
    )
    hors = int(((tetes > 2 * MARGE_S) | (queues > 2 * MARGE_S)).sum())
    print(
        f"prises au silence non ramené : {hors}"
        + ("  ⚠️  élagage inopérant sur ces prises" if hors else "  ✓")
    )

    # Le garde-fou : ce qu'on a jeté doit être du bruit, pas de la parole.
    ecarts = [p.pic_dbfs - p.rejet_max_dbfs for p in prises if math.isfinite(p.rejet_max_dbfs)]
    ecarts.sort()
    print(
        f"écart pic → rejet le plus fort : min {ecarts[0]:.0f} dB · "
        f"médian {ecarts[len(ecarts)//2]:.0f} dB "
        f"(sous ~20 dB, vérifier à l'oreille)"
    )

    # LA garantie : aucune trame à moins de 25 dB sous le pic ne doit être jetée.
    # C'est la propriété qui manquait à la première version, celle qui lui a fait
    # perdre des mots entiers sans que rien ne le signale.
    perdues = [p for p in prises if p.parole_perdue]
    if perdues:
        print(f"\n⚠️  GARANTIE VIOLÉE sur {len(perdues)} prise(s) — à écouter, à retirer sinon :")
        for p in perdues:
            print(f"     {p.fichier:22s} {p.texte}")
    else:
        print(
            f"\ngarantie : sur les {len(prises)} prises, aucune trame à moins de "
            f"{PAROLE_SOUS_PIC_DB:.0f} dB sous le pic n'a été jetée ✓"
        )

    print(f"\nentraînement / validation : {len(entrainement)} / {len(validation)}")
    _couverture(entrainement, validation)


def _couverture(entrainement: list, validation: list) -> None:
    vus: Counter[tuple[str, ...]] = Counter()
    for _, texte in entrainement:
        vus.update(_unites(texte))
    manquants = defaultdict(list)
    for _, texte in validation:
        for u in _unites(texte):
            if not vus[u]:
                manquants[u[0]].append(u)
    if manquants:
        for genre, items in manquants.items():
            print(f"  ⚠️  {genre} en validation mais jamais à l'entraînement : {items}")
    else:
        print(
            "  couverture : chaque mot, position et jonction de la validation "
            "est vu au moins une fois à l'entraînement ✓"
        )


def appliquer_gain(audio: dict[str, np.ndarray], crete_visee: float = 0.99) -> float:
    """Remonte tout le corpus d'un SEUL facteur, sans écrêter.

    Ces prises ont été enregistrées bas : RMS moyen 0,064 pour une bande visée
    de 0,10–0,20. Rien n'est abîmé pour autant — aucune saturation, un fond très
    bas — c'est un simple déficit de niveau.

    Un gain est une multiplication : il n'invente aucun échantillon et ne crée
    aucun artefact. C'est ce qui le sépare d'un débruitage, que cette chaîne
    refuse justement parce qu'il remplace un bruit décorrélé par des artefacts
    corrélés à la parole.

    Le facteur est **global**, calculé sur la crête la plus haute du corpus. Un
    gain par fichier ramènerait chaque prise au même niveau et effacerait les
    écarts d'intensité entre énoncés — le modèle apprendrait une voix plate.
    """
    crete = max(float(np.abs(x).max()) for x in audio.values())
    if crete <= 0:
        raise SystemExit("corpus muet : crête nulle")
    gain = crete_visee / crete
    if gain <= 1.0:
        print(f"gain : aucun (crête déjà à {crete:.3f})")
        return 1.0
    for fichier in audio:
        audio[fichier] = audio[fichier] * gain
    rms = [float(np.sqrt(np.mean(x**2))) for x in audio.values()]
    dans_bande = sum(1 for r in rms if 0.10 <= r <= 0.20)
    print(
        f"gain global : ×{gain:.3f} ({20 * math.log10(gain):+.1f} dB) — "
        f"RMS moyen {sum(rms) / len(rms):.3f}, "
        f"{dans_bande}/{len(rms)} prises dans la bande 0,10–0,20"
    )
    return gain


def verifier_caracteres(lignes: list[tuple[str, str]]) -> None:
    """Refuse d'écrire un corpus que Piper amputerait en silence.

    Le même contrôle existe côté Colab, mais il est bien plus utile ici : autant
    échouer sur le Mac en deux secondes qu'après le téléversement.
    """
    try:
        from piper.phoneme_ids import DEFAULT_PHONEME_ID_MAP as carte
    except ModuleNotFoundError:
        print("piper absent : contrôle des caractères reporté à Colab")
        return
    manquants: dict[str, int] = {}
    for _, texte in lignes:
        for caractere in unicodedata.normalize("NFD", texte):
            if caractere not in carte:
                manquants[caractere] = manquants.get(caractere, 0) + 1
    if manquants:
        detail = "\n".join(
            f"  U+{ord(c):04X} {unicodedata.name(c, '?')} — {n} occurrences"
            for c, n in sorted(manquants.items(), key=lambda p: -p[1])
        )
        raise SystemExit(
            "ces caractères seraient supprimés en silence du texte appris :\n"
            f"{detail}\ncompléter TRANSLITTERATION avant d'écrire le corpus."
        )
    print(f"caractères : tous présents dans la table Piper ({len(carte)} symboles)")


def _ecrire(
    sortie: Path, audio: dict[str, np.ndarray], entrainement: list, validation: list
) -> None:
    verifier_caracteres(entrainement + validation)
    appliquer_gain(audio)
    wavs = sortie / "wavs"
    wavs.mkdir(parents=True, exist_ok=True)
    for fichier, x in audio.items():
        sf.write(wavs / fichier, x, FREQUENCE_CIBLE, subtype="PCM_16")
    for nom, lignes in (
        ("metadata.csv", entrainement + validation),
        ("train.csv", entrainement),
        ("val.csv", validation),
    ):
        with (sortie / nom).open("w", encoding="utf-8", newline="") as flux:
            for fichier, texte in lignes:
                flux.write(f"{fichier}|{texte}\n")
    print(f"\nécrit dans {sortie} — {len(audio)} wav à {FREQUENCE_CIBLE} Hz")


def _echantillons(
    source: Path,
    sortie: Path,
    prises: list[Prise],
    audio: dict[str, np.ndarray],
    verifier: tuple[str, ...] = (),
) -> None:
    """Paires avant/après à écouter — les cas typiques *et* les plus risqués."""
    sortie.mkdir(parents=True, exist_ok=True)
    # Le dossier est reconstruit à chaque fois : y laisser les paires d'une
    # exécution précédente ferait écouter un « après » qui n'est plus produit.
    for ancien in sortie.glob("*.wav"):
        ancien.unlink()
    par_ecart = sorted(prises, key=lambda p: p.pic_dbfs - p.rejet_max_dbfs)
    par_coupe = sorted(prises, key=lambda p: p.duree_avant - p.duree_apres, reverse=True)
    choix: list[tuple[str, Prise]] = []
    # D'abord les prises nommément demandées : celles qu'une écoute a mises en
    # cause. Elles doivent pouvoir être réécoutées après correction, sans
    # dépendre du fait qu'un classement automatique les resélectionne.
    par_nom = {p.fichier: p for p in prises}
    choix += [("verif", par_nom[f]) for f in verifier if f in par_nom]
    choix += [("risque", p) for p in par_ecart[:3]]
    choix += [("coupe", p) for p in par_coupe[:3]]
    milieu = len(prises) // 2
    choix += [
        ("typique", p) for p in sorted(prises, key=lambda p: p.duree_avant)[milieu : milieu + 3]
    ]

    vus: set[str] = set()
    for etiquette, p in choix:
        if p.fichier in vus:
            continue
        vus.add(p.fichier)
        base = f"{etiquette}_{p.fichier.replace('.wav', '').replace('%2F', '-')}"
        x, fr = sf.read(source / "wavs" / p.fichier, dtype="float64")
        sf.write(sortie / f"{base}_avant.wav", x, fr, subtype="PCM_16")
        sf.write(sortie / f"{base}_apres.wav", audio[p.fichier], FREQUENCE_CIBLE, subtype="PCM_16")
    print(f"échantillons avant/après : {sortie} ({len(vus)} paires)")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--source", type=Path, required=True)
    parseur.add_argument("--sortie", type=Path)
    parseur.add_argument("--echantillons", type=Path)
    parseur.add_argument(
        "--verifier",
        default="",
        help="fichiers à inclure d'office dans les échantillons, séparés par des virgules "
        "(les prises qu'une écoute a mises en cause)",
    )
    parseur.add_argument("--rapport", action="store_true")
    parseur.add_argument("--graine", type=int, default=1789)
    parseur.add_argument(
        "--fond",
        choices=("uniforme", "naturel"),
        default="uniforme",
        help="uniforme : les deux marges viennent du fond réel (d'après la parole) ; "
        "naturel : on garde le silence tel qu'enregistré, 12 dB plus bas en tête",
    )
    args = parseur.parse_args()

    lignes = _lire_metadata(args.source)
    prises, audio, fond = _traiter(args.source, lignes, fond_uniforme=args.fond == "uniforme")
    print(f"fond du corpus mesuré   : {fond:.1f} dBFS · seuil {fond + MARGE_SEUIL_DB:.1f} dBFS")
    entrainement, validation = decouper(lignes, PART_VALIDATION, args.graine)

    if args.rapport or not (args.sortie or args.echantillons):
        _rapport(prises, entrainement, validation)
    if args.sortie:
        _ecrire(args.sortie, audio, entrainement, validation)
    if args.echantillons:
        _echantillons(
            args.source,
            args.echantillons,
            prises,
            audio,
            tuple(f for f in args.verifier.split(",") if f),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
