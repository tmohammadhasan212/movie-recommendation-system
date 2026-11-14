.PHONY: help bootstrap up down migrate data-download data-import train model-publish test test-e2e lint load-test monitoring-up build smoke

export UV_CACHE_DIR ?= $(CURDIR)/.uv-cache

help:
	@echo 'bootstrap up down migrate data-download data-import train model-publish test test-e2e lint load-test monitoring-up build smoke'

bootstrap:
	@test -f .env || cp .env.example .env
	uv sync --locked
	cd frontend && npm ci

up:
	docker-compose up -d --build

down:
	docker-compose down

migrate:
	docker-compose run --rm api alembic upgrade head

data-download:
	docker-compose run --rm api python -m backend.cli.download_data

data-import:
	docker-compose run --rm api python -m backend.cli.import_data

train:
	uv run --group ml python -m backend.cli.train_model

model-publish:
	docker-compose run --rm api python -m backend.cli.publish_model

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
	docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

build:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

smoke:
	curl --fail --silent http://localhost:8000/health/live
	curl --fail --silent http://localhost:8000/health/ready
	docker-compose exec -T redis redis-cli ping
	docker-compose exec -T db psql -U recsys -d recsys -Atc "select count(*) from model_versions where active"
