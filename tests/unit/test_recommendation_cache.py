from backend.app.api.v1.recommendations import _recommendation_cache_key


def test_anonymous_cache_key_tracks_model_and_limit() -> None:
    assert _recommendation_cache_key(
        user_id=None,
        profile_version=0,
        model_version="mf-v2",
        limit=20,
        include_watchlist=True,
    ) == "recommendations:anonymous:mf-v2:20"


def test_personalized_cache_key_tracks_profile_model_and_options() -> None:
    first = _recommendation_cache_key(
        user_id="user-1",
        profile_version=7,
        model_version=None,
        limit=12,
        include_watchlist=False,
    )
    updated = _recommendation_cache_key(
        user_id="user-1",
        profile_version=8,
        model_version=None,
        limit=12,
        include_watchlist=False,
    )

    assert first == "recommendations:user:user-1:7:fallback:12:0"
    assert updated != first
