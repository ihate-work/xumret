"""DummyExecutor — returns canned responses without spawning processes.

Used for local development and tests where real subprocess execution
is unnecessary or undesirable. Recognises common termux-api binary names
in argv and returns plausible fake output. Unknown commands get a generic stub.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import ihate_work.o11y as o11y

from xumret.executor.models import (
    DaemonProcessStatus,
    DaemonStatus,
    PhoneCommandDaemonHandle,
    PhoneCommandResult,
    ProcessResult,
)
from xumret.server_bridge.models import (
    CancelCommand,
    CommandError,
    DaemonEnded,
    DaemonStatusReport,
    EndDaemon,
    QueryDaemon,
    QueryStatus,
    SubmitCommand,
    SubmitDaemonStarted,
    SubmitOneshotResult,
)

logger, *_ = o11y.get_o11y(__name__)

# Maps termux-api binary name → canned stdout content
_CANNED: dict[str, object] = {
    "termux-battery-status": {
        "health": "GOOD",
        "percentage": 72,
        "plugged": "UNPLUGGED",
        "status": "DISCHARGING",
        "temperature": 28.5,
        "current": -423000,
    },
    "termux-wifi-connectioninfo": {
        "bssid": "00:11:22:33:44:55",
        "frequency_mhz": 5180,
        "ip": "192.168.1.42",
        "link_speed_mbps": 866,
        "rssi": -45,
        "ssid": "HomeNetwork",
        "supplicant_state": "COMPLETED",
    },
    "termux-location": {
        "latitude": 35.6762,
        "longitude": 139.6503,
        "altitude": 40.0,
        "accuracy": 12.3,
        "bearing": 0.0,
        "speed": 0.0,
        "provider": "gps",
    },
    "termux-telephony-deviceinfo": {
        "data_enabled": "true",
        "data_state": "CONNECTED",
        "device_id": "000000000000000",
        "device_software_version": "01",
        "network_operator": "44010",
        "network_operator_name": "NTT DOCOMO",
        "network_type": "LTE",
        "phone_type": "GSM",
        "sim_operator": "44010",
        "sim_operator_name": "NTT DOCOMO",
        "sim_state": "READY",
    },
    "termux-camera-info": [
        {
            "id": "0",
            "facing": "back",
            "jpeg_output_sizes": [
                {"width": 4032, "height": 3024},
                {"width": 1920, "height": 1080},
            ],
        },
        {
            "id": "1",
            "facing": "front",
            "jpeg_output_sizes": [
                {"width": 3264, "height": 2448},
                {"width": 1920, "height": 1080},
            ],
        },
    ],
    "termux-clipboard-get": "clipboard contents here",
    "termux-volume": [
        {"stream": "music", "volume": 8, "max_volume": 15},
        {"stream": "ring", "volume": 5, "max_volume": 7},
        {"stream": "notification", "volume": 5, "max_volume": 7},
        {"stream": "alarm", "volume": 6, "max_volume": 7},
    ],
    "termux-contact-list": [
        {"name": "Alice", "number": "+81-90-1234-5678"},
        {"name": "Bob", "number": "+81-80-9876-5432"},
    ],
    "termux-sms-list": [
        {
            "threadid": 1,
            "type": "inbox",
            "read": True,
            "number": "+81-90-1234-5678",
            "body": "Hey, are you free tonight?",
            "received": "2026-05-01 18:32:00",
        },
        {
            "threadid": 1,
            "type": "sent",
            "read": True,
            "number": "+81-90-1234-5678",
            "body": "Sure, let me check my schedule",
            "received": "2026-05-01 18:35:00",
        },
    ],
    "termux-call-log": [
        {
            "name": "Alice",
            "phone_number": "+81-90-1234-5678",
            "type": "INCOMING",
            "date": "2026-05-01 17:00:00",
            "duration": "120",
        },
    ],
    # Commands that produce no output
    "termux-toast": None,
    "termux-vibrate": None,
    "termux-torch": None,
    "termux-notification": None,
    "termux-clipboard-set": None,
}

# Simulated latencies per binary (seconds)
_LATENCIES: dict[str, float] = {
    "termux-location": 0.8,
    "termux-camera-photo": 1.2,
    "termux-sms-list": 0.3,
    "termux-call-log": 0.3,
    "termux-contact-list": 0.2,
}
_DEFAULT_LATENCY = 0.05


def _fake_stdout(binary: str, argv: list[str]) -> str:
    """Produce canned stdout for a known binary, or a generic stub."""
    canned = _CANNED.get(binary)
    if canned is None and binary in _CANNED:
        # Known command that produces no output (toast, vibrate, ...)
        return ""
    if canned is not None:
        return (json.dumps(canned, indent=2) if not isinstance(canned, str) else canned) + "\n"
    # Unknown binary — generic stub
    return json.dumps({"dummy": True, "argv": argv}) + "\n"


class DummyExecutor:
    """Implements Executor protocol with fake results. No real processes are spawned."""

    def __init__(self) -> None:
        self._daemons: dict[str, str] = {}  # handle_id -> command_id
        self._cancelled: set[str] = set()  # command_ids

    async def submit(
        self, cmd: SubmitCommand
    ) -> SubmitOneshotResult | SubmitDaemonStarted | CommandError:
        pc = cmd.phone_command
        if pc.daemon:
            handle_id = str(uuid.uuid4())
            self._daemons[handle_id] = cmd.command_id
            logger.info("dummy daemon started", handle_id=handle_id, command_id=cmd.command_id)
            return SubmitDaemonStarted(
                handle=PhoneCommandDaemonHandle(
                    command_id=cmd.command_id, handle_id=handle_id,
                )
            )

        logger.debug("dummy oneshot", command_id=cmd.command_id, steps=len(pc.steps))
        step_results: list[ProcessResult] = []
        for step in pc.steps:
            binary = step.argv[0] if step.argv else ""
            await asyncio.sleep(_LATENCIES.get(binary, _DEFAULT_LATENCY))
            step_results.append(ProcessResult(
                exit_code=0, stdout=_fake_stdout(binary, step.argv), stderr="",
            ))

        return SubmitOneshotResult(
            result=PhoneCommandResult(
                command_id=cmd.command_id, steps=step_results,
            )
        )

    async def cancel(self, cmd: CancelCommand) -> None:
        self._cancelled.add(cmd.command_id)

    async def query_status(self, cmd: QueryStatus) -> DaemonStatusReport | CommandError:
        for handle_id, command_id in self._daemons.items():
            if command_id == cmd.command_id:
                return self._make_status(handle_id)
        return CommandError(command_id=cmd.command_id, error="not_found")

    async def query_daemon(self, cmd: QueryDaemon) -> DaemonStatusReport:
        if cmd.handle_id in self._daemons:
            return self._make_status(cmd.handle_id)
        return DaemonStatusReport(
            status=DaemonStatus(handle_id=cmd.handle_id, steps=[], all_running=False)
        )

    async def end_daemon(self, cmd: EndDaemon) -> DaemonEnded:
        self._daemons.pop(cmd.handle_id, None)
        return DaemonEnded(handle_id=cmd.handle_id, final_steps=[])

    def _make_status(self, handle_id: str) -> DaemonStatusReport:
        return DaemonStatusReport(
            status=DaemonStatus(
                handle_id=handle_id,
                steps=[DaemonProcessStatus(running=True)],
                all_running=True,
            )
        )
