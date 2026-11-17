import httpx
import pytest

from backend.app.api.v1.catalog import movie_response
from backend.app.core.models import Movie
from backend.app.modules.catalog.tmdb import (
    TmdbClient,
    TmdbMetadataError,
    parse_movie_metadata,
    parse_poster_path,
)


def test_parse_poster_path_rejects_mismatched_or_unsafe_metadata() -> None:
    with pytest.raises(TmdbMetadataError, match="did not match"):
        parse_poster_path({"id": 2, "poster_path": "/safe.jpg"}, 1)
    with pytest.raises(TmdbMetadataError, match="invalid poster"):
        parse_poster_path({"id": 1, "poster_path": "https://example.com/a.jpg"}, 1)


def test_parse_movie_metadata_validates_and_normalizes_fields() -> None:
    metadata = parse_movie_metadata(
        {
            "id": 1,
            "poster_path": "/safe.jpg",
            "overview": "  A useful story.  ",
            "vote_average": 7.25,
            "vote_count": 123,
            "belongs_to_collection": {"id": 263, "name": "The Dark Knight Collection"},
        },
        1,
    )
    assert metadata.poster_path == "/safe.jpg"
    assert metadata.overview == "A useful story."
    assert metadata.vote_average == 7.25
    assert metadata.vote_count == 123
    assert metadata.collection_id == 263
    assert metadata.collection_name == "The Dark Knight Collection"

    with pytest.raises(TmdbMetadataError, match="vote average"):
        parse_movie_metadata(
            {"id": 1, "poster_path": None, "overview": "", "vote_average": 11, "vote_count": 1},
            1,
        )


def test_client_validates_configuration_and_fetches_poster() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/3/configuration":
            return httpx.Response(
                200,
                json={
                    "images": {
                        "secure_base_url": "https://image.tmdb.org/t/p/",
                        "poster_sizes": ["w185", "w500", "original"],
                    }
                },
            )
        return httpx.Response(200, json={"id": 550, "poster_path": "/poster.jpg"})

    with TmdbClient(
        "secret-token",
        "https://api.themoviedb.org/3",
        transport=httpx.MockTransport(handler),
    ) as client:
        client.validate_image_base("https://image.tmdb.org/t/p/w500")
        assert client.poster_path(550) == "/poster.jpg"

    assert all(request.headers["Authorization"] == "Bearer secret-token" for request in requests)


def test_client_supports_v3_api_key_authentication() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": 550, "poster_path": "/poster.jpg"})

    with TmdbClient(
        "",
        "https://api.themoviedb.org/3",
        api_key="v3-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.poster_path(550) == "/poster.jpg"

    assert requests[0].url.params["api_key"] == "v3-key"
    assert "Authorization" not in requests[0].headers


def test_client_retries_rate_limit_without_exposing_response_body() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0.1"}, text="sensitive")
        return httpx.Response(200, json={"id": 10, "poster_path": None})

    with TmdbClient(
        "token",
        "https://api.themoviedb.org/3",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    ) as client:
        assert client.poster_path(10) is None

    assert calls == 2
    assert sleeps == [0.1, 1]


def test_client_rejects_malformed_json() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    with TmdbClient(
        "token",
        "https://api.themoviedb.org/3",
        transport=httpx.MockTransport(handler),
    ) as client, pytest.raises(TmdbMetadataError, match="invalid JSON"):
        client.poster_path(10)


def test_movie_response_exposes_only_a_valid_tmdb_poster_url() -> None:
    movie = Movie(
        id=1,
        movielens_id=1,
        title="Example",
        release_year=2000,
        genres=["Drama"],
        imdb_id="0114709",
        tmdb_id=550,
        poster_path="/poster.jpg",
        poster_source="TMDB",
        overview="An example story.",
        overview_source="TMDB",
        tmdb_rating=7.2,
        tmdb_vote_count=50,
        imdb_rating=8.1,
        imdb_vote_count=100,
        active=True,
        source="MovieLens",
    )

    response = movie_response(movie)
    assert response.poster_url == "https://image.tmdb.org/t/p/w500/poster.jpg"
    assert response.poster_source == "TMDB"
    assert response.summary == "An example story."
    assert [rating.source for rating in response.ratings] == ["IMDb", "TMDB"]
    assert response.ratings[0].url == "https://www.imdb.com/title/tt0114709/"

    movie.poster_path = "https://attacker.invalid/poster.jpg"
    assert movie_response(movie).poster_url is None
