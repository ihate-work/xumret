import click
import ihate_work.o11y as o11y
from dotenv import load_dotenv
import logging

load_dotenv(override=False)
o11y.setup_otel()
o11y.setup_structlog(level=logging.DEBUG)


@click.group()
def cli():
    """xumret - remote control for termux-api."""


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8080, type=int, help="Port to listen on")
@click.option("--dummy", is_flag=True, help="Use DummyExecutor (fake responses, no phone needed)")
def single(host: str, port: int, dummy: bool) -> None:
    """Run xumret in single mode (everything on phone)."""
    import uvicorn

    from xumret.server.api.app import create_app
    from xumret.single import SingleMain
    from xumret.state.phone import PhoneState

    if dummy:
        from xumret.executor.dummy_executor import DummyExecutor

        executor = DummyExecutor()
    else:
        from xumret.executor.local import LocalExecutor

        executor = LocalExecutor()

    state = PhoneState()
    service = SingleMain(executor=executor, state=state)
    app = create_app(service=service)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
    uvicorn.run(app, host=host, port=port, log_config=None)


if __name__ == "__main__":
    cli()
