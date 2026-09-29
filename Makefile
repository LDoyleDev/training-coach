# Common tasks. Run `make help` for the list. CI runs the same targets.
.DEFAULT_GOAL := help
BACKEND := backend
FRONTEND := frontend

.PHONY: help setup lint format typecheck test migrations-check check ci build dev-api dev-web migrate migration seed audit up down logs

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install all dependencies and git hooks
	cd $(BACKEND) && uv sync --frozen
	cd $(FRONTEND) && npm ci
	cd $(BACKEND) && uv run pre-commit install --install-hooks -t pre-commit -t commit-msg --config ../.pre-commit-config.yaml

lint: ## Lint backend and frontend
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(FRONTEND) && npm run lint && npm run format:check

format: ## Auto-format everything
	cd $(BACKEND) && uv run ruff check --fix . && uv run ruff format .
	cd $(FRONTEND) && npm run format

typecheck: ## Type-check backend (mypy strict) and frontend (tsc)
	cd $(BACKEND) && uv run mypy
	cd $(FRONTEND) && npm run typecheck

test: ## Run all tests
	cd $(BACKEND) && uv run pytest
	cd $(FRONTEND) && npm test

migrations-check: ## Migrations apply cleanly and match the models (alembic check)
	cd $(BACKEND) && rm -f .check.db && export TC_DATABASE_URL=sqlite:///./.check.db \
		&& uv run alembic upgrade head && uv run alembic check; status=$$?; rm -f .check.db; exit $$status

check: lint typecheck test migrations-check build ## Everything CI runs offline; must pass before every PR

ci: check audit ## check + dependency audit (needs network); the full CI job set minus Docker

audit: ## Dependency vulnerability scan
	cd $(BACKEND) && uv export --frozen --no-hashes --no-emit-project -o requirements-audit.txt \
		&& uv run pip-audit -r requirements-audit.txt --strict; status=$$?; rm -f requirements-audit.txt; exit $$status
	cd $(FRONTEND) && npm audit --audit-level=high

build: ## Build the dashboard
	cd $(FRONTEND) && npm run build

dev-api: ## Run the API (and bot, if configured) with reload
	cd $(BACKEND) && uv run uvicorn training_coach.api.app:create_app --factory --reload --port 8080

dev-web: ## Run the dashboard dev server (proxies API to :8080)
	cd $(FRONTEND) && npm run dev

migrate: ## Apply database migrations
	cd $(BACKEND) && uv run alembic upgrade head

seed: ## Load or update the training plan from seed/plan.toml (idempotent)
	cd $(BACKEND) && uv run training-coach seed

migration: ## Create a migration: make migration m="add sessions table"
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

up: ## Build and start the stack (on the Pi)
	docker compose up -d --build

down: ## Stop the stack
	docker compose down

logs: ## Follow app logs
	docker compose logs -f app
