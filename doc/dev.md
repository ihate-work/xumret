# dev

Detailed dev rules YOU MUST FOLLOW OR YOU WILL BE FIRED AND A UNICORN WILL CRY IN SHINING TEARS.

## Principles

- readable
- testable
- with test cases
- exactly matches human's intention
- clear module separation
- separation of concern
- exported api should have stable signatures and short comment
- only add comment if it's required. use code for "what" and "how". comment is for when "why" is not clearly visible.

## Python

### No mutable globals

Do not use module-level mutable state (`_foo = None` / `global _foo`) for services, config, or database connections. It makes code hard to test and hides dependencies.

Instead, wire dependencies through **constructor arguments** or **framework DI** (e.g. FastAPI `Depends` + `app.state`). Module-level constants and loggers are fine.

```py
# bad — hidden global, needs reset_* helper for tests
_engine = None
def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(...)
    return _engine

# good — created in lifespan, injected via DI
@asynccontextmanager
async def lifespan(app):
    app.state.engine = create_engine(...)
    yield

def _dep_engine(request: Request) -> Engine:
    return request.app.state.engine
EngineDep = Annotated[Engine, Depends(_dep_engine)]
```

### Data models: Pydantic by default

For any structured record — config, request/response payloads, internal specs, small value objects — use `pydantic.BaseModel`. Do not reach for `dataclasses`, `TypedDict`, or `NamedTuple` unless there is a concrete reason Pydantic can't be used (e.g. a hot loop where validation overhead is measured, or interop with a library that requires `dataclass`). We already depend on Pydantic everywhere; using it consistently gives us validation, `.model_dump()`, and JSON round-tripping for free.

Pydantic `BaseModel.__init__` only accepts **keyword arguments**:

```py
class _SignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    name: str
    columns: list[str]

_SignalSpec(name="log", columns=[...])       # good
_SignalSpec("log", [...])                    # TypeError — positional args not supported
```

Use `ConfigDict(frozen=True)` for immutable specs and `arbitrary_types_allowed=True` when the model contains non-Pydantic types (callables, third-party classes, etc).

### o11y — MANDATORY, NO EXCEPTIONS

**ALL logging, tracing, and metrics MUST use `ihate_work.o11y`.** This is not optional. It is a hard requirement for every Python file in this project. Violations are must-fix bugs.

The `ihate_work` package is installed from GitHub (`local-ihate-work @ git+https://github.com/ihate-work/ihate-library`). It provides a unified pipeline: structlog → stdlib logging → OTEL LoggingHandler → OTLP export.

#### FORBIDDEN

- **`logging.getLogger()`** — NEVER use stdlib logging directly. Not in modules, not in scripts, not "just for debugging". NEVER.
- **`print()` for operational output** — Use the logger. `print()` is only acceptable for CLI user-facing output (e.g. Click commands printing results).
- **printf-style formatting in log calls** — `logger.info("page %d", 1)` is WRONG. structlog uses keyword args.
- **f-string event messages** — `logger.info(f"page {page}")` is WRONG. Pass data as keyword args.

#### Setup (exactly once, at the process entry point)

`setup_otel()`, `setup_structlog()`, and `setup_library_logging()` must each be called **exactly once**, in the entry point (e.g. `__main__.py`). A second call raises `RuntimeError`. Library modules MUST NOT call them.

```py
import ihate_work.o11y as o11y

# in __main__.py or equivalent entry point — ONE TIME ONLY
o11y.setup_otel()
o11y.setup_structlog()
```

`setup_otel()` reads `OTEL_EXPORTER_OTLP_ENDPOINT`. If set, it enables OTLP/HTTP export (traces, metrics, logs). If unset, no export happens (or console fallback if `fallback_to_console=True`).

#### Per-module usage

Every module that needs logging, tracing, or metrics:

