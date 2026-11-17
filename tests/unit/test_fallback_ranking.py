from backend.app.modules.recommendations.service import (
    Candidate,
    genre_similarity,
    rank,
    shrunk_correlation,
    similarity_percentage,
    smoothed_popularity,
)


def test_bayesian_prior_and_support() -> None:
    assert smoothed_popularity(0, 0, 3.5) == 3.5
    assert smoothed_popularity(50, 10, 3.5) == 4
    low_support = Candidate(1, frozenset({"Drama"}), 20, 4)
    supported = Candidate(2, frozenset({"Comedy"}), 25, 5)
    assert [row.movie_id for row in rank([low_support, supported], global_mean=3.5)] == [2]


def test_genre_cold_start_and_seen_filter() -> None:
    candidates = [
        Candidate(1, frozenset({"Drama"}), 0, 0),
        Candidate(2, frozenset({"Comedy"}), 25, 5),
    ]
    result = rank(candidates, global_mean=3.5, preferred_genres=frozenset({"Drama"}), seen_ids=frozenset({2}))
    assert [row.movie_id for row in result] == [1]
    assert result[0].explanation_code == "selected_genres"


def test_similarity_handles_missing_genres() -> None:
    assert genre_similarity(frozenset(), frozenset({"Drama"})) == 0
    assert genre_similarity(frozenset({"Drama"}), frozenset({"Drama", "Comedy"})) == 0.5


def test_similarity_percentage_excludes_popularity_and_supports_genre_fallback() -> None:
    assert similarity_percentage(0.5) == 50
    assert similarity_percentage(1.0, 1.0, 1.0) == 100
    assert similarity_percentage(0.5, 0.75, 0.6) == 57
    assert similarity_percentage(0.75, 0.25, 0.53, same_collection=True) == 86


def test_co_rating_correlation_is_shrunk_for_low_support() -> None:
    assert shrunk_correlation(None, 100) is None
    assert shrunk_correlation(0.8, 1) is None
    assert shrunk_correlation(-0.5, 100) == 0
    assert shrunk_correlation(0.8, 10) == 0.4
    assert shrunk_correlation(0.8, 90) == 0.72
