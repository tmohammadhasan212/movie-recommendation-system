from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import update

from backend.app.core.db import SessionLocal
from backend.app.core.models import ModelVersion
from backend.ml.artifacts import sha256, validate_artifact

ROOT = Path(__file__).resolve().parents[2]


def publish(path: Path) -> str:
    manifest = validate_artifact(path)
    evaluation = json.loads((path / "evaluation.json").read_text())
    version = manifest["version"]
    artifact_hash = sha256(path / "item_embeddings.safetensors")
    with SessionLocal.begin() as db:
        db.execute(update(ModelVersion).where(ModelVersion.active.is_(True)).values(active=False, status="inactive"))
        existing = db.get(ModelVersion, version)
        if existing is None:
            db.add(
                ModelVersion(
                    version_id=version,
                    artifact_uri=str(path),
                    sha256=artifact_hash,
                    training_manifest_uri=str(path / "manifest.json"),
                    evaluation=evaluation,
                    status="active",
                    active=True,
                )
            )
        else:
            if existing.sha256 != artifact_hash:
                raise ValueError("Published version ID has a different artifact checksum")
            existing.status = "active"
            existing.active = True
    return version


if __name__ == "__main__":
    candidates = sorted((ROOT / "models" / "versions").glob("*/manifest.json"))
    if not candidates:
        raise SystemExit("No candidate artifact; run make train first")
    try:
        print(publish(candidates[-1].parent))
    except ValueError as error:
        raise SystemExit(str(error)) from error
