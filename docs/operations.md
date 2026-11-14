# Operations runbook

Check `docker-compose ps -a`, then `/health/ready`. Inspect API, worker, and scheduler logs with `docker-compose logs --tail=200 api worker scheduler`. Prometheus is at `localhost:9090` and Grafana at `localhost:3000` after `make monitoring-up`.

For stuck events, query `outbox_events` by status and `next_attempt_at`. A dead-letter replay tool is not implemented yet; after fixing the cause, an operator may transactionally set a reviewed row back to `pending`, clear `error_code`, and set `next_attempt_at=now()`. Never bulk replay without checking consumer idempotency.

Model rollback is an atomic database update: mark the current row inactive and the prior validated version active in one transaction, then restart API replicas or wait for a version reload. Keep at least two immutable artifact directories. A missing/corrupt active artifact safely falls back but should alert.

Backup PostgreSQL with `docker-compose exec -T db pg_dump -U recsys -Fc recsys > recsys.dump`. Restore only into an empty, isolated database first using `pg_restore --no-owner`; run count, migration, readiness, and smoke checks before switching traffic. On 2026-11-14 an isolated restore rehearsal matched source and restored state at 9,742 movies, 100,836 imported ratings, one model version, and Alembic revision `0003`; its temporary database and dump were removed afterward. Database migration downgrades may lose data; prefer forward fixes and restore only with a reviewed backup.

The scheduler purges consented `interaction_events` older than 30 days. Operators must still expire backups according to the deployment policy.
