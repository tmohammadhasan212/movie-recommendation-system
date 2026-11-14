from __future__ import annotations

from collections import Counter

from backend.ml.data import SourceMovie


def genre_profiles(
    movies: list[SourceMovie], positives: dict[int, set[int]]
) -> tuple[dict[int, frozenset[str]], dict[int, Counter[str]]]:
    movie_genres = {movie.movie_id: frozenset(movie.genres) for movie in movies}
    profiles = {
        user: Counter(genre for movie_id in movie_ids for genre in movie_genres.get(movie_id, ()))
        for user, movie_ids in positives.items()
    }
    return movie_genres, profiles


def content_score(genres: frozenset[str], profile: Counter[str]) -> float:
    if not genres or not profile:
        return 0.0
    return sum(profile[genre] for genre in genres) / (len(genres) * max(profile.values()))