```py
from ihate_work.o11y import get_o11y
logger, tracer, meter = get_o11y(__name__)

# Logging — structlog keyword args, ALWAYS
logger.info("loaded page", page=1, count=100)       # CORRECT
logger.warning("retry failed", attempt=3, err=str(e))  # CORRECT
logger.info("loaded page %d", 1)                     # WRONG — printf-style
logger.info(f"loaded page {page}")                    # WRONG — f-string in event

# Tracing
with tracer.start_as_current_span("my_operation"):
    ...

# Metrics
counter = meter.create_counter("requests_total")
counter.add(1, {"endpoint": "/api/exec"})
```

#### OTLP-safe values

structlog values MUST be primitives (bool, int, float, str, bytes) or dicts/lists of them. Non-primitive values are coerced to `str` with a one-time warning by `_coerce_otel_value()`. Don't rely on this — serialize explicitly.

```py
logger.info("result", data=model.model_dump())     # CORRECT — dict of primitives
logger.info("result", data=model)                   # BAD — Pydantic model is not a primitive
```

#### OTEL log record shape

Understanding the output format helps write good log calls:

```
body (message):
  {
    "message": "importing",
    "level": "info",
    "timestamp": "2026-04-20T14:41:34.703208Z",
    "entity": "subjects",       ← your keyword args land here
    "count": 1000
  }

attributes:
  thread.name = "MainThread"
  thread.id   = 140234567890
  code.filepath = "/.../server.py"
  code.function = "handle_exec"
  code.lineno   = 86

scope.name: "xumret.server.handler"   ← from __name__
```

Body contains your callsite data (keyword args). Runtime metadata (`thread.*`, `code.*`) is in attributes. Module identity is `scope.name`.

#### uvicorn caveat

`uvicorn.run()` overrides logging config by default, which destroys our structlog pipeline. ALWAYS disable it:

```py
uvicorn.run(app, host="0.0.0.0", port=8765, log_config=None)
```

Then reconfigure uvicorn loggers to propagate through the root logger:

```py
for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    uv_logger = logging.getLogger(name)
    uv_logger.handlers.clear()
    uv_logger.propagate = True
```

#### Environment variables

| Variable | Purpose |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint (e.g. `http://localhost:4318`). Enables export. |
| `OTEL_SERVICE_NAME` | Service name in OTEL resource attributes (e.g. `xumret-server`) |
| `IHATE_WORK_LOG_DIR` | If set, structlog also writes JSONL files locally (one per date+pid) |

#### Library log silencing

`ihate_work.o11y` automatically silences noisy third-party loggers:
- **INFO**: httpcore, sqlalchemy, PIL, sse_starlette, watchfiles, urllib3, multipart
- **WARN**: httpx, elastic_transport.transport, LiteLLM

You do not need to configure this manually.

### pytest

Test files should be named `TESTEE_test.py` and placed **beside** the testee module (same directory), not in a separate `tests/` tree.

### Long running processes

Orphan processes from previous sessions waste resources and hold ports.

Makefile and scripts should use the normal command like:

```makefile
server-dev:
	venv/bin/python -m uvicorn ... --port 8765
```

If a service has to be started -- ask your human to do so. He likely already started one.

As a smart agent, never start a long-running server (uvicorn, flask, etc.) without a `timeout` wrapper unless you REALLY have to do so.

### Graceful shutdown for child processes

Any component that spawns child processes (subprocesses, daemons, background tasks) **must** clean them up on server shutdown. Rely on **graceful shutdown only** — do not attempt to revive or reconnect to orphans after a server restart.

Rules:

1. **FastAPI lifespan** is the shutdown hook. The `lifespan` async context manager's teardown phase (`yield` → exit) must call `shutdown()` on the service/executor.
2. **Executor.shutdown()** iterates all tracked child processes and kills them (terminate → brief wait → force kill → drain).
3. **Service.shutdown()** cancels in-flight `asyncio.Task`s, then delegates to the executor.
4. **Don't rely on `__del__`** — Python doesn't guarantee finalizer execution. Use explicit shutdown.
5. **SIGKILL / OOM**: nothing runs. For pipe-connected children, the broken pipe delivers SIGPIPE which kills them. For file-spooled children, add a startup reaper that scans stale PID files if needed.

The priority order: graceful shutdown (covers 95%) > SIGPIPE from broken pipes (automatic) > startup orphan reaper (only if file-spooling is used).

### dotenv

