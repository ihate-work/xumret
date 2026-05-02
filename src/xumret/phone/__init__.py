"""xumret client - runs on Termux, connects to server."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

import click
import ihate_work.o11y as o11y
import websockets
from websockets.client import WebSocketClientProtocol

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

# Default config path
CONFIG_DIR = Path.home() / ".config" / "xumret"
CLIENT_ID_FILE = CONFIG_DIR / "client_id"


def get_or_create_client_id() -> str:
    """Get existing client ID or create a new one."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CLIENT_ID_FILE.exists():
        return CLIENT_ID_FILE.read_text().strip()
    client_id = str(uuid.uuid4())
    CLIENT_ID_FILE.write_text(client_id)
    return client_id


class TermuxExecutor:
    """Execute termux-api commands."""

    # Map command names to termux-api binaries
    COMMAND_MAP = {
        "battery-status": "termux-battery-status",
        "vibrate": "termux-vibrate",
        "torch": "termux-torch",
        "clipboard-get": "termux-clipboard-get",
        "clipboard-set": "termux-clipboard-set",
        "notification": "termux-notification",
        "toast": "termux-toast",
        "location": "termux-location",
        "wifi-connectioninfo": "termux-wifi-connectioninfo",
        "telephony-deviceinfo": "termux-telephony-deviceinfo",
        "volume": "termux-volume",
        "sms-list": "termux-sms-list",
        "sms-send": "termux-sms-send",
        "call-log": "termux-call-log",
        "contact-list": "termux-contact-list",
        "camera-photo": "termux-camera-photo",
        "camera-info": "termux-camera-info",
        "microphone-record": "termux-microphone-record",
    }

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(10)  # Max concurrent commands

    async def execute(self, cmd: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a termux-api command."""
        if cmd not in self.COMMAND_MAP:
            raise ValueError(f"Unknown command: {cmd}")

        binary = self.COMMAND_MAP[cmd]
        cmd_args = self._build_args(cmd, args)

        async with self._semaphore:
            return await self._run_command(binary, cmd_args, args)

    def _build_args(self, cmd: str, args: dict[str, Any]) -> list[str]:
        """Build command line arguments from args dict."""
        cmd_args: list[str] = []

        for key, value in args.items():
            if value is None:
                continue
            if isinstance(value, bool):
                if value:
                    cmd_args.append(f"--{key}")
            elif isinstance(value, (int, float)):
                cmd_args.extend(
                    [f"-{key[0]}" if len(key) == 1 else f"--{key}", str(value)]
                )
            else:
                cmd_args.extend(
                    [f"-{key[0]}" if len(key) == 1 else f"--{key}", str(value)]
                )

        return cmd_args

    async def _run_command(
        self, binary: str, cmd_args: list[str], original_args: dict[str, Any]
    ) -> dict[str, Any]:
        """Run the actual command and capture output."""
        # Handle commands that need stdin input
        stdin_data: bytes | None = None
        if binary == "termux-clipboard-set":
            stdin_data = original_args.get("text", "").encode()
            cmd_args = []  # clipboard-set reads from stdin
        elif binary == "termux-toast":
            stdin_data = original_args.get("text", "").encode()
            cmd_args = [
                a
                for a in cmd_args
                if not a.startswith("--text") and a != original_args.get("text")
            ]

        full_cmd = [binary] + cmd_args
        logger.debug("executing command", cmd=full_cmd)

        try:
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin_data), timeout=self.timeout
            )

            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": stderr.decode().strip() or f"Exit code {proc.returncode}",
                }

            # Try to parse JSON output
            output = stdout.decode().strip()
            try:
                data = json.loads(output) if output else {}
            except json.JSONDecodeError:
                data = {"raw": output}

            return {"success": True, "data": data}

        except asyncio.TimeoutError:
            return {"success": False, "error": "TIMEOUT"}
        except FileNotFoundError:
            return {"success": False, "error": f"Command not found: {binary}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class Client:
    """Xumret WebSocket client."""

    def __init__(
        self,
        server_url: str,
        client_name: str,
        client_id: str | None = None,
    ):
        self.server_url = server_url
        self.client_name = client_name
        self.client_id = client_id or get_or_create_client_id()
        self.executor = TermuxExecutor()
        self._websocket: WebSocketClientProtocol | None = None
        self._seq = 0
        self._stop_event: asyncio.Event | None = None
        self._reconnect_delay = 1.0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    async def start(self) -> None:
        """Start the client with auto-reconnection."""
        self._stop_event = asyncio.Event()

        while not self._stop_event.is_set():
            try:
                await self._connect_and_run()
            except Exception as e:
                logger.error("connection error", error=str(e))

            if not self._stop_event.is_set():
                logger.info("reconnecting", delay_s=self._reconnect_delay)
                await asyncio.sleep(self._reconnect_delay)
                # Exponential backoff, max 60s
                self._reconnect_delay = min(self._reconnect_delay * 2, 60.0)

    def stop(self) -> None:
        """Stop the client."""
        if self._stop_event:
            self._stop_event.set()

    async def _connect_and_run(self) -> None:
        """Connect to server and handle messages."""
        logger.info("connecting to server", url=self.server_url)

        async with websockets.connect(self.server_url) as websocket:
            self._websocket = websocket
            self._seq = 0

            # Send HELLO
            hello = Hello.create(self.client_id, self.client_name)
            await websocket.send(serialize_message(hello))
            logger.info("connected", client_name=self.client_name)

            # Reset backoff on successful connection
            self._reconnect_delay = 1.0

            # Handle messages
            await self._handle_messages(websocket)

    async def _handle_messages(self, websocket: WebSocketClientProtocol) -> None:
        """Handle incoming messages from server."""
        async for raw in websocket:
            try:
                msg = parse_message(raw)
                await self._process_message(websocket, msg)
            except Exception as e:
                logger.exception("error processing message", error=str(e))

    async def _process_message(
        self, websocket: WebSocketClientProtocol, msg: Message
    ) -> None:
        """Process a single message from server."""
        if isinstance(msg, Ping):
            # Respond with pong
            pong = Pong(seq=self._next_seq())
            await websocket.send(serialize_message(pong))

        elif isinstance(msg, Cmd):
            # Execute command
            cmd_id = msg.payload.get("id", "")
            cmd = msg.payload.get("cmd", "")
            args = msg.payload.get("args", {})

            logger.info("executing command", cmd=cmd)

            try:
                result = await self.executor.execute(cmd, args)

                if result.get("success"):
                    response = CmdResult.create(
                        cmd_id, "ok", result.get("data"), seq=self._next_seq()
                    )
                else:
                    response = CmdError.create(
                        cmd_id, result.get("error", "UNKNOWN"), seq=self._next_seq()
                    )
            except ValueError as e:
                response = CmdError.create(cmd_id, str(e), seq=self._next_seq())
            except Exception as e:
                logger.exception("command execution failed", error=str(e))
                response = CmdError.create(
                    cmd_id, "COMMAND_FAILED", seq=self._next_seq()
                )

            await websocket.send(serialize_message(response))

        else:
            logger.warning("unexpected message type", msg_type=msg.type)


async def run_client(host: str, port: int, name: str) -> None:
    """Run the client."""
    url = f"ws://{host}:{port}"
    client = Client(url, name)
    await client.start()


@click.command()
@click.option("--host", default="localhost", help="Server host to connect to")
@click.option("--port", default=8765, help="Server port")
@click.option("--name", required=True, help="Client name (e.g., phone-home)")
def main(host: str, port: int, name: str) -> None:
    """Start the xumret client."""
    asyncio.run(run_client(host, port, name))


if __name__ == "__main__":
    main()
