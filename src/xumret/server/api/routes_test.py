from __future__ import annotations

import time

from fastapi.testclient import TestClient

from xumret.executor.dummy_executor import DummyExecutor
from xumret.server.api.app import create_app
from xumret.single import SingleMain
from xumret.state.models import RunStateCompleted
from xumret.state.phone import PhoneState


def _make_client() -> tuple[TestClient, SingleMain, PhoneState]:
    state = PhoneState()
    service = SingleMain(executor=DummyExecutor(), state=state)
    app = create_app(service=service)
    return TestClient(app), service, state


def _submit(
    client: TestClient,
    *,
    name: str = "test",
    daemon: bool = False,
    slug: str | None = None,
    mutex_by_slug: bool = False,
    argv: list[str] | None = None,
):
    pc = {
        "name": name,
        "steps": [{"argv": argv or ["termux-toast", "hi"]}],
        "connections": [],
        "daemon": daemon,
        "run_option": {"slug": slug, "mutex_by_slug": mutex_by_slug},
    }
    resp = client.post("/api/runs", json={"phone_command": pc})
    return resp


def _force_terminal(state: PhoneState, slug: str) -> None:
    run = state.get(slug)
    assert run is not None
    run.emit(RunStateCompleted(slug=slug, at=time.time()))


# --- POST /api/runs ---


def test_submit_returns_record():
    client, _, _ = _make_client()
    resp = _submit(client)
    assert resp.status_code == 200
    data = resp.json()
    assert "slug" in data
    assert data["status"] in {"pending", "running", "completed"}
    assert "created_at" in data
    assert data["steps"]


def test_submit_with_slug_uses_it():
    client, _, _ = _make_client()
    data = _submit(client, slug="my-run").json()
    assert data["slug"] == "my-run"


def test_submit_idempotent_join_returns_same_slug():
    client, _, state = _make_client()
    a = _submit(client, slug="X").json()
    b = _submit(client, slug="X").json()
    assert a["slug"] == b["slug"] == "X"


def test_submit_409_when_terminal_unreaped():
    client, _, state = _make_client()
    _submit(client, slug="X")
    _force_terminal(state, "X")
    resp = _submit(client, slug="X")
    assert resp.status_code == 409


def test_submit_409_when_live_with_mutex():
    client, _, _ = _make_client()
    _submit(client, daemon=True, slug="X")
    resp = _submit(client, daemon=True, slug="X", mutex_by_slug=True)
    assert resp.status_code == 409


# --- GET /api/runs ---


def test_list_empty():
    client, _, _ = _make_client()
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_after_submit():
    client, _, _ = _make_client()
    _submit(client)
    _submit(client)
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- GET /api/runs/{slug} ---


def test_get_run():
    client, _, _ = _make_client()
    handle = _submit(client, slug="X").json()
    resp = client.get(f"/api/runs/{handle['slug']}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "X"


def test_get_run_not_found():
    client, _, _ = _make_client()
    resp = client.get("/api/runs/no-such")
    assert resp.status_code == 404


def test_get_run_slim_omits_transitions():
    client, _, state = _make_client()
    _submit(client, slug="X")
    _force_terminal(state, "X")
    resp = client.get("/api/runs/X").json()
    assert resp["transitions"] == []


# --- GET /api/runs/{slug}/state ---


def test_get_state_includes_transitions():
    client, _, state = _make_client()
    _submit(client, slug="X")
    _force_terminal(state, "X")
    resp = client.get("/api/runs/X/state").json()
    types = [t["type"] for t in resp["transitions"]]
    assert "created" in types
    assert "completed" in types


def test_get_state_not_found():
    client, _, _ = _make_client()
    resp = client.get("/api/runs/nope/state")
    assert resp.status_code == 404


# --- POST /api/runs/{slug}/stop ---


def test_stop_unknown_slug_404():
    client, _, _ = _make_client()
    resp = client.post("/api/runs/nope/stop")
    assert resp.status_code == 404


def test_stop_terminal_run_is_noop_success():
    client, _, state = _make_client()
    _submit(client, slug="X")
    _force_terminal(state, "X")
    resp = client.post("/api/runs/X/stop")
    assert resp.status_code == 200


def test_stop_idempotent():
    client, _, state = _make_client()
    _submit(client, slug="X")
    _force_terminal(state, "X")
    a = client.post("/api/runs/X/stop")
    b = client.post("/api/runs/X/stop")
    assert a.status_code == b.status_code == 200


# --- POST /api/runs/{slug}/reap ---


def test_reap_terminal_succeeds():
    client, _, state = _make_client()
    _submit(client, slug="X")
    _force_terminal(state, "X")
    resp = client.post("/api/runs/X/reap")
    assert resp.status_code == 200
    assert resp.json()["reaped"] is True
    # gone afterward
    assert client.get("/api/runs/X").status_code == 404


def test_reap_live_run_409():
    client, _, _ = _make_client()
    _submit(client, daemon=True, slug="X")
    resp = client.post("/api/runs/X/reap")
    assert resp.status_code == 409


def test_reap_unknown_slug_404():
    client, _, _ = _make_client()
    resp = client.post("/api/runs/nope/reap")
    assert resp.status_code == 404


def test_reap_then_reap_404():
    client, _, state = _make_client()
    _submit(client, slug="X")
    _force_terminal(state, "X")
    client.post("/api/runs/X/reap")
    second = client.post("/api/runs/X/reap")
    assert second.status_code == 404


# --- DELETE not exposed ---


def test_delete_not_allowed():
    client, _, _ = _make_client()
    handle = _submit(client, slug="X").json()
    resp = client.delete(f"/api/runs/{handle['slug']}")
    assert resp.status_code in (404, 405)
