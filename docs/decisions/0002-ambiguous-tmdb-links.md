# ADR 0002: Ambiguous optional TMDB IDs

Status: accepted, 2026-11-13.

The verified `ml-latest-small` archive currently assigns TMDB ID `4912` to two different MovieLens movie IDs (lines 4171 and 9108 of `links.csv`, including the header). The strict parser rejects duplicate external IDs by default, as the specification requests. For the default import, omit all affected TMDB IDs and record the number of affected rows in the local manifest and `data_imports.counts`. Keep both MovieLens movies and their ratings. This avoids attaching an ambiguous third-party identity. The importer still rejects duplicate MovieLens IDs and duplicate IMDb IDs.
