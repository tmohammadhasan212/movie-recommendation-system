from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from safetensors.numpy import load_file

from backend.ml.artifacts import validate_artifact


@dataclass(frozen=True)
class ModelBundle:
    version: str
    item_ids: list[int]
    embeddings: np.ndarray
    bias: np.ndarray
    index: dict[int, int]


def load_bundle(path: Path) -> ModelBundle:
    manifest = validate_artifact(path)
    import json

    item_ids = json.loads((path / "item_map.json").read_text())
    tensors = load_file(path / "item_embeddings.safetensors")
    embeddings = tensors["item_embeddings"].astype(np.float32)
    bias = tensors["item_bias"].astype(np.float32)
    if embeddings.shape[0] != len(item_ids) or bias.shape != (len(item_ids),):
        raise ValueError("Artifact tensor dimensions do not match item map")
    return ModelBundle(manifest["version"], item_ids, embeddings, bias, {item_id: index for index, item_id in enumerate(item_ids)})


def app_user_scores(
    bundle: ModelBundle,
    positive: list[tuple[int, float]],
    negative: list[tuple[int, float]],
) -> np.ndarray | None:
    positives = [(bundle.index[item_id], rating) for item_id, rating in positive if item_id in bundle.index]
    if not positives:
        return None
    weights = np.array([max(0.5, rating - 3.5) for _, rating in positives], dtype=np.float32)
    vectors = bundle.embeddings[[index for index, _ in positives]]
    user_vector = np.average(vectors, axis=0, weights=weights)
    scores = bundle.embeddings @ user_vector + bundle.bias
    negatives = [bundle.index[item_id] for item_id, _ in negative if item_id in bundle.index]
    if negatives:
        negative_vector = bundle.embeddings[negatives].mean(axis=0)
        scores -= 0.4 * (bundle.embeddings @ negative_vector)
    return scores


def normalized(values: np.ndarray) -> np.ndarray:
    minimum, maximum = float(values.min()), float(values.max())
    return (values - minimum) / (maximum - minimum) if maximum > minimum else np.zeros_like(values)
