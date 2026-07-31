#!/usr/bin/env python3
"""Prepare adab-tech/murya-piper-hausa-tts for Sherpa-ONNX.

The upstream ONNX file is a Piper graph without the model metadata required by
Sherpa-ONNX.  The upstream model is grapheme-based (``phoneme_type: text``), so
the correct Sherpa frontend is ``characters``: no eSpeak data or lexicon is
needed.  This script validates that assumption, creates ``tokens.txt`` from the
upstream JSON, and adds the required metadata to the ONNX graph.

Run from the Flutter project directory with, for example:

    uv run --with onnx==1.17.0 python tool/prepare_hausa_tts_model.py
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import onnx

ASSET_DIR = Path(__file__).resolve().parents[1] / "assets/models/hausa_tts"
MODEL_PATH = ASSET_DIR / "model.onnx"
CONFIG_PATH = ASSET_DIR / "model.onnx.json"
TOKENS_PATH = ASSET_DIR / "tokens.txt"
MANIFEST_PATH = ASSET_DIR / "asset_manifest.json"

UPSTREAM_REPOSITORY = "adab-tech/murya-piper-hausa-tts"
UPSTREAM_REVISION = "7eccd91ec0dc154c789b778c924b89f59a0dbccb"
UPSTREAM_MODEL_SHA256 = "7889e1a9e07cabf6e1cbec4ce09d8eed49fc63bb729770f60dcb7de2f1d34c74"
REQUIRED_VOICE = "M3"
EXPECTED_M3_ID = 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_and_validate_config() -> dict:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("phoneme_type") != "text":
        raise RuntimeError(
            "Ce modèle n'est plus graphémique (phoneme_type != text) ; "
            "réévaluer le phonémiseur avant de créer les assets."
        )

    speaker_map = config.get("speaker_id_map")
    if not isinstance(speaker_map, dict) or REQUIRED_VOICE not in speaker_map:
        raise RuntimeError("La voix obligatoire M3 est absente de speaker_id_map.")
    if speaker_map[REQUIRED_VOICE] != EXPECTED_M3_ID:
        raise RuntimeError(
            f"L'identifiant M3 vaut {speaker_map[REQUIRED_VOICE]!r}, "
            f"mais la révision validée attend {EXPECTED_M3_ID}."
        )

    token_map = config.get("phoneme_id_map")
    if not isinstance(token_map, dict) or not token_map:
        raise RuntimeError("phoneme_id_map est absent ou vide.")
    for special, expected in {"_": 0, "^": 1, "$": 2, " ": 3}.items():
        if token_map.get(special) != [expected]:
            raise RuntimeError(
                f"Jeton Piper inattendu pour {special!r}: " f"{token_map.get(special)!r}."
            )
    return config


def write_tokens(config: dict) -> None:
    entries: list[tuple[int, str]] = []
    seen_ids: set[int] = set()
    for symbol, ids in config["phoneme_id_map"].items():
        if len(symbol) != 1 or not isinstance(ids, list) or len(ids) != 1:
            raise RuntimeError(f"Jeton non compatible characters: {symbol!r}={ids!r}")
        token_id = ids[0]
        if not isinstance(token_id, int) or token_id in seen_ids:
            raise RuntimeError(f"Identifiant de jeton invalide ou dupliqué: {token_id!r}")
        seen_ids.add(token_id)
        entries.append((token_id, symbol))

    # Sherpa represents a literal space with a line containing only its ID.
    lines = [
        str(token_id) if symbol == " " else f"{symbol} {token_id}"
        for token_id, symbol in sorted(entries)
    ]
    TOKENS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_sherpa_metadata(config: dict) -> None:
    model = onnx.load(MODEL_PATH, load_external_data=False)
    existing = {entry.key: entry.value for entry in model.metadata_props}
    already_prepared = existing.get("hausa_tts_source_revision") == UPSTREAM_REVISION

    if not already_prepared:
        actual_hash = sha256(MODEL_PATH)
        if actual_hash != UPSTREAM_MODEL_SHA256:
            raise RuntimeError(
                "Le modèle ONNX ne correspond ni à l'original validé ni à un "
                f"modèle déjà préparé (SHA-256: {actual_hash})."
            )

    sample_rate = config.get("audio", {}).get("sample_rate")
    num_speakers = config.get("num_speakers")
    if sample_rate != 22050 or num_speakers != 8:
        raise RuntimeError(f"Métadonnées amont inattendues: {sample_rate=} {num_speakers=}")

    metadata = {
        "model_type": "vits",
        "comment": "piper; grapheme frontend prepared for sherpa-onnx",
        "language": "Hausa",
        "voice": REQUIRED_VOICE,
        "frontend": "characters",
        "sample_rate": str(sample_rate),
        "n_speakers": str(num_speakers),
        "add_blank": "1",
        "blank_id": "0",
        "bos_id": "1",
        "eos_id": "2",
        "use_eos_bos": "1",
        "pad_id": "0",
        "punctuation": "!?.,:;-",
        "hausa_tts_source": UPSTREAM_REPOSITORY,
        "hausa_tts_source_revision": UPSTREAM_REVISION,
        "hausa_tts_required_voice": REQUIRED_VOICE,
    }
    merged = {**existing, **metadata}
    del model.metadata_props[:]
    for key, value in sorted(merged.items()):
        entry = model.metadata_props.add()
        entry.key = key
        entry.value = value

    temporary = MODEL_PATH.with_suffix(".onnx.preparing")
    onnx.save(model, temporary)
    os.replace(temporary, MODEL_PATH)


def write_manifest() -> None:
    files = {}
    for path in (MODEL_PATH, CONFIG_PATH, TOKENS_PATH):
        files[path.name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    manifest = {
        "format": 1,
        "source": UPSTREAM_REPOSITORY,
        "source_revision": UPSTREAM_REVISION,
        "upstream_model_sha256": UPSTREAM_MODEL_SHA256,
        "runtime": "sherpa_onnx",
        "frontend": "characters",
        "phonemizer_resources": [],
        "voice": REQUIRED_VOICE,
        "expected_speaker_id": EXPECTED_M3_ID,
        "files": files,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    config = load_and_validate_config()
    write_tokens(config)
    add_sherpa_metadata(config)
    write_manifest()
    print(f"Modèle Sherpa-ONNX préparé: {MODEL_PATH}")
    print(f"Voix obligatoire validée: {REQUIRED_VOICE}={EXPECTED_M3_ID}")
    print(f"SHA-256 préparé: {sha256(MODEL_PATH)}")


if __name__ == "__main__":
    main()
