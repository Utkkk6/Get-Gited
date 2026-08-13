"""TUI smoke tests."""

from __future__ import annotations

from get_gited.tui import WorkspaceApp


def test_workspace_app_constructs() -> None:
    app = WorkspaceApp(roots=[])
    assert app._filter_mode == "actionable"
    assert app.TITLE == "Get Gited"
    assert app.SUB_TITLE == "SIMPLE. SAFE. SYNCED."
