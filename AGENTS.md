This directory contains `xumret`, a remote control solution for termux and termux-api.

Please check README.md to grasp the idea of the project.

Please check doc/architecture.md to understand the components and roles.

## Code

- src/ : python code for server and clients

- xumret-controller: React+TypeScript code for official controller UI.

## Vendor packages

The dependency `termux-api` `termux-app` `termux-api-packages` repositories are added as git submodules for reference.

Their code schematic is [indexed](doc/termux-schematic.md). Please refer to (and update if needed) the index to save your and human's energy.

## Shared library

Depends on `local-ihate-work` from `../ihate_library` (editable install). Provides `ihate_work.o11y` for observability.

## Coding rules

Inherited from vibra conventions:

- **o11y**: Use `ihate_work.o11y` exclusively (not stdlib `logging.getLogger()`). structlog uses keyword args, not printf-style. `setup_otel()` / `setup_structlog()` called exactly once at entry point (`__main__.py`).
- **Data models**: Pydantic `BaseModel` by default for structured records. Keyword args only.
- **No mutable globals**: Wire deps through constructor args or framework DI.
- **Tests**: Named `TESTEE_test.py`. Run with `make test`.
- **dotenv**: Always `load_dotenv(override=False)`.
- **Formatting**: ruff (line-length 100, select E/F/I/N/W/UP).
