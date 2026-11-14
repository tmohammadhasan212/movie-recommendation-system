# Privacy

Imported MovieLens source users are anonymized dataset identifiers stored only in `imported_ratings`; they are never joined to accounts or returned by the API. Offline training uses only those imported ratings. App accounts collect normalized email, an Argon2id password hash, sessions, genre choices, ratings, watchlist items, and explicitly consented allowlisted events. Raw passwords, tokens, emails, IP addresses, search text, and event payloads are excluded from logs, metrics, jobs, and model files.

Access and rotating refresh tokens are cookies, not browser storage. Refresh identifiers and CSRF tokens are hashed at rest. Account export returns the user's profile, ratings, watchlist, and events. Deletion requires recent authentication, revokes sessions, removes preferences and interactions, pseudonymizes retained event records, and removes account outbox data. Because app interactions are not training data, deletion does not require model retraining.

Raw app events are purged by a daily 30-day retention task. Backup expiry remains an operator responsibility under `docs/operations.md`. Redis entries are disposable. This design has not received legal review and makes no GDPR compliance claim.
