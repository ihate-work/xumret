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

### o11y

Use `ihate_work.o11y` for o11y. Do NOT use `logging.getLogger()` from stdlib.

The logger is structlog — use keyword args, not printf-style formatting.

```py
import ihate_work.o11y as o11y

# in entrypoint (script or notebook): run one-shot setup and summon a logger
o11y.setup_otel()
o11y.setup_structlog()
logger, *_ = o11y.get_o11y(__name__)

# in library: only the logger
logger, *_ = o11y.get_o11y(__name__)

# structlog uses keyword args:
logger.info("loaded page", page=1, count=100)  # good
logger.info("loaded page %d", 1)               # bad
```

### o11y setup guards

`setup_otel()`, `setup_structlog()`, and `setup_library_logging()` must each be called **exactly once**, at the process entry point. A second call raises `RuntimeError`. Library modules must never call them.

#### uvicorn caveat

`uvicorn.run()` applies its own `LOGGING_CONFIG` by default, which re-creates handlers on `uvicorn.*` loggers and overrides structlog formatting. Always pass `log_config=None` to keep our structlog pipeline intact:

```py
uvicorn.run(app, host="0.0.0.0", port=8107, log_config=None)
```

Then reconfigure uvicorn loggers to propagate through the root logger (which has structlog formatters):

```py
for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    uv_logger = logging.getLogger(name)
    uv_logger.handlers.clear()
    uv_logger.propagate = True
```

### pytest

Test files should be named `TESTEE_test.py`.

### Long running processes

Orphan processes from previous sessions waste resources and hold ports.

Makefile and scripts should use the normal command like:

```makefile
acnh-render-hub:
	venv/bin/python -m uvicorn ... --port 8107
```

If a service has to be started -- ask your human to do so. He likely already started one.

As a smart agent, never start a long-running server (uvicorn, flask, etc.) without a `timeout` wrapper unless you REALLY have to do so.

### dotenv

Always use `load_dotenv(override=False)` so that env vars set on the command line (e.g. in Makefile targets) take precedence over `.env` file values.

### Dependency management (uv)

Deps are managed with **uv + requirements files** (not `uv sync` / `pyproject.toml` deps).

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

### Key conventions

- **structlog-style keyword args** for any structured logging
- **Pydantic models** for all API payloads shared between frontend and backend

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
- Test file naming: must be `TESTEE_test.py`
- Tests that don't actually assert anything meaningful
- Tests coupled to implementation details rather than behavior

### Security
- Injection risks (SQL, command, XSS, template)
- Hardcoded secrets or credentials
- Unsafe deserialization or eval
- Overly broad permissions or exception handling that swallows errors

### Severity

- **must-fix**: bugs, security issues, convention violations
- **should-fix**: readability problems, missing tests, unclear intent
- **nit**: minor style preferences (keep these to a minimum)

Focus on substance over style. Three real findings beat twenty nitpicks.
