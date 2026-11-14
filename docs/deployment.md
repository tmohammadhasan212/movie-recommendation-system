# Deployment

`docker-compose.yml` is the local stack. `docker-compose.prod.yml` adds a non-root static Node frontend image, Caddy TLS, secure cookies, resource limits, and mandatory production settings. Do not expose PostgreSQL, Redis, Prometheus, or Grafana publicly.

Create a root-owned production environment file before the first deployment:

```bash
cp .env.production.example .env
chmod 600 .env
```

Replace every placeholder in that file. `SESSION_SECRET` must be unique and contain at least 32 characters; `openssl rand -hex 32` is a suitable generator. `POSTGRES_PASSWORD` must match the password encoded in `DATABASE_URL`; percent-encode URL-sensitive password characters in the URL. The deployment script loads this file, validates the merged Compose configuration, and stops before pulling images when a required value is absent. After pulling and verifying the release images, it runs the application's production validator before creating a backup or applying migrations. Insecure cookies and development or placeholder secrets therefore fail before the database is changed.

The release workflow runs only after a successful push CI run on the repository's default branch. It checks out that run's exact commit, labels both images with the full Git SHA, and publishes both images under that SHA. Deployment accepts only a full lowercase commit SHA, pulls both images, verifies their embedded revisions, and uses the same API image for migrations, the API, the worker, and the scheduler. It backs up PostgreSQL before applying migrations, starts the stack, and checks readiness.

Select a SHA from a successful Release images workflow and dispatch the manual deployment with that exact value. The deployment workflow accepts only a full SHA from the default branch's history, checks out that revision locally, then checks out the same detached revision on the host before running its deployment script. Treat the SHA as the release identity for the API image, web image, Compose definition, migrations, and deployment record.

The repository includes workflow scaffolding; no VPS credentials are configured and no public deployment has occurred. An application-image rollback still requires selecting the prior verified SHA and dispatching it again. A database rollback is a separate reviewed operation because a migration may not be reversible.

Database rollback is not automatically safe after destructive migrations. Each migration needs a compatibility review before deployment. The current deployment is a single VPS design and has no high availability.
