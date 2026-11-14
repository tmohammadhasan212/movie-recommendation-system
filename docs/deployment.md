# Deployment

`docker-compose.yml` is the local stack. `docker-compose.prod.yml` adds a non-root static Node frontend image, Caddy TLS, secure cookies, and resource limits. Set a real `SESSION_SECRET`, database password, and `APP_DOMAIN` in the deployment environment. Do not expose PostgreSQL, Redis, Prometheus, or Grafana publicly.

The release workflow runs only after a successful push CI run on the repository's default branch. It checks out that run's exact commit, labels both images with the full Git SHA, and publishes both images under that SHA. Deployment accepts only a full lowercase commit SHA, pulls both images, verifies their embedded revisions, and uses the same API image for migrations, the API, the worker, and the scheduler. It backs up PostgreSQL before applying migrations, starts the stack, and checks readiness.

Configure `GHCR_OWNER` and `APP_DOMAIN` on the target host. Select a SHA from a successful Release images workflow and dispatch the manual deployment with that exact value. The deployment workflow accepts only a full SHA from the default branch's history, checks out that revision locally, then checks out the same detached revision on the host before running its deployment script. Treat the SHA as the release identity for the API image, web image, Compose definition, migrations, and deployment record.

The repository includes workflow scaffolding; no VPS credentials are configured and no public deployment has occurred. An application-image rollback still requires selecting the prior verified SHA and dispatching it again. A database rollback is a separate reviewed operation because a migration may not be reversible.

Database rollback is not automatically safe after destructive migrations. Each migration needs a compatibility review before deployment. The current deployment is a single VPS design and has no high availability.
