"""xumret server - runs on control machine, accepts client connections."""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

import click
import ihate_work.o11y as o11y
import websockets
from websockets.server import WebSocketServerProtocol

from xumret.shared.messages import (
    Cmd,
    CmdError,
    CmdResult,
    Hello,
    Message,
    Ping,
    Pong,
    parse_message,
    serialize_message,
)

logger, *_ = o11y.get_o11y(__name__)

CLIENT_NAME_PATTERN = re.compile(r"^[a-z0-9-]{3,32}$")


@dataclass
class ConnectedClient:
    """Represents a connected client."""

    client_id: str
    client_name: str
    websocket: WebSocketServerProtocol
    seq: int = 0
    pending_commands: dict[str, asyncio.Future] = field(default_factory=dict)

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq


class Server:
    """Xumret WebSocket server."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: dict[str, ConnectedClient] = {}  # client_name -> client
        self._stop_event: asyncio.Event | None = None

    async def start(self) -> None:
        """Start the server."""
        self._stop_event = asyncio.Event()
        logger.info("starting server", host=self.host, port=self.port)

        async with websockets.serve(self._handle_connection, self.host, self.port):
            await self._stop_event.wait()

    def stop(self) -> None:
        """Stop the server."""
        if self._stop_event:
            self._stop_event.set()

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """Handle a new client connection."""
        client: ConnectedClient | None = None
        try:
            # Wait for HELLO message
            raw = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            msg = parse_message(raw)

            if not isinstance(msg, Hello):
                logger.warning("expected HELLO", got=msg.type)
                await websocket.close(1002, "Expected HELLO")
                return

            client_id = msg.payload.get("client_id", "")
            client_name = msg.payload.get("client_name", "")

            # Validate client name
            if not CLIENT_NAME_PATTERN.match(client_name):
                logger.warning("invalid client name", client_name=client_name)
                await websocket.close(1002, "Invalid client name")
                return

            # Check for duplicate name
            if client_name in self.clients:
                logger.warning("duplicate client name", client_name=client_name)
                await websocket.close(1002, "Client name already connected")
                return

            # Register client
            client = ConnectedClient(
                client_id=client_id,
                client_name=client_name,
                websocket=websocket,
            )
            self.clients[client_name] = client
            logger.info(
                "client connected", client_name=client_name, client_id=client_id
            )

            # Handle messages
            await self._handle_messages(client)

        except asyncio.TimeoutError:
            logger.warning("client did not send HELLO in time")
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.exception("error handling connection", error=str(e))
        finally:
            if client and client.client_name in self.clients:
                del self.clients[client.client_name]
                logger.info("client disconnected", client_name=client.client_name)

    async def _handle_messages(self, client: ConnectedClient) -> None:
        """Handle messages from a connected client."""
        async for raw in client.websocket:
            try:
                msg = parse_message(raw)
                await self._process_message(client, msg)
            except Exception as e:
                logger.exception("error processing message", error=str(e))

    async def _process_message(self, client: ConnectedClient, msg: Message) -> None:
        """Process a single message from client."""
        if isinstance(msg, Pong):
            # Keepalive response, ignore for now
            pass
        elif isinstance(msg, CmdResult):
            cmd_id = msg.payload.get("id")
            if cmd_id in client.pending_commands:
                client.pending_commands[cmd_id].set_result(msg)
        elif isinstance(msg, CmdError):
            cmd_id = msg.payload.get("id")
            if cmd_id in client.pending_commands:
                client.pending_commands[cmd_id].set_result(msg)
        else:
            logger.warning("unexpected message type from client", msg_type=msg.type)

    async def send_command(
        self,
        target: str | list[str],
        cmd: str,
        args: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Message]:
        """Send command to target client(s) and wait for response."""
        # Resolve targets
        if target == "*":
            targets = list(self.clients.keys())
        elif isinstance(target, str):
            targets = [target]
        else:
            targets = target

        results: dict[str, Message] = {}

        async def send_to_client(client_name: str) -> None:
            if client_name not in self.clients:
                results[client_name] = CmdError.create("", "CLIENT_NOT_CONNECTED")
                return

            client = self.clients[client_name]
            cmd_msg = Cmd.create(cmd, args, seq=client.next_seq())
            cmd_id = cmd_msg.payload["id"]

            # Create future for response
            future: asyncio.Future = asyncio.Future()
            client.pending_commands[cmd_id] = future

            try:
                await client.websocket.send(serialize_message(cmd_msg))
                result = await asyncio.wait_for(future, timeout=timeout)
                results[client_name] = result
            except asyncio.TimeoutError:
                results[client_name] = CmdError.create(cmd_id, "TIMEOUT")
            finally:
                client.pending_commands.pop(cmd_id, None)

        await asyncio.gather(*[send_to_client(name) for name in targets])
        return results

    async def ping_client(self, client_name: str) -> bool:
        """Send ping to client and wait for pong."""
        if client_name not in self.clients:
            return False

        client = self.clients[client_name]
        ping_msg = Ping(seq=client.next_seq())

        try:
            await client.websocket.send(serialize_message(ping_msg))
            return True
        except Exception:
            return False

    def list_clients(self) -> list[dict[str, str]]:
        """List all connected clients."""
        return [
            {"client_id": c.client_id, "client_name": c.client_name}
            for c in self.clients.values()
        ]


# Global server instance for CLI
_server: Server | None = None


async def run_server(host: str, port: int, interactive: bool = False) -> None:
    """Run the server."""
    global _server
    _server = Server(host, port)

    if interactive:
        from xumret.server.repl import run_repl

        async def server_with_repl() -> None:
            server_task = asyncio.create_task(_server.start())
            await asyncio.sleep(0.5)  # Let server start
            await run_repl(_server)
            server_task.cancel()

        await server_with_repl()
    else:
        await _server.start()


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8765, help="Port to listen on")
@click.option("--interactive", "-i", is_flag=True, help="Start interactive REPL")
def main(host: str, port: int, interactive: bool) -> None:
    """Start the xumret server."""
    asyncio.run(run_server(host, port, interactive))


if __name__ == "__main__":
    main()
