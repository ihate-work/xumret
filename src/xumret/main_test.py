"""Tests for the `python -m xumret` CLI.

Imports the module as `xumret.__main__`. We avoid actually serving HTTP —
`single` is patched to skip `uvicorn.run` so we only exercise wiring.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from xumret.__main__ import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "single" in result.output
    assert "dev-openapi" in result.output


def test_single_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["single", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output
    assert "--dummy" in result.output


def test_single_dummy_wires_app(monkeypatch) -> None:
    captured_kwargs: dict[str, object] = {}
    captured_app: list[object] = []

    def fake_uvicorn_run(app, **kwargs) -> None:
        captured_app.append(app)
        captured_kwargs.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_uvicorn_run)
    runner = CliRunner()
    result = runner.invoke(cli, ["single", "--dummy", "--port", "0"])
    assert result.exit_code == 0, result.output
    assert captured_app
    assert captured_kwargs["port"] == 0


def test_single_real_executor_wires_app(monkeypatch) -> None:
    """The non-dummy branch imports LocalExecutor; just confirm it doesn't crash."""
    monkeypatch.setattr("uvicorn.run", lambda *a, **kw: None)
    runner = CliRunner()
    result = runner.invoke(cli, ["single", "--port", "0"])
    assert result.exit_code == 0, result.output


def test_dev_openapi_to_stdout() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["dev-openapi"])
    assert result.exit_code == 0, result.output
    # YAML output should mention the title we set.
    assert "xumret" in result.output


def test_dev_openapi_to_file(tmp_path: Path) -> None:
    out = tmp_path / "openapi.yaml"
    runner = CliRunner()
    result = runner.invoke(cli, ["dev-openapi", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()
    content = out.read_text()
    assert "openapi" in content.lower()
