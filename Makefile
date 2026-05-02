.PHONY: setup setup-server setup-dev sync format typecheck test clean client-local server-dev

# Setup virtual environment and install base dependencies
setup:
	uv venv
	uv sync

# Setup with server dependencies
setup-server:
	uv venv
	uv sync --extra server

# Setup with dev dependencies
setup-dev:
	uv venv
	uv sync --extra server --group dev

# Sync dependencies (after changing pyproject.toml)
sync:
	uv sync

# Format code
format:
	npx dprint fmt .

# Type check
typecheck:
	uv run mypy src

# Run tests
test:
	uv run pytest

# Run client connecting to localhost (for local dev)
client-local:
	OTEL_SERVICE_NAME=xumret-client uv run xumret client --host localhost --port 8765

# Run server in dev mode (listens on all interfaces)
server-dev:
	OTEL_SERVICE_NAME=xumret-server uv run xumret server --host 0.0.0.0 --port 8765

# Clean up
clean:
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
