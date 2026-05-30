import logging
from pathlib import Path

import click
import ihate_work.o11y as o11y
import uvicorn
from dotenv import load_dotenv

load_dotenv(override=False)
o11y.setup_otel()
o11y.setup_structlog(level=logging.DEBUG)


@click.group()
def cli() -> None:
    """xumret - remote control for termux-api."""


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8080, type=int, help="Port to listen on")
@click.option(
    "--dummy", is_flag=True, help="Use DummyExecutor (fake responses, no phone needed)"
)
def single(host: str, port: int, dummy: bool) -> None:
    """Run xumret in single mode (everything on phone)."""

    from xumret.protocol.executor import Executor
    from xumret.server.api.app import create_app
    from xumret.single import SingleMain
    from xumret.state.phone import PhoneState

    executor: Executor
    if dummy:
        from xumret.executor.dummy_executor import DummyExecutor

        executor = DummyExecutor()
    else:
        from xumret.executor.local_executor import LocalExecutor

        executor = LocalExecutor()

    state = PhoneState()
    service = SingleMain(executor=executor, state=state)
    app = create_app(service=service)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
    uvicorn.run(app, host=host, port=port, log_config=None)


@cli.command("dev-openapi")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output path (default: stdout).",
)
def dev_openapi(output: Path | None) -> None:
    """Export the FastAPI OpenAPI schema as YAML."""
    import yaml

    from xumret.executor.dummy_executor import DummyExecutor
    from xumret.server.api.app import create_app
    from xumret.single import SingleMain
    from xumret.state.phone import PhoneState

    service = SingleMain(executor=DummyExecutor(), state=PhoneState())
    app = create_app(service=service)
    text = yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True)
    if output is None:
        click.echo(text, nl=False)
    else:
        output.write_text(text)
        click.echo(f"wrote {output}", err=True)


if __name__ == "__main__":
    cli()
