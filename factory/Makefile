.PHONY: test

## Tests for the factory's own code (hooks). Needs only uv; no project environment.
test:
	uvx ruff check hooks worker tests
	uv run --no-project --with pytest pytest -q tests
