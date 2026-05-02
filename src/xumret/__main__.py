import click
import ihate_work.o11y as o11y
from dotenv import load_dotenv

load_dotenv(override=False)
o11y.setup_otel()
o11y.setup_structlog()


@click.group()
def cli():
    """xumret - remote control for termux-api."""


from xumret.phone import main as client_cmd
from xumret.server import main as server_cmd

cli.add_command(server_cmd, "server")
cli.add_command(client_cmd, "client")

if __name__ == "__main__":
    cli()
