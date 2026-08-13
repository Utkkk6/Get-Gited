"""CLI smoke tests via Typer CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from get_gited import __version__
from get_gited.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Get Gited" in result.stdout
    assert "doctor" in result.stdout


def test_short_help() -> None:
    result = runner.invoke(app, ["-h"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout
    assert "acpt" in result.stdout


def test_ui_help() -> None:
    result = runner.invoke(app, ["ui", "--help"])
    assert result.exit_code == 0
    assert "terminal look" in result.stdout.lower() or "UI" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_doctor_command_runs() -> None:
    # Uses the real runner; must not traceback even if git/gh missing.
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in {0, 1}
    assert "Python" in result.stdout
    assert "Git" in result.stdout
    assert "GitHub" in result.stdout
    assert "Config" in result.stdout
    assert "Traceback" not in result.stdout
