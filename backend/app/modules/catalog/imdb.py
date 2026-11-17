"""Parsing helpers for IMDb's official non-commercial title ratings dataset."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class ImdbRating:
    imdb_id: str
    rating: float
    vote_count: int


def ratings(rows: Iterable[str], wanted_ids: set[str]) -> Iterator[ImdbRating]:
    reader = csv.DictReader(rows, delimiter="\t")
    if reader.fieldnames != ["tconst", "averageRating", "numVotes"]:
        raise ValueError("IMDb ratings dataset has an unexpected header")
    seen: set[str] = set()
    for row in reader:
        tconst = row["tconst"]
        if not tconst.startswith("tt") or not tconst[2:].isdigit():
            raise ValueError("IMDb ratings dataset contains an invalid title ID")
        imdb_id = tconst[2:]
        if imdb_id not in wanted_ids:
            continue
        if imdb_id in seen:
            raise ValueError("IMDb ratings dataset contains a duplicate title ID")
        try:
            rating = float(row["averageRating"])
            vote_count = int(row["numVotes"])
        except (TypeError, ValueError) as error:
            raise ValueError("IMDb ratings dataset contains an invalid rating") from error
        if not 0 <= rating <= 10 or vote_count < 0:
            raise ValueError("IMDb ratings dataset contains an invalid rating")
        seen.add(imdb_id)
        yield ImdbRating(imdb_id, rating, vote_count)
