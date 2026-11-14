# Operations runbook

Check `docker-compose ps -a`, then `/health/ready`. Inspect API, worker, and scheduler logs with `docker-compose logs --tail=200 api worker scheduler`. Prometheus is at `localhost:9090` and Grafana at `localhost:3000` after `make monitoring-up`.

The operations dashboard breaks rate-limit decisions down by the fixed `scope` and `outcome` labels. Any `unavailable` outcome means a protected request failed closed because Redis could not provide trustworthy limiter state; the `RecSysRateLimiterUnavailable` alert fires immediately. Check API and Redis health before retrying the action. Rejected requests return `Retry-After` with the remaining fixed-window duration.

For stuck events, inspect `outbox_events` by status and `next_attempt_at`. List dead letters without exposing their payloads with `make outbox-replay ARGS="--list"`. After fixing the cause, dry-run exact event IDs first:

```bash
make outbox-replay ARGS="--event-id <uuid>"
make outbox-replay ARGS="--event-id <uuid> --apply --reason 'broker incident resolved'"
```

The command locks and validates the entire batch, refuses missing, non-dead-letter, duplicate, or already-processed events, and caps a replay at 100 IDs. Applying resets delivery attempts and schedules immediate dispatch in one transaction. The prior attempt count, error code, reason, and timestamp remain in `outbox_replays`. Never replay an event until its failure cause and consumer idempotency have been reviewed.

Model rollback is an atomic database update: mark the current row inactive and the prior validated version active in one transaction, then restart API replicas or wait for a version reload. Keep at least two immutable artifact directories. A missing/corrupt active artifact safely falls back but should alert.

Backup PostgreSQL with `docker-compose exec -T db pg_dump -U recsys -Fc recsys > recsys.dump`. Restore only into an empty, isolated database first using `pg_restore --no-owner`; run count, migration, readiness, and smoke checks before switching traffic. On 2026-11-14 an isolated restore rehearsal matched source and restored state at 9,742 movies, 100,836 imported ratings, one model version, and Alembic revision `0003`; its temporary database and dump were removed afterward. Database migration downgrades may lose data; prefer forward fixes and restore only with a reviewed backup.

The scheduler purges consented `interaction_events` older than 30 days. Operators must still expire backups according to the deployment policy.
