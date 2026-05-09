from __future__ import annotations

from fastapi.testclient import TestClient

from xumret.executor.dummy_executor import DummyExecutor
from xumret.server.api.app import create_app
from xumret.single import SingleMain
from xumret.state.phone import PhoneState


def _make_client() -> TestClient:
    executor = DummyExecutor()
    state = PhoneState()
    service = SingleMain(executor=executor, state=state)
    app = create_app(service=service)
    return TestClient(app)


def _submit(client: TestClient, name: str = "test", daemon: bool = False) -> dict:
    resp = client.post("/api/commands", json={
        "phone_command": {
            "name": name,
            "steps": [{"argv": ["termux-battery-status"]}],
            "connections": [],
            "daemon": daemon,
        },
    })
    assert resp.status_code == 200
    return resp.json()


# --- POST /api/commands ---


def test_submit_returns_handle():
    client = _make_client()
    data = _submit(client)
    assert "command_id" in data
    assert data["status"] == "pending"
    assert "created_at" in data


# --- GET /api/commands ---


def test_list_empty():
    client = _make_client()
    resp = client.get("/api/commands")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_after_submit():
    client = _make_client()
    _submit(client)
    _submit(client)
    resp = client.get("/api/commands")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- GET /api/commands/{command_id} ---


def test_get_command():
    client = _make_client()
    handle = _submit(client)
    command_id = handle["command_id"]
    resp = client.get(f"/api/commands/{command_id}")
    assert resp.status_code == 200
    assert resp.json()["command_id"] == command_id


def test_get_command_not_found():
    client = _make_client()
    resp = client.get("/api/commands/no-such")
    assert resp.status_code == 404


# --- DELETE /api/commands/{command_id} ---


def test_cancel_command():
    client = _make_client()
    handle = _submit(client)
    command_id = handle["command_id"]
    resp = client.delete(f"/api/commands/{command_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_command_not_found():
    client = _make_client()
    resp = client.delete("/api/commands/no-such")
    assert resp.status_code == 404
