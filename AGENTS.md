This directory contains `xumret`, a remote control solution for termux and termux-api.

Please check README.md to grasp the idea of the project.

Please check doc/architecture.md to understand the components and roles.

## Code

- src/ : python code for server and clients

- webui-src/ : React+TypeScript source for the controller UI. Built output goes to webui-assets/.

## Vendor packages

The dependency `termux-api` `termux-app` `termux-api-packages` repositories are added as git submodules for reference.

Their code schematic is [indexed](doc/termux-schematic.md). Please refer to (and update if needed) the index to save your and human's energy.

## Shared library

Depends on `local-ihate-work` from `../ihate_library` (editable install). Provides `ihate_work.o11y` for observability.

## Web UI rules

- **PrimeReact is the ONLY component library.** Use PrimeReact components unconditionally for all UI (buttons, inputs, layout, data display, overlays, etc.). Do NOT use Tailwind CSS, custom utility classes, or other component libraries.
- Theme: `lara-light-cyan` (imported in `main.tsx`). Use PrimeReact's built-in theming/styling — do not override with raw CSS unless absolutely necessary.
- PrimeIcons for all icons (`primeicons` package).
- Entry point: `webui-src/main.tsx`. Vite config + tsconfig at repo root.
- Build: `make webui-dev` (dev server), `npm run build` (production → webui-assets/).

## Wits

`doc/wits.md` is a living scratchpad of small design ideas and decisions. When you encounter or make a non-obvious design choice worth preserving, add it there. Keep entries very concise — intent + rationale, one or two lines.

## Coding rules

Inherited from vibra conventions:

- **o11y**: Use `ihate_work.o11y` exclusively (not stdlib `logging.getLogger()`). structlog uses keyword args, not printf-style. `setup_otel()` / `setup_structlog()` called exactly once at entry point (`__main__.py`).
- **Data models**: Pydantic `BaseModel` by default for structured records. Keyword args only.
- **No mutable globals**: Wire deps through constructor args or framework DI.
- **Tests**: Named `TESTEE_test.py`. Run with `make test`.
- **dotenv**: Always `load_dotenv(override=False)`.
- **Formatting**: ruff (line-length 100, select E/F/I/N/W/UP).
