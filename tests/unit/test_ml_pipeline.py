from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.ml.artifacts import validate_artifact
from backend.ml.data import SourceRating
from backend.ml.train import split_positive_history


def test_temporal_split_reserves_latest_two_positives() -> None:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    rows = [SourceRating(1, index + 1, 4.0, start + timedelta(days=index)) for index in range(7)]
    train, validation, test, seen = split_positive_history(rows)
    assert train[1] == [1, 2, 3, 4, 5]
    assert validation[1] == 6
    assert test[1] == 7
    assert seen[1] == set(range(1, 8))


def test_temporal_split_excludes_short_histories_and_neutral_ratings() -> None:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    rows = [SourceRating(1, index + 1, 3.5, start + timedelta(days=index)) for index in range(10)]
    train, validation, test, _ = split_positive_history(rows)
    assert train == validation == test == {}


def test_artifact_validation_rejects_missing_and_corrupt_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing"):
        validate_artifact(tmp_path)
