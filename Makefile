.PHONY: help bootstrap up down migrate data-download data-import train model-publish test test-e2e lint load-test monitoring-up build smoke

help:
	@echo 'bootstrap up down migrate data-download data-import train model-publish test test-e2e lint load-test monitoring-up build smoke'

bootstrap:
	@test -f .env || cp .env.example .env
	uv sync --locked
	cd frontend && npm ci

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	docker compose run --rm api uv run alembic upgrade head

data-download:
	uv run python -m backend.cli.download_data

data-import:
	uv run python -m backend.cli.import_data

train:
	uv run python -m backend.cli.train_model

model-publish:
	uv run python -m backend.cli.publish_model

test:
	uv run pytest
	cd frontend && npm test -- --run

test-e2e:
	cd frontend && npm run test:e2e

lint:
	uv run ruff check backend tests
	cd frontend && npm run lint

load-test:
	uv run python tests/performance/load.py

monitoring-up:
	docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

build:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

smoke:
	curl --fail http://localhost:8000/health/live
