"""Convertit la voix Piper hausa au format `sherpa-onnx`, pour l'application mobile.

À exécuter dans Colab, après `--exporter` (et après la quantification int8 si tu
la retiens) :

    !python hausa_tts/convert_tts_for_sherpa.py \\
        --modele /content/drive/MyDrive/hausa_tts/hausa-nombres-int8.onnx \\
        --config /content/drive/MyDrive/hausa_tts/hausa-nombres.onnx.json \\
        --sortie /content/drive/MyDrive/hausa_tts/sherpa

Produit un dossier prêt à embarquer : le modèle annoté et son `tokens.txt`.


Pourquoi ce script existe, et pas `add_meta_data.py` de sherpa-onnx
-------------------------------------------------------------------

Le script officiel pose `has_espeak = 1` et ne l'annule que pour le pinyin
chinois. Notre voix est entraînée sur des **graphèmes** : espeak-ng
phonétiserait le hausa en voix française avant d'atteindre le réseau, et le
résultat serait du charabia. Sans erreur, sans avertissement.

La route correcte, lue dans `offline-tts-vits-impl.h` : la métadonnée
`frontend = "characters"` fait choisir `OfflineTtsCharacterFrontend`, testé
**avant** toutes les branches espeak. Ce frontend n'appelle jamais le
phonétiseur — d'où, en prime, aucune donnée espeak-ng à embarquer.

Deux métadonnées, deux rôles qu'il ne faut pas confondre : `frontend` décide
**comment le texte devient des identifiants**, `comment` décide **quelles entrées
sont présentées au graphe ONNX**. Voir `COMMENTAIRE` plus bas — les confondre
coûte une violation de segment silencieuse.


L'équivalence est exacte, et ce script la vérifie
--------------------------------------------------

Piper assemble ses identifiants ainsi (`phoneme_ids.py`) :

    [BOS] [PAD] car [PAD] car [PAD] … [PAD] [EOS]

`OfflineTtsCharacterFrontend`, avec `add_blank=1` et `use_eos_bos=1`, assemble
exactement la même suite. Les valeurs de Piper — `^`=1, `_`=0, `$`=2 — deviennent
`bos_id`, `blank_id`, `eos_id`.

Plutôt que de faire confiance à cette lecture, `_verifier_equivalence` réimplémente
le frontend C++ en Python et compare les identifiants produits, énoncé par énoncé,
avec ceux de Piper. Une divergence ne s'entendrait qu'à l'usage, sur un appareil,
après intégration : c'est le pire endroit pour la découvrir.


Deux pièges du format `tokens.txt`
-----------------------------------

Lus dans `ReadTokens` (`offline-tts-character-frontend.cc`) :

1. **L'espace s'écrit seul.** Le lecteur fait `iss >> sym` puis, s'il atteint la
   fin de ligne, comprend que ce qu'il a lu était l'identifiant et pose
   `sym = " "`. La ligne de l'espace ne contient donc *que* son numéro.
2. **Un symbole, un point de code.** Le lecteur *quitte le programme* si un
   symbole en compte plusieurs. La table de Piper en contient cinq — les
   diphtongues `aɪ aʊ ɔɪ eɪ oʊ` — qu'on écarte. Elles ne peuvent pas apparaître
   dans du texte hausa, qui s'écrit en lettres latines simples.
"""

from __future__ import annotations

import argparse
import json
import shutil
import unicodedata
from pathlib import Path

#: Ce que Piper met de part et d'autre de chaque caractère, et que le frontend
#: « characters » de sherpa-onnx reproduit à partir des métadonnées.
BOS, PAD, EOS = "^", "_", "$"

#: Le commentaire **doit** contenir « piper », et ce n'est pas cosmétique.
#:
#: sherpa-onnx y cherche des mots-clés pour poser `is_piper`, lequel ne choisit
#: pas le phonétiseur — il choisit la **signature d'entrée du graphe ONNX** :
#:
#:     if (is_piper || is_coqui) return RunVitsPiperOrCoqui(...);
#:         // entrées : [x, x_length, scales(3 flottants)]
#:     return RunVits(...);
#:         // entrées : [x, x_length, noise_scale, length_scale, noise_scale_w]
#:
#: Un modèle exporté par Piper attend la première forme. Sans ce mot, sherpa-onnx
#: présente cinq entrées à un graphe qui en compte trois : **violation de segment**,
#: sans message. (Constaté, puis lu dans `offline-tts-vits-model.cc`.)
#:
#: Le phonétiseur, lui, reste écarté par deux verrous indépendants : `InitFrontend`
#: teste `frontend == "characters"` *avant* toute branche espeak, et cette branche
#: exige de surcroît un `data_dir` non vide, que nous laissons vide.
COMMENTAIRE = "piper — hausa-nombres, graphemes, frontend=characters"


def _table_symboles(carte: dict[str, list[int]]) -> tuple[list[str], list[str]]:
    """Lignes de `tokens.txt`, et les symboles écartés (avec leur raison)."""
    lignes: list[str] = []
    ecartes: list[str] = []
    for symbole, identifiants in sorted(carte.items(), key=lambda p: p[1][0]):
        identifiant = identifiants[0]
        if len(symbole) != 1:
            ecartes.append(f"{symbole!r} (id {identifiant}) — plusieurs points de code")
            continue
        # L'espace ne peut pas s'écrire « <espace> <id> » : le lecteur découpe sur
        # les blancs. Sa ligne ne porte que l'identifiant.
        lignes.append(str(identifiant) if symbole == " " else f"{symbole} {identifiant}")
    return lignes, ecartes


