from __future__ import annotations

import json
import os
import random
import subprocess
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch
from safetensors.torch import save_file
from torch import nn

from backend.ml.artifacts import sha256
from backend.ml.data import SourceRating, movies, ratings
from backend.ml.evaluate import EvaluationInputs, evaluate
from backend.ml.features import genre_profiles
from backend.ml.models import MatrixFactorization

SEED = 20261113


def _git_sha(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def split_positive_history(rows: list[SourceRating]) -> tuple[dict[int, list[int]], dict[int, int], dict[int, int], dict[int, set[int]]]:
    by_user: dict[int, list[SourceRating]] = defaultdict(list)
    all_seen: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        all_seen[row.user_id].add(row.movie_id)
        if row.rating >= 4:
            by_user[row.user_id].append(row)
    train: dict[int, list[int]] = {}
    validation: dict[int, int] = {}
    test: dict[int, int] = {}
    for user_id, history in by_user.items():
        ordered = sorted(history, key=lambda row: (row.occurred_at, row.movie_id))
        if len(ordered) < 7:
            continue
        train[user_id] = [row.movie_id for row in ordered[:-2]]
        validation[user_id] = ordered[-2].movie_id
        test[user_id] = ordered[-1].movie_id
    return train, validation, test, all_seen


def train_model(data_dir: Path, models_dir: Path, *, epochs: int = 8, factors: int = 48) -> Path:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    source_movies = list(movies(data_dir / "movies.csv"))
    item_ids = [movie.movie_id for movie in source_movies]
    known = set(item_ids)
    source_ratings = list(ratings(data_dir / "ratings.csv", known))
    train_positive, validation, test, all_seen = split_positive_history(source_ratings)
    if not train_positive:
        raise ValueError("No users have enough positive history for temporal evaluation")
    user_ids = sorted(train_positive)
    user_index = {user_id: index for index, user_id in enumerate(user_ids)}
    item_index = {item_id: index for index, item_id in enumerate(item_ids)}
    rng = random.Random(SEED)
    examples: list[tuple[int, int, float]] = []
    catalog = set(item_ids)
    explicit_negative = defaultdict(set)
    for row in source_ratings:
        if row.user_id in user_index and row.rating <= 2.5:
            explicit_negative[row.user_id].add(row.movie_id)
    for user_id, positives in train_positive.items():
        negative_pool = sorted(catalog - all_seen[user_id])
        sampled = rng.sample(negative_pool, min(len(positive_pool := positives), len(negative_pool)))
        examples.extend((user_index[user_id], item_index[item_id], 1.0) for item_id in positive_pool)
        examples.extend((user_index[user_id], item_index[item_id], 0.0) for item_id in sampled)
        examples.extend((user_index[user_id], item_index[item_id], 0.0) for item_id in sorted(explicit_negative[user_id]))
    rng.shuffle(examples)
    user_tensor = torch.tensor([row[0] for row in examples], dtype=torch.long)
    item_tensor = torch.tensor([row[1] for row in examples], dtype=torch.long)
    label_tensor = torch.tensor([row[2] for row in examples], dtype=torch.float32)
    model = MatrixFactorization(len(user_ids), len(item_ids), factors)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.025, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    start = time.perf_counter()
    losses: list[float] = []
    for _ in range(epochs):
        generator = torch.Generator().manual_seed(SEED + len(losses))
        permutation = torch.randperm(len(examples), generator=generator)
        total = 0.0
        for offset in range(0, len(examples), 2048):
            batch = permutation[offset : offset + 2048]
            optimizer.zero_grad()
            loss = loss_fn(model(user_tensor[batch], item_tensor[batch]), label_tensor[batch])
            loss.backward()
            optimizer.step()
            total += loss.item() * len(batch)
        losses.append(total / len(examples))
    duration = time.perf_counter() - start
    model.eval()
    item_embeddings = model.item_embeddings.weight.detach().cpu()
    item_bias = model.item_bias.weight.detach().cpu().squeeze(1)
    user_scores = {}
    with torch.no_grad():
        for user_id, index in user_index.items():
            scores = item_embeddings @ model.user_embeddings.weight[index].cpu() + item_bias
            user_scores[user_id] = scores.numpy()
    counts = Counter(row.movie_id for row in source_ratings)
    popularity = np.array([counts[item_id] for item_id in item_ids], dtype=np.float32)
    movie_genres, profiles = genre_profiles(source_movies, {user: set(items) for user, items in train_positive.items()})
    metrics = evaluate(EvaluationInputs(item_ids, test, {user: set(train_positive[user]) | {validation[user]} for user in test}, user_scores, popularity, movie_genres, profiles))
    metrics["training"] = {"final_loss": losses[-1], "duration_seconds": duration, "epochs": epochs, "examples": len(examples), "eligible_users": len(user_ids)}
    root = Path(__file__).resolve().parents[2]
    version = datetime.now(UTC).strftime("mf-%Y%m%dT%H%M%SZ")
    output = models_dir / "versions" / version
    output.mkdir(parents=True, exist_ok=False)
    save_file({"item_embeddings": item_embeddings, "item_bias": item_bias}, output / "item_embeddings.safetensors")
    (output / "item_map.json").write_text(json.dumps(item_ids) + "\n")
    (output / "evaluation.json").write_text(json.dumps(metrics, indent=2) + "\n")
    source_manifest = json.loads((data_dir.parent / "manifest.json").read_text())
    manifest = {
        "schema_version": 1,
        "version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "source_sha256": source_manifest["sha256"],
        "code_commit": _git_sha(root),
        "seed": SEED,
        "hyperparameters": {"epochs": epochs, "factors": factors, "learning_rate": 0.025, "positive_threshold": 4, "negative_threshold": 2.5},
        "python": os.sys.version.split()[0],
        "torch": torch.__version__,
        "checksums": {},
    }
    for name in ("item_embeddings.safetensors", "item_map.json", "evaluation.json"):
        manifest["checksums"][name] = sha256(output / name)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return output
