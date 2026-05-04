
default: deps
	@echo "deps installed"

###
### SECTION dev scripts
###

PY_CODE_ROOTS = src/ tests/

format:
	npx dprint fmt .

typecheck: deps
	venv/bin/mypy src

test: deps
	venv/bin/pytest $(PY_CODE_ROOTS)

test-watch: deps
	. venv/bin/activate && exec pytest-watcher $(PY_CODE_ROOTS)

webui-dev: webui-deps
	npx vite --host

webui-deps: node_modules/.webui_deps_installed

node_modules/.webui_deps_installed: package.json package-lock.json
	npm ci
	@touch $@

# Run client connecting to localhost (for local dev)
client-local: deps
	OTEL_SERVICE_NAME=xumret-client venv/bin/python -m xumret client --host localhost --port 8765

# Run server in dev mode (listens on all interfaces)
server-dev: deps
	OTEL_SERVICE_NAME=xumret-server venv/bin/python -m xumret server --host 0.0.0.0 --port 8765

###
### SECTION deps
###

PYTHON_VER ?= 3.13

REQUIREMENTS = -r requirements.txt
UV_PIP_INSTALL = UV_PYTHON=venv UV_LINK_MODE=symlink uv pip install '--only-binary=:all:'

deps: Makefile venv/.deps_installed

venv/.deps_installed: venv/.venv_created requirements.txt
	$(UV_PIP_INSTALL) $(REQUIREMENTS)
	@echo "deps installed"
	@touch $@

venv: venv/.venv_created

venv/.venv_created: Makefile
	uv venv --clear --python=$(PYTHON_VER) venv
	@touch $@
	@rm -fv venv/.deps_installed

clean:
	rm -rf venv __pycache__ .pytest_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

.PHONY:
