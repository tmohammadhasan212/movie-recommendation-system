# Data source and import

RecSys is a non-commercial portfolio demo. The default source is [MovieLens ml-latest-small](https://grouplens.org/datasets/movielens/latest/) from GroupLens Research at the University of Minnesota. The source terms and citation are in the [MovieLens README](https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html). GroupLens does not endorse this project. Commercial or revenue-bearing use needs separate permission or another source.

The source has `movies.csv`, `links.csv`, `ratings.csv`, and `tags.csv`. The app imports the first three. Tags are omitted because no serving feature needs untrusted free text. Imported source user IDs are never app account IDs and are not exposed by the API. The catalog shows titles, genres, and years; posters, descriptions, cast, and current popularity are unavailable from this source.

`make data-download` fetches the archive over HTTPS and verifies the [MD5 published by GroupLens](https://files.grouplens.org/datasets/movielens/ml-latest-small.zip.md5). GroupLens does not publish a SHA-256 for this artifact. The command computes a local SHA-256 for provenance and optionally verifies an operator-supplied `DATA_EXPECTED_SHA256`. It rejects unexpected ZIP paths, duplicate entries, and oversized archives. The manifest and raw files stay under ignored `data/`.

`make data-import` checks local file hashes, validates headers and rows, upserts catalog and source ratings in one transaction, and records counts. Rerunning does not duplicate records. The actual downloaded checksum, date, and counts belong in the local manifest and implementation log after an import has run. Historical MovieLens rating count is only a catalog popularity proxy. The "latest" dataset can change and is not a stable research benchmark.

Citation: Harper, F. M., & Konstan, J. A. (2015). The MovieLens Datasets: History and Context. *ACM Transactions on Interactive Intelligent Systems*, 5(4), 19:1–19:19.
