"""MovieLens historical rating popularity and genre-based fallback ranking."""

from __future__ import annotations

from dataclasses import dataclass

PRIOR_COUNT = 20
MIN_POPULARITY_SUPPORT = 5


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