def _ids_piper(texte: str, carte: dict[str, list[int]]) -> list[int]:
    """Les identifiants tels que Piper les fabrique — la référence."""
    ids = list(carte[BOS]) + list(carte[PAD])
    for caractere in unicodedata.normalize("NFD", texte):
        if caractere not in carte:
            continue
        ids += list(carte[caractere]) + list(carte[PAD])
    return ids + list(carte[EOS])


def _ids_sherpa(texte: str, carte: dict[str, list[int]]) -> list[int]:
    """Réimplémentation de `OfflineTtsCharacterFrontend` (add_blank, use_eos_bos).

    Le frontend C++ met le texte en minuscules avant tout : on fait de même, sans
    quoi la comparaison mentirait sur un corpus qui contiendrait des majuscules.
    """
    table = {s: i[0] for s, i in carte.items() if len(s) == 1}
    ids = [carte[BOS][0], carte[PAD][0]]
    for caractere in unicodedata.normalize("NFD", texte.lower()):
        if caractere in table:
            ids += [table[caractere], carte[PAD][0]]
    return ids + [carte[EOS][0]]


def _verifier_equivalence(carte: dict[str, list[int]], corpus: Path | None) -> None:
    """Compare les deux chaînes d'identifiants sur de vrais énoncés."""
    enonces = [
        "zangou hakou di wey cindi yega",
        "zambar iwey cindi hinza da zangou gou da waranza cindi iddu",
        "zambar fo da zangou hinka di wey kanga izabou zangou hakou da waygou cindi iyye",
    ]
    if corpus is not None:
        for nom in ("train.csv", "val.csv"):
            fichier = corpus / nom
            if fichier.exists():
                enonces += [
                    ligne.split("|", 1)[1]
                    for ligne in fichier.read_text(encoding="utf-8").splitlines()
                    if "|" in ligne
                ]

    divergences = [t for t in enonces if _ids_piper(t, carte) != _ids_sherpa(t, carte)]
    if divergences:
        raise SystemExit(
            f"{len(divergences)} énoncé(s) sur {len(enonces)} donnent des identifiants\n"
            "différents entre Piper et le frontend de sherpa-onnx. Le modèle\n"
            "prononcerait autre chose que ce qu'il a appris. Premier écart :\n"
            f"  texte  : {divergences[0]}\n"
            f"  piper  : {_ids_piper(divergences[0], carte)}\n"
            f"  sherpa : {_ids_sherpa(divergences[0], carte)}"
        )
    print(f"équivalence des identifiants vérifiée sur {len(enonces)} énoncés")


def _annoter(modele: Path, sortie: Path, config: dict) -> None:
    """Écrit le modèle annoté des métadonnées que sherpa-onnx exige."""
    import onnx

    carte = config["phoneme_id_map"]
    # `sample_rate`, `n_speakers`, `language` et `comment` n'ont pas de valeur par
    # défaut côté sherpa-onnx : leur absence fait échouer le chargement.
    metadonnees = {
        "model_type": "vits",
        "comment": COMMENTAIRE,
        "language": "Hausa",
        "voice": "hausa-nombres",
        "sample_rate": config["audio"]["sample_rate"],
        "n_speakers": config.get("num_speakers", 1),
        "frontend": "characters",  # la ligne qui évite espeak-ng
        "add_blank": 1,
        "use_eos_bos": 1,
        "bos_id": carte[BOS][0],
        "eos_id": carte[EOS][0],
        "blank_id": carte[PAD][0],
        "pad_id": carte[PAD][0],
        "has_espeak": 0,
    }

    graphe = onnx.load(str(modele))
    del graphe.metadata_props[:]
    for cle, valeur in metadonnees.items():
        entree = graphe.metadata_props.add()
        entree.key, entree.value = cle, str(valeur)
    onnx.save(graphe, str(sortie))

    print(f"\nmodèle annoté : {sortie} ({sortie.stat().st_size / 1e6:.1f} Mo)")
    for cle, valeur in metadonnees.items():
        print(f"  {cle:12s} {valeur}")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--modele", type=Path, required=True, help="le .onnx exporté")
    parseur.add_argument("--config", type=Path, required=True, help="le .onnx.json de Piper")
    parseur.add_argument("--sortie", type=Path, required=True, help="dossier à produire")
    parseur.add_argument(
        "--corpus",
        type=Path,
        default=Path("/content/hausa_tts/tts_corpus"),
        help="corpus dont les énoncés servent au contrôle (défaut : %(default)s)",
    )
    args = parseur.parse_args()

    for chemin in (args.modele, args.config):
        if not chemin.exists():
            raise SystemExit(f"introuvable : {chemin}")

    config = json.loads(args.config.read_text(encoding="utf-8"))
    carte = config["phoneme_id_map"]

    if config.get("phoneme_type") != "text":
        raise SystemExit(
            f"phoneme_type vaut {config.get('phoneme_type')!r}, attendu 'text'.\n"
            "Ce convertisseur ne vaut que pour une voix entraînée sur des graphèmes."
        )

    _verifier_equivalence(carte, args.corpus if args.corpus.is_dir() else None)

    lignes, ecartes = _table_symboles(carte)
    args.sortie.mkdir(parents=True, exist_ok=True)
    jetons = args.sortie / "tokens.txt"
    jetons.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"tokens.txt : {len(lignes)} symboles")
    for raison in ecartes:
        print(f"  écarté — {raison}")

    _annoter(args.modele, args.sortie / "model.onnx", config)
    shutil.copy2(args.config, args.sortie / "piper-config.json")  # trace, non utilisée

    print(
        f"\nDossier prêt : {args.sortie}\n"
        "  model.onnx + tokens.txt suffisent au runtime ; aucune donnée espeak-ng\n"
        "  n'est nécessaire, le frontend « characters » ne la consulte jamais."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
