# Deployment

`docker-compose.yml` is the local stack. `docker-compose.prod.yml` adds a non-root static Node frontend image, Caddy TLS, secure cookies, and resource limits. Set a real `SESSION_SECRET`, database password, and `APP_DOMAIN` in the deployment environment. Do not expose PostgreSQL, Redis, Prometheus, or Grafana publicly.

The intended release flow builds immutable API and web images after CI, pushes them to GHCR, backs up the target database, applies migrations, starts the new stack, checks readiness, and restores the previous image/model pointer if application checks fail. The repository includes workflow scaffolding; no VPS credentials are configured and no public deployment has occurred.

Database rollback is not automatically safe after destructive migrations. Each migration needs a compatibility review before deployment. The current deployment is a single VPS design and has no high availability.
