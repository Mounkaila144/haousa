"""Fabrique l'archive unique à déposer sur Drive pour l'entraînement TTS.

Même principe que `bundle_for_colab.py` côté ASR, et pour la même raison : la
principale source d'erreurs a été d'oublier de recopier dans la session le
script qu'on venait de modifier. Un seul fichier à téléverser, corpus et code
ensemble, donc toujours cohérents.

    cd /Users/pc/project/Haousa
    .venv/bin/python entrainement/tts_training/bundle_tts_for_colab.py

Contenu de `hausa_tts.zip` (tout sous `hausa_tts/`) :

    tts_corpus/wavs/            375 clips élagués, 22 050 Hz
    tts_corpus/train.csv        356 énoncés — ce que Piper voit
    tts_corpus/val.csv          19 énoncés tenus à l'écart, pour l'écoute
    train_tts_piper_colab.py    l'entraînement
    convert_tts_for_sherpa.py   la conversion vers le format du mobile

`val.csv` voyage sans être donné à Piper : son `random_split` refait un tirage au
hasard et défairait le découpage qui préserve la couverture. Il sert à synthétiser
des énoncés que le modèle n'a jamais vus, et à les écouter.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOURCES = {
    "tts_corpus": ROOT / "dataset" / "tts" / "corpus",
    "train_tts_piper_colab.py": Path(__file__).with_name("train_tts_piper_colab.py"),
    "convert_tts_for_sherpa.py": Path(__file__).with_name("convert_tts_for_sherpa.py"),
}

EXCLUDED = {"__pycache__", ".DS_Store", ".pytest_cache"}


def _fichiers(source: Path):
    if source.is_file():
        yield source, source.name
        return
    for chemin in sorted(source.rglob("*")):
        if chemin.is_dir() or any(part in EXCLUDED for part in chemin.parts):
            continue
        yield chemin, str(chemin.relative_to(source.parent))


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument(
        "--sortie", type=Path, default=ROOT / "dataset" / "tts" / "hausa_tts.zip"
    )
    args = parseur.parse_args()

    manquants = [nom for nom, chemin in SOURCES.items() if not chemin.exists()]
    if manquants:
        raise SystemExit(
            "manquant : " + ", ".join(manquants) + "\n"
            "lancer d'abord prepare_tts_corpus.py avec --sortie"
        )

    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(args.sortie, "w", zipfile.ZIP_DEFLATED) as archive:
        for source in SOURCES.values():
            for chemin, relatif in _fichiers(source):
                archive.write(chemin, f"hausa_tts/{relatif}")
                total += 1
    taille = args.sortie.stat().st_size / 1e6
    print(f"{args.sortie} — {total} fichiers, {taille:.0f} Mo")
    print("à déposer dans le dossier Drive `hausa_tts`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
