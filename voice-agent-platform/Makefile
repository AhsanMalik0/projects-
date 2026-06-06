.PHONY: build up down migrate test logs lint format

build:
	docker compose -f docker/docker-compose.yml build

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

migrate:
	alembic upgrade head

test:
	pytest tests/unit/ -v --cov=app --cov-report=term-missing

test-all:
	pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	ruff check app/ workers/ tests/
	ruff format --check app/ workers/ tests/

format:
	ruff check --fix app/ workers/ tests/
	ruff format app/ workers/ tests/

logs:
	docker compose -f docker/docker-compose.yml logs -f
