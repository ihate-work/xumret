"""DummyExecutor — emits canned events without spawning processes.

Used for local development and tests where real subprocess execution is
unnecessary or undesirable. Recognises common termux-api binary names in argv
and emits plausible fake stdout. Unknown commands get a generic stub.
"""

from __future__ import annotations

import asyncio
import json
import time

import ihate_work.o11y as o11y

from xumret.protocol.executor import Executor
from xumret.state.models import (
    RunOutputEvent,
    RunStateCancelled,
    RunStateCompleted,
    RunStateRunning,
    RunStateStepExited,
    RunStateStepStarted,
)
from xumret.state.run import Run

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

_LATENCIES: dict[str, float] = {
    "termux-location": 0.05,
    "termux-camera-photo": 0.05,
    "termux-sms-list": 0.02,
    "termux-call-log": 0.02,
    "termux-contact-list": 0.02,
}
_DEFAULT_LATENCY = 0.005


def _fake_stdout(binary: str, argv: list[str]) -> str:
    canned = _CANNED.get(binary)
    if canned is None and binary in _CANNED:
        return ""  # known silent command
    if canned is not None:
        return (json.dumps(canned, indent=2) if not isinstance(canned, str) else canned) + "\n"
    return json.dumps({"dummy": True, "argv": argv}) + "\n"


class DummyExecutor(Executor):
    """Implements `Executor` with fake events. No real processes are spawned."""

    def __init__(self) -> None:
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._fake_pid_seed = 90000

    async def run(self, run: Run) -> None:
        slug = run.slug
        cancel_ev = asyncio.Event()
        self._cancel_events[slug] = cancel_ev
        try:
            run.emit(RunStateRunning(slug=slug, at=time.time()))
            for i, step in enumerate(run.phone_command.steps):
                if cancel_ev.is_set():
                    break
                self._fake_pid_seed += 1
                pid = self._fake_pid_seed
                run.emit(RunStateStepStarted(
                    slug=slug, at=time.time(), step_index=i, pid=pid,
                ))
                binary = step.argv[0] if step.argv else ""
                await asyncio.sleep(_LATENCIES.get(binary, _DEFAULT_LATENCY))
                stdout = _fake_stdout(binary, step.argv)
                if stdout and step.stdout_stream.capture:
                    lines = stdout.rstrip("\n").split("\n")
                    run.emit(RunOutputEvent(
                        slug=slug, at=time.time(), step_index=i,
                        fd="stdout", lines=lines,
                    ))
                run.emit(RunStateStepExited(
                    slug=slug, at=time.time(), step_index=i, exit_code=0,
                ))

            if cancel_ev.is_set():
                run.emit(RunStateCancelled(slug=slug, at=time.time()))
                return

            run.emit(RunStateCompleted(slug=slug, at=time.time()))
        finally:
            self._cancel_events.pop(slug, None)

    async def stop(self, slug: str) -> None:
        ev = self._cancel_events.get(slug)
        if ev is not None:
            ev.set()

    async def shutdown(self) -> None:
        for ev in list(self._cancel_events.values()):
            ev.set()
