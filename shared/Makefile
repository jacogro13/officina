.PHONY: install test test-backend test-frontend lint typecheck drift

install:
	uv sync
	cd frontend && npm ci --no-audit --no-fund

## Full gate for a change to any canonical file
test: test-backend test-frontend

test-backend: lint typecheck
	uv run pytest

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run pyright

test-frontend:
	cd frontend && npm run typecheck && npm test

## Which apps carry which canonical files, and in what state (fails on unlabelled edits)
drift:
	uv run python tools/check_drift.py $(APP)
