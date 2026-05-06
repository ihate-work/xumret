---
name: code-deps
description: "Manage Python/Node dependencies in this project. Use this to install/update deps in the smooth way."
allowed-tools: [Read, Edit, Bash, Glob, Grep]
---

# code-deps — Dependency Management

Manage Python and Node dependencies for the xumret project. This skill covers adding, removing, upgrading, and troubleshooting packages.

## Critical Rules

- **NEVER run `pip install` or `uv pip install` directly.** Always add the package to `requirements.txt` first, then run `make deps`.
- **NEVER edit `venv/` contents manually.** The venv is managed by uv via the Makefile.

## Python Dependencies

### Layout

| Path | Purpose |
|---|---|
| `requirements.txt` | All Python deps (pinned and unpinned) |
| `Makefile` | `deps`, venv creation targets |
| `venv/` | The uv-managed virtualenv (Python 3.13) |

### Adding a New Python Package

1. **Edit `requirements.txt`**: Add the package. Don't add a version — uv will find the latest compatible version.
2. **Install**: Run `make deps`
3. **Verify**: The Makefile target uses `uv pip install -r requirements.txt` under the hood. It touches `venv/.deps_installed` as a sentinel file so subsequent `make deps` calls are no-ops unless `requirements.txt` changes.

### Shared library (`ihate_work`)

The `local-ihate-work` package is installed from GitHub (not a local editable tree):

```
local-ihate-work @ git+https://github.com/ihate-work/ihate-library
```

This provides `ihate_work.o11y`, `ihate_work.util`, etc. To upgrade to the latest commit, run:

```bash
uv pip install --force-reinstall "local-ihate-work @ git+https://github.com/ihate-work/ihate-library"
```

Or delete the venv and reinstall: `make clean && make deps`.

### Removing a Python Package

1. Remove the line from `requirements.txt`.
2. Run `make deps`. Note: uv may not uninstall the removed package from the existing venv automatically. If a clean state is needed, run `make clean && make deps` to recreate.

### Venv Details

- **Location**: `venv/`
- **Python version**: 3.13 (set by `PYTHON_VER` in Makefile)
- **Created by**: `uv venv --clear --python=3.13 venv`
- **Sentinel files**: `venv/.venv_created` (venv exists), `venv/.deps_installed` (deps are current)
- **Environment variables used during install**: `UV_PYTHON=venv UV_LINK_MODE=symlink`
- **Interpreter path**: `venv/bin/python`

To recreate the venv from scratch: `make clean && make deps`.

### Troubleshooting Python Deps

- **`ModuleNotFoundError`**: Check that the package is in `requirements.txt` and run `make deps`. If the sentinel file is up to date but the package is missing, delete `venv/.deps_installed` and re-run.
- **Stale venv**: Run `make clean && make deps` to get a clean state.
- **`make deps` is a no-op but packages are missing**: The sentinel `venv/.deps_installed` may be newer than `requirements.txt`. Run `touch requirements.txt && make deps` to force reinstall.

## Node Dependencies (Web UI)

### Layout

| Path | Purpose |
|---|---|
| `package.json` | JS deps for the web UI |
| `package-lock.json` | Lockfile (committed) |

### Adding a New Node Package

```bash
npm install <package-name>
```

For dev dependencies:

```bash
npm install -D <package-name>
```

### Installing

```bash
make webui-deps
```

This runs `npm ci` and touches `node_modules/.webui_deps_installed` as a sentinel.

### Troubleshooting Node Deps

- **Module not found**: Run `npm ci` to reinstall from the lockfile.
- **Lockfile conflicts**: Delete `node_modules/` and `package-lock.json`, then run `npm install` to regenerate. Only do this as a last resort.
