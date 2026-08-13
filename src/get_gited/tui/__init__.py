"""Textual workspace TUI."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static

from get_gited.adapters.command import (
    CommandRequest,
    CommandRunner,
    SubprocessCommandRunner,
)
from get_gited.adapters.config import append_ignore_path, load_config
from get_gited.application.status import ProjectStatusRow, collect_workspace_status
from get_gited.domain.matching import MatchConfidence


class WorkspaceApp(App[None]):
    """Keyboard-first workspace table."""

    TITLE = "Get Gited"
    SUB_TITLE = "SIMPLE. SAFE. SYNCED."

    CSS = """
    Screen { layout: vertical; background: #0f1419; }
    Header { background: #1a2330; color: #e8eef5; text-style: bold; }
    Footer { background: #1a2330; }
    #summary { height: 3; padding: 0 1; color: #9ecbff; }
    #details { height: 8; padding: 0 1; border-top: solid #3d8bfd; color: #c5d0dc; }
    DataTable { height: 1fr; }
    DataTable > .datatable--header { text-style: bold; color: #7dd3c7; }
    DataTable > .datatable--cursor { background: #1e3a5f; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("space", "toggle_select", "Select"),
        Binding("enter", "show_details", "Details"),
        Binding("f", "cycle_filter", "Filter"),
        Binding("o", "open_github", "Open GitHub"),
        Binding("i", "ignore_once", "Ignore once"),
        Binding("I", "ignore_always", "Ignore always"),
        Binding("s", "sync_preview", "Sync preview"),
        Binding("escape", "clear_details", "Back"),
    ]

    def __init__(
        self,
        roots: list[Path] | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        super().__init__()
        self._roots = roots
        self._runner = runner or SubprocessCommandRunner()
        self._rows: list[ProjectStatusRow] = []
        self._visible: list[ProjectStatusRow] = []
        self._selected: set[str] = set()
        self._ignored_once: set[str] = set()
        self._filter_mode = "actionable"  # all | actionable | warnings

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading workspace…", id="summary")
        yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
        yield Static("Select a project and press Enter for details.", id="details")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Sel", "Project", "Local", "GitHub", "Status")
        self.action_refresh()

    def action_refresh(self) -> None:
        config = load_config()
        self._rows = collect_workspace_status(
            self._runner,
            self._roots,
            config=config,
            include_github=True,
        )
        self._apply_filter()

    def action_cycle_filter(self) -> None:
        order = ["actionable", "warnings", "all"]
        idx = order.index(self._filter_mode)
        self._filter_mode = order[(idx + 1) % len(order)]
        self._apply_filter()

    def action_toggle_select(self) -> None:
        row = self._current_row()
        if row is None:
            return
        key = _row_key(row)
        if key in self._selected:
            self._selected.remove(key)
        else:
            self._selected.add(key)
        self._render_table()

    def action_show_details(self) -> None:
        row = self._current_row()
        if row is None:
            return
        details = self.query_one("#details", Static)
        path = str(row.path) if row.path else "(remote only)"
        nwo = row.match.nwo or "—"
        branch = row.facts.branch if row.facts else "—"
        ahead = row.state.ahead
        behind = row.state.behind
        dirty = (
            "dirty"
            if row.facts and not row.facts.working_tree.clean
            else "clean"
            if row.facts
            else "—"
        )
        details.update(
            f"{row.name}\n"
            f"Path: {path}\n"
            f"GitHub: {nwo} ({row.match.confidence})\n"
            f"Branch: {branch}\n"
            f"Status: {row.state.primary}  ahead={ahead} behind={behind}\n"
            f"Working tree: {dirty}\n"
            f"Keys: Space select · O open · i ignore once · I ignore always · F filter"
        )

    def action_sync_preview(self) -> None:
        from get_gited.application.planner import format_plan_preview, plan_operations

        rows = self._visible
        if self._selected:
            selected_rows = [r for r in self._rows if _row_key(r) in self._selected]
            if selected_rows:
                rows = selected_rows
        ops = plan_operations(rows)
        preview = format_plan_preview(ops)
        self.query_one("#details", Static).update(preview[:2000])
        self.notify("Dry-run preview (no changes)")

    def action_clear_details(self) -> None:
        self.query_one("#details", Static).update(
            "Select a project and press Enter for details."
        )

    def action_open_github(self) -> None:
        row = self._current_row()
        if row is None or not row.match.nwo:
            self.notify("No GitHub match", severity="warning")
            return
        if row.match.confidence == MatchConfidence.NAME_HINT:
            self.notify(
                "Name hint only — not opening automatically", severity="warning"
            )
            return
        result = self._runner.run(
            CommandRequest(argv=["gh", "repo", "view", row.match.nwo, "--web"])
        )
        if result.exit_code != 0:
            self.notify("Failed to open GitHub", severity="error")
        else:
            self.notify(f"Opened {row.match.nwo}")

    def action_ignore_once(self) -> None:
        row = self._current_row()
        if row is None or row.path is None:
            self.notify("Nothing to ignore", severity="warning")
            return
        self._ignored_once.add(str(row.path))
        self._apply_filter()
        self.notify(f"Ignored once: {row.name}")

    def action_ignore_always(self) -> None:
        row = self._current_row()
        if row is None or row.path is None:
            self.notify("Nothing to ignore", severity="warning")
            return
        append_ignore_path(row.path)
        self._ignored_once.add(str(row.path))
        self.action_refresh()
        self.notify(f"Always ignore: {row.name}")

    def _apply_filter(self) -> None:
        visible: list[ProjectStatusRow] = []
        for row in self._rows:
            if row.path and str(row.path) in self._ignored_once:
                continue
            primary = row.state.primary
            if self._filter_mode == "actionable":
                if primary in {"SYNCED"} and "UNCOMMITTED" not in {
                    f.value for f in row.state.flags
                }:
                    continue
            elif (
                self._filter_mode == "warnings"
                and primary
                not in {
                    "BLOCKED",
                    "DIVERGED",
                    "ERROR",
                }
                and "UNCOMMITTED" not in {f.value for f in row.state.flags}
            ):
                continue
            visible.append(row)
        self._visible = visible
        self._render_table()
        synced = sum(1 for r in self._rows if r.state.primary == "SYNCED")
        actionable = len(self._rows) - synced
        summary = self.query_one("#summary", Static)
        summary.update(
            f"Projects: {len(self._rows)} · Synced: {synced} · "
            f"Other: {actionable} · Filter: {self._filter_mode} · "
            f"Selected: {len(self._selected)}"
        )

    def _render_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for row in self._visible:
            key = _row_key(row)
            sel = "[x]" if key in self._selected else "[ ]"
            local = "no" if row.is_remote_only else "yes"
            table.add_row(
                sel,
                row.name,
                local,
                row.github_label,
                row.state.primary,
                key=key,
            )

    def _current_row(self) -> ProjectStatusRow | None:
        table = self.query_one(DataTable)
        if table.cursor_row is None or table.cursor_row >= len(self._visible):
            return None
        return self._visible[table.cursor_row]


def _row_key(row: ProjectStatusRow) -> str:
    if row.path is not None:
        return str(row.path)
    return f"remote:{row.match.nwo or row.name}"


def run_tui(roots: list[Path] | None = None) -> None:
    WorkspaceApp(roots=roots).run()
