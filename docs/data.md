# Data source and import

RecSys is a non-commercial portfolio demo. The default source is [MovieLens ml-latest-small](https://grouplens.org/datasets/movielens/latest/) from GroupLens Research at the University of Minnesota. The source terms and citation are in the [MovieLens README](https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html). GroupLens does not endorse this project. Commercial or revenue-bearing use needs separate permission or another source.

The source has `movies.csv`, `links.csv`, `ratings.csv`, and `tags.csv`. The app imports the first three. Tags are omitted because no serving feature needs untrusted free text. Imported source user IDs are never app account IDs and are not exposed by the API. MovieLens supplies titles, genres, years, and optional external identifiers; it does not grant rights to poster images, descriptions, cast, or current popularity.

`make data-download` fetches the archive over HTTPS and verifies the [MD5 published by GroupLens](https://files.grouplens.org/datasets/movielens/ml-latest-small.zip.md5). GroupLens does not publish a SHA-256 for this artifact. The command computes a local SHA-256 for provenance and optionally verifies an operator-supplied `DATA_EXPECTED_SHA256`. It rejects unexpected ZIP paths, duplicate entries, and oversized archives. The manifest and raw files stay under ignored `data/`.

`make data-import` checks local file hashes, validates headers and rows, upserts catalog and source ratings in one transaction, and records counts. Rerunning does not duplicate records. The actual downloaded checksum, date, and counts belong in the local manifest and implementation log after an import has run. Historical MovieLens rating count is only a catalog popularity proxy. The "latest" dataset can change and is not a stable research benchmark.

The current archive has one duplicate TMDB ID affecting two rows. The import omits those optional IDs and records `ambiguous_tmdb_rows`; see [ADR 0002](decisions/0002-ambiguous-tmdb-links.md). Strict link parsing still rejects duplicate IDs by default.

## Optional TMDB posters

Poster enrichment is disabled unless an operator supplies `TMDB_API_TOKEN` or `TMDB_API_KEY` and explicitly runs `make metadata-enrich`. The command selects at most 250 stale movies per run, validates TMDB's current secure image configuration, retrieves poster paths using the MovieLens-provided TMDB IDs, retries bounded transient failures, and records the source and refresh time. It stores only paths and timestamps in PostgreSQL; poster image files are served remotely from TMDB and are not downloaded into the repository or model artifacts. Missing, invalid, removed, or failed images retain the local typographic placeholder.

TMDB permits its developer API for non-commercial use with attribution and requires its approved logo plus the notice shown on the in-app Credits page. Public or commercial operators must review the current [TMDB FAQ and attribution requirements](https://developer.themoviedb.org/docs/faq), [approved logo page](https://www.themoviedb.org/about/logos-attribution), and applicable API terms before enabling enrichment. This product uses the TMDB API but is not endorsed or certified by TMDB.

Citation: Harper, F. M., & Konstan, J. A. (2015). The MovieLens Datasets: History and Context. *ACM Transactions on Interactive Intelligent Systems*, 5(4), 19:1–19:19.