Always use `load_dotenv(override=False)` so that env vars set on the command line (e.g. in Makefile targets) take precedence over `.env` file values.

### Dependency management (uv)

Deps are managed with **uv + requirements files** (not `uv sync` / `pyproject.toml` deps).

The shared library `ihate_work` is installed from GitHub:

```
local-ihate-work @ git+https://github.com/ihate-work/ihate-library
```

Install base deps:
```sh
make deps          # installs requirements.txt into venv
```

## TypeScript / React

### Generic Dev Dependencies

- TypeScript config:
  - tsconfig.json should extend `@tsconfig/strictest`
  - other package-wise config should be above the configs being extended
- code formatter: `dprint`
- testing: `vitest`
- asset bundler: `vite`
- linter: no linter (playground-like repo)

### Type checking

Always run `npx tsc --noEmit` after any file change (create, rename, edit, delete) to catch type errors immediately. Do not consider a change complete until tsc passes cleanly.

### File and path conventions

Source lives in `webui-src/` with three top-level directories:

- `pages/` — route pages (see below)
- `components/` — shared UI components
- `util/` — pure helpers, hooks, types

**Page files** follow a nested directory structure that mirrors the route path. Each page is an `index.tsx` inside a directory named after its route segment. Dynamic segments use `:paramName`.

```
pages/
  devices/
    index.tsx                              → /devices          (DevicesPage)
    :deviceId/
      index.tsx                            → /devices/:deviceId (DevicePage)
      commands/
        index.tsx                          → /devices/:deviceId/commands          (DeviceCommandsPage)
        :commandId/
          index.tsx                        → /devices/:deviceId/commands/:commandId (DeviceCommandPage)
```

Rules:
- Page component names end with `Page` (e.g. `DevicesPage`, `DevicePage`).
- Dynamic directory names must match the route param name (`:deviceId`, not `:id`).
- The `~` import alias resolves to `webui-src/` (configured in both `vite.config.mts` and `tsconfig.json`). Use `~/components/Foo` instead of fragile relative paths for cross-directory imports.

### Key conventions

- **structlog-style keyword args** for any structured logging
- **Pydantic models** for all API payloads shared between frontend and backend

### Mechanism vs policy

The backend is **mechanism** — a generic process runner with no termux-api domain knowledge. The WebUI is **policy** — it knows which commands to compose for each use case and how to present their results. Do not leak domain-specific termux-api logic into the Python backend; it belongs in the frontend.

## Code Review Checklist

When reviewing code, evaluate against all of the following perspectives. Skip any that have nothing to flag.

### Correctness
- Logic errors, off-by-one, wrong operator, missing edge cases
- Incorrect API usage (wrong arg types, missing required params)
- Resource leaks (unclosed files/connections, missing cleanup)
- Race conditions or concurrency issues

### Readability
- Unclear naming (variables, functions, parameters)
- Overly complex expressions that should be broken up
- Dead code or unreachable branches
- Misleading comments (worse than no comment)

### Testability & Tests
- New logic without corresponding tests
- Test file naming: must be `TESTEE_test.py`, beside the testee module
- Tests that don't actually assert anything meaningful
- Tests coupled to implementation details rather than behavior

### Security
- Injection risks (SQL, command, XSS, template)
- Hardcoded secrets or credentials
- Unsafe deserialization or eval
- Overly broad permissions or exception handling that swallows errors

### o11y (ALWAYS CHECK)
- Any use of `logging.getLogger()` — MUST be replaced with `get_o11y(__name__)`
- Any use of `print()` for operational logging — MUST use the logger
- Printf-style or f-string log formatting — MUST use keyword args
- `setup_otel()` / `setup_structlog()` called outside the entry point — MUST be entry-point only
- Non-primitive values in structlog calls — MUST serialize to dict/primitives
- Missing `log_config=None` in `uvicorn.run()` — MUST be present

### Severity

- **must-fix**: bugs, security issues, convention violations, o11y violations
- **should-fix**: readability problems, missing tests, unclear intent
- **nit**: minor style preferences (keep these to a minimum)

Focus on substance over style. Three real findings beat twenty nitpicks.
