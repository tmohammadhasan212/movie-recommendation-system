# Academic project brief

## Project

**RecSys: a reproducible, production-oriented movie recommendation system**

Author: Mohammad Hasan Talebi

## Abstract

RecSys is a full-stack study of recommendation quality and the engineering required to serve recommendations safely. It compares popularity, genre-content, matrix-factorization, and hybrid ranking strategies on MovieLens `ml-latest-small`. The system also handles cold starts, deterministic degradation when model artifacts are unavailable, secure user interactions, versioned model publication, caching, observability, and data provenance. The observed hybrid result has the best Recall@10 and NDCG@10 in the recorded local experiment, although the margin is small and no statistical-significance or online-uplift claim is made.

## Research questions

1. Does a blend of collaborative, genre, and popularity signals improve top-10 ranking quality over its individual baselines?
2. Can the same application serve useful results to anonymous and new users who have no collaborative history?
3. Can model training, validation, publication, fallback behavior, and application operations be made reproducible and auditable in one portfolio project?

## Main contributions

- A chronological evaluation split that avoids training on a user's held-out future positives.
- Full-catalog evaluation of four ranking strategies using Recall@10, NDCG@10, and catalog coverage@10.
- A hybrid serving path that constructs an application-user profile from positive item embeddings without treating application accounts as MovieLens users.
- Explicit cold-start and failure fallbacks based on popularity, genres, and user preferences.
- Immutable `safetensors` artifacts, checksum verification, transactional publication, and a serving smoke test.
- A complete web application with secure sessions, watchlists, ratings, search, metadata enrichment, transactional outbox processing, caching, metrics, tests, and containerized deployment.
- Documented dataset rights, privacy boundaries, security assumptions, architectural decisions, and operational limitations.

## Methodology

The offline model learns 48-dimensional user and item embeddings with PyTorch matrix factorization. Ratings of at least 4 are positive, ratings of at most 2.5 are explicit negatives, and neutral ratings are excluded from preference loss. For each of 592 eligible source users, the latest positive is held out for testing and the preceding positive for validation; at least five earlier positives remain for training. Sampled negatives use a fixed seed, and known or held-out interactions are excluded from the negative pool.

Each held-out positive is ranked against the full eligible catalog after masking prior interactions. The hybrid score combines normalized collaborative, genre-content, and smoothed-popularity signals with weights of 0.60, 0.25, and 0.15 respectively. These weights are development choices rather than the result of an exhaustive hyperparameter search.

## Recorded results

Artifact `mf-20261114T082603Z` was trained locally on CPU using the verified MovieLens source recorded in [the model report](model.md).

| Strategy | Recall@10 | NDCG@10 | Coverage@10 |
|---|---:|---:|---:|
| Popularity | 0.0456 | 0.0213 | 0.0055 |
| Genre content | 0.0152 | 0.0083 | 0.0266 |
| Collaborative | 0.0473 | 0.0227 | 0.0996 |
| **Hybrid** | **0.0490** | **0.0248** | **0.0779** |

The hybrid has the strongest observed ranking metrics. Pure collaborative ranking reaches higher catalog coverage, while popularity has very low coverage. The results support further experimentation but do not establish statistical significance, causal improvement, or generalization to another dataset.

## Reproducibility

The application pins Python and JavaScript dependencies and provides deterministic data, training, publication, and verification commands:

```bash
make bootstrap
make up
make data-download
make data-import
make train
make model-publish
make test
make smoke
```

The source archive is checksum-verified, imports are idempotent, training records its random seed and source checksum, and published model files are verified before activation. Raw data and model binaries are intentionally excluded from Git because they have separate terms or can be regenerated. Exact environment and operating instructions are in the main [README](../README.md), [data report](data.md), and [model report](model.md).

## Limitations and threats to validity

- The dataset is small, historical, and subject to selection and popularity biases.
- MovieLens `latest` can change, so this is not a fixed public benchmark result.
- The evaluation contains one local training run and no confidence intervals or significance tests.
- Recall@10 is low in absolute terms and should be interpreted alongside the full-catalog evaluation protocol.
- The hybrid weights were selected manually; there is no systematic ablation or hyperparameter study yet.
- Offline ranking metrics do not measure satisfaction, diversity, novelty, fairness, retention, or causal online impact.
- TMDB and IMDb enrichment affects presentation but is not used as ground truth for recommendation quality.
- The Compose deployment has a single-host failure domain and is a portfolio deployment design, not a highly available production service.

## Suggested CV entry

**Movie Recommendation System — independent academic portfolio project**

Designed and implemented a reproducible full-stack recommender using PyTorch, FastAPI, React, PostgreSQL, Redis, and Celery. Compared popularity, genre-content, collaborative, and hybrid models on MovieLens using chronological full-catalog evaluation; the hybrid achieved the best observed Recall@10 (`0.0490`) and NDCG@10 (`0.0248`) across 592 eligible users. Added deterministic cold-start fallbacks, checksum-verified model publication, secure user accounts, watchlists, ratings, search, metadata enrichment, observability, CI, and containerized deployment.

## Suggested repository description

Reproducible hybrid movie recommender with full-catalog evaluation, secure FastAPI/React application, PostgreSQL/Redis/Celery infrastructure, and checksum-verified PyTorch model publication.

## Presentation checklist

- Link the public repository from the CV.
- Keep the CI badge green and create a tagged release for the version cited in applications.
- Add two or three current interface screenshots or a short demo recording when the application is running with enriched metadata.
- Do not commit `.env` files, API keys, raw datasets, database exports, user data, or generated model artifacts.
- If a public demo is added, label free-tier sleep/wake behavior and keep the source-code link as the permanent artifact.

## Data citation

Harper, F. M., & Konstan, J. A. (2015). The MovieLens Datasets: History and Context. *ACM Transactions on Interactive Intelligent Systems*, 5(4), 19:1–19:19. https://doi.org/10.1145/2827872
