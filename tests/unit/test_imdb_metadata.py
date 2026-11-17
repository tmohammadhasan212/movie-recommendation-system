import pytest

from backend.app.modules.catalog.imdb import ratings


def test_ratings_selects_wanted_ids_and_validates_values() -> None:
    rows = [
        "tconst\taverageRating\tnumVotes\n",
        "tt0000001\t5.7\t2118\n",
        "tt0114709\t8.3\t123456\n",
    ]
    result = list(ratings(rows, {"0114709"}))
    assert len(result) == 1
    assert result[0].imdb_id == "0114709"
    assert result[0].rating == 8.3
    assert result[0].vote_count == 123456


def test_ratings_rejects_an_unexpected_header_or_invalid_match() -> None:
    with pytest.raises(ValueError, match="unexpected header"):
        list(ratings(["wrong\theader\n"], {"1"}))

    rows = ["tconst\taverageRating\tnumVotes\n", "tt0114709\t12.0\t1\n"]
    with pytest.raises(ValueError, match="invalid rating"):
        list(ratings(rows, {"0114709"}))
