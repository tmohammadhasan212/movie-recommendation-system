"""MovieLens historical rating popularity and genre-based fallback ranking."""

from __future__ import annotations

from dataclasses import dataclass

PRIOR_COUNT = 20
MIN_POPULARITY_SUPPORT = 5
SIMILAR_GENRE_WEIGHT = 0.55
SIMILAR_EMBEDDING_WEIGHT = 0.35
CO_RATING_PRIOR = 10


@dataclass(frozen=True)
class Candidate:
    movie_id: int
    genres: frozenset[str]
    rating_sum: float
    rating_count: int


@dataclass(frozen=True)
class Ranked:
    movie_id: int
    score: float
    source: str
    explanation_code: str


def smoothed_popularity(rating_sum: float, rating_count: int, global_mean: float) -> float:
    return (rating_sum + PRIOR_COUNT * global_mean) / (rating_count + PRIOR_COUNT)


def genre_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def shrunk_correlation(correlation: float | None, support: int) -> float | None:
    if correlation is None or support < 2:
        return None
    correlation = min(1.0, max(0.0, correlation))
    return correlation * support / (support + CO_RATING_PRIOR)


def similarity_percentage(
    genre_score: float,
    embedding_score: float | None = None,
    co_rating_score: float | None = None,
    *,
    same_collection: bool = False,
) -> int:
    """Blend available similarity evidence without popularity influencing the value."""
    genre_score = min(1.0, max(0.0, genre_score))
    signals = [(0.5, genre_score)]
    if co_rating_score is not None:
        signals.append((0.35, min(1.0, max(0.0, co_rating_score))))
    if embedding_score is not None:
        signals.append((0.15, min(1.0, max(0.0, embedding_score))))
    base = sum(weight * score for weight, score in signals) / sum(
        weight for weight, _ in signals
    )
    if same_collection:
        base = 0.65 + 0.35 * base
    return round(min(1.0, max(0.0, base)) * 100)


def rank(
    candidates: list[Candidate],
    *,
    global_mean: float,
    preferred_genres: frozenset[str] = frozenset(),
    seen_ids: frozenset[int] = frozenset(),
    limit: int = 20,
) -> list[Ranked]:
    rows: list[Ranked] = []
    for movie in candidates:
        if movie.movie_id in seen_ids:
            continue
        popularity = smoothed_popularity(movie.rating_sum, movie.rating_count, global_mean) / 5
        overlap = genre_similarity(movie.genres, preferred_genres)
        if preferred_genres and overlap > 0:
            score = 0.65 * popularity + 0.35 * overlap
            rows.append(Ranked(movie.movie_id, score, "genre_content", "selected_genres"))
        elif movie.rating_count >= MIN_POPULARITY_SUPPORT:
            rows.append(Ranked(movie.movie_id, popularity, "historical_popularity", "popular_in_catalog"))
    rows.sort(key=lambda item: (-item.score, item.movie_id))
    return rows[:limit]
