import hashlib
import zipfile
from pathlib import Path

import pytest

from backend.cli.download_data import verify_archive
from backend.ml.data import links, movies, ratings


def test_parses_titles_and_ratings(tmp_path: Path) -> None:
    movie_file = tmp_path / "movies.csv"
    movie_file.write_text('movieId,title,genres\n1,"A, Film (1999)",Drama|Comedy\n2,Untitled,(no genres listed)\n')
    parsed = list(movies(movie_file))
    assert parsed[0].title == "A, Film"
    assert parsed[0].year == 1999
    assert parsed[0].genres == ("Comedy", "Drama")
    assert parsed[1].year is None
    rating_file = tmp_path / "ratings.csv"
    rating_file.write_text("userId,movieId,rating,timestamp\n5,1,4.5,1530000000\n")
    assert next(ratings(rating_file, {1, 2})).rating == 4.5


@pytest.mark.parametrize(
    "contents",
    [
        "movieId,title,wrong\n1,Film,Drama\n",
        "movieId,title,genres\n1,Film,Drama\n1,Again,Drama\n",
        "movieId,title,genres\n0,Film,Drama\n",
    ],
)
def test_rejects_bad_movies(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "movies.csv"
    path.write_text(contents)
    with pytest.raises(ValueError):
        list(movies(path))


def test_rejects_unknown_and_invalid_rating(tmp_path: Path) -> None:
    path = tmp_path / "ratings.csv"
    path.write_text("userId,movieId,rating,timestamp\n5,2,4.5,1530000000\n")
    with pytest.raises(ValueError, match="unknown movie"):
        list(ratings(path, {1}))
    path.write_text("userId,movieId,rating,timestamp\n5,1,4.3,1530000000\n")
    with pytest.raises(ValueError, match="invalid rating"):
        list(ratings(path, {1}))


def test_links_allow_missing_rows_but_reject_duplicate_external_ids(tmp_path: Path) -> None:
    path = tmp_path / "links.csv"
    path.write_text("movieId,imdbId,tmdbId\n1,0111111,10\n")
    assert next(links(path, {1, 2})).movie_id == 1
    path.write_text("movieId,imdbId,tmdbId\n1,0111111,10\n2,0111111,11\n")
    with pytest.raises(ValueError, match="duplicate or invalid external ID"):
        list(links(path, {1, 2}))


def test_archive_verification_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "test.zip"
    with zipfile.ZipFile(archive, "w") as target:
        for name in ("movies.csv", "links.csv", "ratings.csv"):
            target.writestr(f"ml-latest-small/{name}", "header\n")
        target.writestr("../escape", "bad")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Unexpected ZIP path"):
        verify_archive(archive, digest)


def test_archive_verification_requires_checksum(tmp_path: Path) -> None:
    archive = tmp_path / "test.zip"
    archive.write_bytes(b"not a zip")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_archive(archive, "0" * 64)


def test_archive_accepts_published_md5_and_records_sha256(tmp_path: Path) -> None:
    archive = tmp_path / "test.zip"
    with zipfile.ZipFile(archive, "w") as target:
        for name in ("movies.csv", "links.csv", "ratings.csv"):
            target.writestr(f"ml-latest-small/{name}", "header\n")
    md5 = hashlib.md5(archive.read_bytes()).hexdigest()  # Test of upstream format.
    result = verify_archive(archive, published_md5=md5)
    assert result["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
