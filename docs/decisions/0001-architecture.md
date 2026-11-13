# ADR 0001: Local portfolio architecture

Status: accepted, 2026-11-13.

Use one FastAPI modular monolith and PostgreSQL because the catalog, accounts, and interaction writes share transactional boundaries. Redis serves disposable cache and Celery work; a PostgreSQL outbox will bridge committed interactions to jobs. Use MovieLens small for a no-credential non-commercial demo; source users remain separate from app users. Train offline so serving never depends on training latency. These decisions follow `spec.md`; production claims require measured evidence.
