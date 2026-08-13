"""Scan application and CLI tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from get_gited.adapters.config import (
    AppConfig,
    IgnoreConfig,
    ScanConfig,
    WorkspaceRootConfig,
)
from get_gited.application.scan import format_scan_table, scan_projects
from get_gited.cli import app

runner = CliRunner()


def test_scan_uses_config_roots(tmp_path: Path) -> None:
    project = tmp_path / "Demo"
    (project / ".git").mkdir(parents=True)
    config = AppConfig(
        roots=(WorkspaceRootConfig(path=tmp_path),),
        scan=ScanConfig(max_depth=4),
        ignore=IgnoreConfig(),
        source_path=tmp_path / "config.toml",
        exists=True,
    )
    projects = scan_projects(None, config=config)
    assert any(p.name == "Demo" for p in projects)


def test_cli_roots_override_config(tmp_path: Path) -> None:
    wanted = tmp_path / "wanted"
    other = tmp_path / "other"
    (wanted / ".git").mkdir(parents=True)
    (other / ".git").mkdir(parents=True)
    config = AppConfig(
        roots=(WorkspaceRootConfig(path=other),),
        scan=ScanConfig(max_depth=4),
        exists=True,
    )
    projects = scan_projects([wanted], config=config)
    assert len(projects) == 1
    assert projects[0].path == wanted


def test_format_scan_table_empty() -> None:
    assert format_scan_table([]) == "No projects found."


def test_scan_cli(tmp_path: Path) -> None:
    project = tmp_path / "CLIProj"
    (project / ".git").mkdir(parents=True)
    result = runner.invoke(app, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    assert "CLIProj" in result.stdout
    assert "Projects: 1" in result.stdout


def test_scan_cli_no_roots() -> None:
    result = runner.invoke(app, ["scan"])
    assert result.exit_code == 1
    assert "No workspace roots" in result.stdout


def test_status_cli(tmp_path: Path) -> None:
    project = tmp_path / "StatProj"
    (project / ".git").mkdir(parents=True)
    # Bare .git dir without commits still discovered; inspect may ERROR.
    result = runner.invoke(app, ["status", str(tmp_path)])
    assert result.exit_code == 0
    assert "StatProj" in result.stdout
    assert "GitHub" in result.stdout
