PYTHON ?= python3
BACKEND_PYTHON := backend/.venv/bin/python
COMPOSE ?= docker compose

.PHONY: setup test lint check up down logs migrate up-host down-host logs-host migrate-host

setup: init
	$(PYTHON) -m venv backend/.venv
	$(BACKEND_PYTHON) -m pip install --require-hashes -r backend/requirements-dev.lock
	$(BACKEND_PYTHON) -m pip install --no-deps -e backend

test:
	cd backend && .venv/bin/python -m pytest

lint:
	cd backend && .venv/bin/python -m ruff check .
	cd backend && .venv/bin/python -m ruff format --check .

check: lint test

up: init
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs --tail=100 -f api worker migrate

migrate:
	$(COMPOSE) run --rm migrate

up-host: init
	mkdir -p .local/postgres
	$(COMPOSE) -f compose.yaml -f compose.host-storage.yaml up --build -d

down-host:
	$(COMPOSE) -f compose.yaml -f compose.host-storage.yaml down

logs-host:
	$(COMPOSE) -f compose.yaml -f compose.host-storage.yaml logs --tail=100 -f api worker migrate

migrate-host:
	$(COMPOSE) -f compose.yaml -f compose.host-storage.yaml run --rm migrate

init:
	$(PYTHON) scripts/init_env.py

seed:
	$(COMPOSE) exec -T api python -m mts_backend.auth.seed

seed-host:
	$(COMPOSE) -f compose.yaml -f compose.host-storage.yaml exec -T api python -m mts_backend.auth.seed
