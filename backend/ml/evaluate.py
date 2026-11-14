from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np

from backend.ml.features import content_score


@dataclass(frozen=True)
class EvaluationInputs:
    item_ids: list[int]
    test_items: dict[int, int]
    masked_items: dict[int, set[int]]
    user_scores: dict[int, np.ndarray]
    popularity: np.ndarray
    movie_genres: dict[int, frozenset[str]]
    genre_profiles: dict[int, Counter[str]]


def _normalize(values: np.ndarray) -> np.ndarray:
    minimum, maximum = float(values.min()), float(values.max())
    return (values - minimum) / (maximum - minimum) if maximum > minimum else np.zeros_like(values)


def evaluate(inputs: EvaluationInputs, k: int = 10) -> dict[str, dict[str, float]]:
    item_index = {item_id: index for index, item_id in enumerate(inputs.item_ids)}
    strategies = {name: {"hits": 0, "ndcg": 0.0, "recommended": set()} for name in ("popularity", "content", "collaborative", "hybrid")}
    evaluated = 0
    for user_id, target_id in inputs.test_items.items():
        if user_id not in inputs.user_scores or target_id not in item_index:
            continue
        collaborative = _normalize(inputs.user_scores[user_id].copy())
        popularity = _normalize(inputs.popularity.copy())
        profile = inputs.genre_profiles.get(user_id, Counter())
        content = np.array([content_score(inputs.movie_genres.get(item_id, frozenset()), profile) for item_id in inputs.item_ids], dtype=np.float32)
        score_sets = {
            "popularity": popularity,
            "content": 0.8 * content + 0.2 * popularity,
            "collaborative": collaborative,
            "hybrid": 0.6 * collaborative + 0.25 * content + 0.15 * popularity,
        }
        masked = inputs.masked_items.get(user_id, set()) - {target_id}
        for name, scores in score_sets.items():
            for item_id in masked:
                if item_id in item_index:
                    scores[item_index[item_id]] = -np.inf
            top = np.argpartition(scores, -k)[-k:]
            top = top[np.argsort(scores[top])[::-1]]
            ranked_ids = [inputs.item_ids[index] for index in top]
            strategies[name]["recommended"].update(ranked_ids)
            if target_id in ranked_ids:
                rank = ranked_ids.index(target_id) + 1
                strategies[name]["hits"] += 1
                strategies[name]["ndcg"] += 1 / math.log2(rank + 1)
        evaluated += 1
    if not evaluated:
        raise ValueError("No eligible source users for evaluation")
    catalog_size = len(inputs.item_ids)
    return {
        name: {
            "recall_at_10": values["hits"] / evaluated,
            "ndcg_at_10": values["ndcg"] / evaluated,
            "coverage_at_10": len(values["recommended"]) / catalog_size,
            "evaluated_users": evaluated,
        }
        for name, values in strategies.items()
    }
