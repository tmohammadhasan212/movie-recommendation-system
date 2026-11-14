from __future__ import annotations

import hashlib
import json
from pathlib import Path

REQUIRED_FILES = {"item_embeddings.safetensors", "item_map.json", "manifest.json", "evaluation.json"}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_artifact(path: Path) -> dict:
    missing = REQUIRED_FILES - {item.name for item in path.iterdir() if item.is_file()}
    if missing:
        raise ValueError(f"Model artifact is missing: {', '.join(sorted(missing))}")
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported model artifact schema")
    for name, expected in manifest.get("checksums", {}).items():
        if sha256(path / name) != expected:
            raise ValueError(f"Checksum mismatch for {name}")
    item_map = json.loads((path / "item_map.json").read_text())
    if not item_map or len(set(item_map)) != len(item_map):
        raise ValueError("Item map is empty or contains duplicates")
    return manifest
