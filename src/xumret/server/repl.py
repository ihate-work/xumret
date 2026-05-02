"""Interactive REPL for xumret server."""

import asyncio
import json
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xumret.server import Server


async def run_repl(server: "Server") -> None:
    """Run interactive command REPL."""
    print("\nXumret Server REPL")
    print("Commands:")
    print("  list                    - List connected clients")
    print("  send <client> <cmd>     - Send command to client")
    print("  send <client> <cmd> {}  - Send command with JSON args")
    print("  broadcast <cmd>         - Send command to all clients")
    print("  quit                    - Stop server")
    print()

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        try:
            print("> ", end="", flush=True)
            line = await reader.readline()
            if not line:
                break

            cmd_line = line.decode().strip()
            if not cmd_line:
                continue

            parts = cmd_line.split(maxsplit=3)
            cmd = parts[0].lower()

            if cmd == "quit":
                server.stop()
                break

            elif cmd == "list":
                clients = server.list_clients()
                if clients:
                    for c in clients:
                        print(f"  {c['client_name']} ({c['client_id']})")
                else:
                    print("  No clients connected")

            elif cmd == "send" and len(parts) >= 3:
                target = parts[1]
                api_cmd = parts[2]
                args = {}
                if len(parts) > 3:
                    try:
                        args = json.loads(parts[3])
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON args: {e}")
                        continue

                results = await server.send_command(target, api_cmd, args)
                for client_name, result in results.items():
                    print(f"  {client_name}: {result.model_dump_json(indent=2)}")

            elif cmd == "broadcast" and len(parts) >= 2:
                api_cmd = parts[1]
                args = {}
                if len(parts) > 2:
                    try:
                        args = json.loads(parts[2])
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON args: {e}")
                        continue

                results = await server.send_command("*", api_cmd, args)
                for client_name, result in results.items():
                    print(f"  {client_name}: {result.model_dump_json(indent=2)}")

            else:
                print(
                    "Unknown command. Type 'list', 'send <client> <cmd>', 'broadcast <cmd>', or 'quit'"
                )

        except Exception as e:
            print(f"Error: {e}")
