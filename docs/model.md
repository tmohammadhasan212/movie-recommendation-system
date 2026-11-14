# Recommendation model

The serving path always has a deterministic popularity and genre fallback. Historical MovieLens rating counts are treated as a catalog popularity proxy. For an app account, selected genres and positively rated movies shape fallback ranking; rated and watchlisted items are suppressed by default.

The offline model uses 48-dimensional PyTorch matrix factorization on MovieLens source users. Ratings at least 4 are positives, ratings at most 2.5 are explicit negatives, and 3/3.5 are omitted from preference loss. Each eligible source user's latest positive is held out for test, the preceding positive for validation, and at least five earlier positives remain for training. Unobserved negatives are sampled with seed `20261113`; held-out positives and all known user interactions are excluded from that pool. App account IDs never enter training.

For an app user, serving builds a vector from the item embeddings of positive ratings and uses negative ratings for suppression. This works without assigning the app user a MovieLens source ID. Scores blend collaborative, genre, and smoothed-popularity signals. New or unmapped movies remain eligible through the fallback path.

## Observed local training result

Artifact `mf-20261114T082603Z` was trained on 2026-11-14 with Python 3.12.0 and PyTorch 2.15.0 on CPU. The verified source SHA-256 was `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436`. Training used 113,557 examples, 592 eligible users, eight epochs, and took 0.820 seconds. Metrics rank each held-out positive against the full eligible catalog and mask training/validation items.

| Strategy | Recall@10 | NDCG@10 | Coverage@10 |
|---|---:|---:|---:|
| Popularity | 0.0456 | 0.0213 | 0.0055 |
| Genre content | 0.0152 | 0.0083 | 0.0266 |
| Collaborative | 0.0473 | 0.0227 | 0.0996 |
| Hybrid | 0.0490 | 0.0248 | 0.0779 |

These are development measurements on the changing MovieLens “latest small” dataset, not live uplift or a stable research benchmark. The hybrid improvement is small. Publication requires a valid artifact, nonzero output, checksum verification, and a serving smoke test; it does not claim statistical significance.

Artifacts use safetensors plus JSON, contain no email or app user ID, and are immutable under `models/versions/<version>/`. Publication verifies every checksum and switches the single active registry row transactionally. Missing or corrupt artifacts trigger the deterministic fallback with an explicit reason.
