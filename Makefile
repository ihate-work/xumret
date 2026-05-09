
default: runtime-deps
	@echo "deps installed"

###
### SECTION dev scripts
###

PY_CODE_ROOTS = src/

format:
	npx dprint fmt .

typecheck: deps
	venv/bin/mypy src

test: deps
	venv/bin/pytest $(PY_CODE_ROOTS)

test-cov: deps
	venv/bin/pytest $(PY_CODE_ROOTS) --cov --cov-report=term-missing --cov-report=html:htmlcov

test-watch: deps
	. venv/bin/activate && exec pytest-watcher $(PY_CODE_ROOTS)

webui-dev: deps
	npx vite --host

# Run client connecting to localhost (for local dev)
client-local: runtime-deps
	OTEL_SERVICE_NAME=xumret-client venv/bin/python -m xumret client --host localhost --port 8765

# Run server in dev mode (listens on all interfaces)
server-dev: runtime-deps
	OTEL_SERVICE_NAME=xumret-server venv/bin/python -m xumret server --host 0.0.0.0 --port 8765

###
### SECTION deps
###

PYTHON_VER ?= 3.13

# requirements files
REQUIREMENTS_RUNTIME = -r requirements.txt
REQUIREMENTS_DEV = -r requirements-dev.txt -r requirements.txt

# Termux pypi index: only added on Android. Keeping it in requirements.txt would
# break Linux installs — uv's default first-match index strategy stops at the
# first index that has a package, and the Termux index ships android-only wheels.
EXTRA_INDEX := $(if $(filter Android,$(shell uname -o 2>/dev/null)),--extra-index-url https://termux-user-repository.github.io/pypi)

UV_PIP_INSTALL = UV_PYTHON=venv UV_LINK_MODE=symlink uv pip install '--only-binary=:all:' --no-binary=ihate-work --exclude-newer-package 'ihate-work=2030-01-01' $(EXTRA_INDEX)

# Default developer-facing deps: install dev + runtime deps
deps: Makefile venv/.dev_deps_installed

# Runtime-only deps (for running server/client in minimal env)
runtime-deps: Makefile venv/.deps_installed

venv/.deps_installed: venv/.venv_created requirements.txt
	$(UV_PIP_INSTALL) $(REQUIREMENTS_RUNTIME)
	@echo "runtime deps installed"
	@touch $@

venv/.dev_deps_installed: venv/.venv_created requirements.txt requirements-dev.txt package.json package-lock.json
	$(UV_PIP_INSTALL) $(REQUIREMENTS_DEV)
	npm ci
	@echo "dev deps installed"
	@touch $@

venv: venv/.venv_created

venv/.venv_created: Makefile
	uv venv --clear --python=$(PYTHON_VER) venv
	@touch $@
	@rm -fv venv/.deps_installed venv/.dev_deps_installed

clean:
	rm -rf venv __pycache__ .pytest_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

.PHONY:
