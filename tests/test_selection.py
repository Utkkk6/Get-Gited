"""Numbered [*] picker, sort, and About-column tests."""

from __future__ import annotations

import os
import time
from pathlib import Path

from get_gited.adapters.fs import LocalProject, directory_size
from get_gited.application.brand import UiTheme
from get_gited.application.planner import suggest_operation
from get_gited.application.selection import (
    format_pick_screen,
    format_pick_table,
    format_preview_screen,
    format_sort_screen,
    parse_pick_input,
    parse_preview_input,
    publish_candidates,
    run_workspace_picker,
    selected_rows,
    toggle_selection,
)
from get_gited.application.sort import (
    SortMode,
    parse_sort_input,
    parse_sort_mode,
    sort_rows,
)
from get_gited.application.status import ProjectStatusRow
from get_gited.application.summaries import project_about, scrub_public_text
from get_gited.domain.matching import MatchConfidence, ProjectMatch
from get_gited.domain.models import ProjectFlag, ProjectState
from get_gited.domain.operations import OperationType


def _row(
    name: str,
    path: Path | None,
    primary: str,
    *,
    has_git: bool = True,
    remote_only: bool = False,
) -> ProjectStatusRow:
    project = None
    if path is not None:
        project = LocalProject(path, name, has_git, ())
    return ProjectStatusRow(
        name=name,
        path=path,
        project=project,
        facts=None,
        state=ProjectState(
            sync=None,
            flags=frozenset(
                {ProjectFlag.LOCAL_ONLY} if primary == "LOCAL_ONLY" else ()
            ),
            primary=primary,
        ),
        match=ProjectMatch(confidence=MatchConfidence.NONE, nwo=None, repo=None),
        github_label="—",
        is_remote_only=remote_only,
    )


def test_pick_table_marks_star_and_columns() -> None:
    rows = [
        _row("Alpha", Path("a"), "LOCAL_ONLY"),
        _row("Beta", Path("b"), "NO_REMOTE"),
    ]
    text = format_pick_table(rows, {2})
    header = text.splitlines()[0]
    assert "Date" in header
    assert "About (gg acpt --help)" in header
    granted = format_pick_table(rows, {2}, infer=True)
    assert "About (gg acpt --help)" not in granted.splitlines()[0]
    assert "About" in granted.splitlines()[0]
    starred = [line for line in text.splitlines() if "Beta" in line]
    empty = [line for line in text.splitlines() if "Alpha" in line]
    assert starred and "[*]" in starred[0]
    assert empty and "[ ]" in empty[0]


def test_toggle_and_selected_in_original_order() -> None:
    rows = [
        _row("A", Path("a"), "LOCAL_ONLY"),
        _row("B", Path("b"), "LOCAL_ONLY"),
        _row("C", Path("c"), "LOCAL_ONLY"),
    ]
    selected: set[int] = set()
    toggle_selection(selected, 3)
    toggle_selection(selected, 1)
    picked = selected_rows(rows, selected)
    assert [row.name for row in picked] == ["A", "C"]
    toggle_selection(selected, 3)
    assert selected == {1}


def test_parse_pick_input() -> None:
    assert parse_pick_input("", 3).action.value == "done"
    assert parse_pick_input("q", 3).action.value == "back"
    assert parse_pick_input("exit", 3).action.value == "quit"
    assert parse_pick_input("e", 3).action.value == "quit"
    parsed = parse_pick_input("2", 3)
    assert parsed.action.value == "toggle"
    assert parsed.number == 2
    sort = parse_pick_input("s2", 3)
    assert sort.action.value == "sort"
    assert sort.sort_mode is SortMode.SYNC
    assert parse_pick_input("s 4", 3).sort_mode is SortMode.SIZE
    assert parse_pick_input("i", 3).action.value == "infer"
    theme = parse_pick_input("u2", 3)
    assert theme.action.value == "theme"
    assert theme.theme is UiTheme.MINIMAL
    assert parse_pick_input("u", 3).action.value == "theme"
    assert parse_pick_input("9", 3).action.value == "error"


def test_parse_preview_input() -> None:
    assert parse_preview_input("") == "execute"
    assert parse_preview_input("q") == "back"
    assert parse_preview_input("e") == "quit"
    assert parse_preview_input("exit") == "quit"


def test_preview_footer_keys() -> None:
    text = format_preview_screen("push demo", 1)
    assert "[Enter] - execute" in text
    assert "q - back" in text
    assert "e - exit" in text
    assert "Enter  execute" not in text


def test_workspace_picker_toggle_and_finish() -> None:
    rows = [
        _row("A", Path("a"), "LOCAL_ONLY"),
        _row("B", Path("b"), "LOCAL_ONLY"),
        _row("C", Path("c"), "LOCAL_ONLY"),
    ]
    answers = iter(["", "2", "1", ""])
    frames: list[str] = []
    outcome = run_workspace_picker(
        rows,
        read_line=lambda _prompt: next(answers),
        show=frames.append,
        ask_sort=True,
    )
    assert outcome.status == "selected"
    assert [row.name for row in outcome.rows] == ["A", "B"]
    last = frames[-1]
    assert "Sel" in last
    assert "[*]" in last
    assert last.count("SIMPLE. SAFE. SYNCED.") == 1


def test_q_returns_to_sort_then_continues() -> None:
    rows = [
        _row("Local", Path("a"), "LOCAL_ONLY"),
        _row("Synced", Path("b"), "SYNCED"),
    ]
    answers = iter(["", "q", "2", "1", ""])
    frames: list[str] = []
    outcome = run_workspace_picker(
        rows,
        read_line=lambda _prompt: next(answers),
        show=frames.append,
        ask_sort=True,
    )
    assert outcome.status == "selected"
    assert [row.name for row in outcome.rows] == ["Synced"]
    assert any("sort" in frame and "SIMPLE. SAFE. SYNCED." in frame for frame in frames)


def test_q_on_first_sort_does_not_quit() -> None:
    rows = [_row("A", Path("a"), "LOCAL_ONLY")]
    answers = iter(["q", "exit"])
    outcome = run_workspace_picker(
        rows,
        read_line=lambda _prompt: next(answers),
        show=lambda _text: None,
        ask_sort=True,
    )
    assert outcome.status == "quit"


def test_inline_sort_keeps_selection_by_identity() -> None:
    rows = [
        _row("Local", Path("a"), "LOCAL_ONLY"),
        _row("Synced", Path("b"), "SYNCED"),
    ]
    answers = iter(["", "1", "s2", ""])
    outcome = run_workspace_picker(
        rows,
        read_line=lambda _prompt: next(answers),
        show=lambda _text: None,
        ask_sort=True,
    )
    assert outcome.status == "selected"
    assert [row.name for row in outcome.rows] == ["Local"]


def test_empty_enter_without_selection_stays() -> None:
    rows = [_row("A", Path("a"), "LOCAL_ONLY")]
    answers = iter(["", "", "1", ""])
    frames: list[str] = []
    outcome = run_workspace_picker(
        rows,
        read_line=lambda _prompt: next(answers),
        show=frames.append,
        ask_sort=True,
    )
    assert outcome.status == "selected"
    assert any("Select at least one project" in frame for frame in frames)


def test_publish_candidates_skips_synced() -> None:
    rows = [
        _row("Local", Path("a"), "LOCAL_ONLY"),
        _row("Ok", Path("b"), "SYNCED"),
    ]
    candidates = publish_candidates(rows)
    assert [row.name for row in candidates] == ["Local"]
    assert suggest_operation(candidates[0]).type == OperationType.PUBLISH


def test_sort_by_sync_and_presence() -> None:
    rows = [
        _row("Zed", Path("z"), "LOCAL_ONLY", has_git=False),
        _row("Ann", Path("a"), "SYNCED"),
        _row("Remote", None, "REMOTE_ONLY", remote_only=True),
        _row("Gitty", Path("g"), "NO_REMOTE"),
    ]
    by_sync = sort_rows(rows, SortMode.SYNC)
    assert [row.name for row in by_sync] == ["Ann", "Gitty", "Zed", "Remote"]
    by_presence = sort_rows(rows, SortMode.PRESENCE)
    assert [row.name for row in by_presence] == ["Ann", "Gitty", "Zed", "Remote"]


def test_sort_by_mtime_and_size(tmp_path: Path) -> None:
    older = tmp_path / "older"
    newer = tmp_path / "newer"
    older.mkdir()
    newer.mkdir()
    (older / "small.txt").write_bytes(b"a")
    (newer / "big.txt").write_bytes(b"b" * 200)
    older_row = _row("older", older, "LOCAL_ONLY")
    newer_row = _row("newer", newer, "LOCAL_ONLY")
    assert directory_size(newer) > directory_size(older)

    now = time.time()
    os.utime(older, (now - 100, now - 100))
    os.utime(newer, (now, now))

    by_mtime = sort_rows([older_row, newer_row], SortMode.MTIME)
    assert [row.name for row in by_mtime] == ["newer", "older"]
    by_size = sort_rows([older_row, newer_row], SortMode.SIZE)
    assert [row.name for row in by_size] == ["newer", "older"]


def test_sort_screen_banner() -> None:
    text = format_sort_screen(SortMode.SCAN)
    assert "GET GITED" in text
    assert "SIMPLE. SAFE. SYNCED." in text
    assert "Last modified" in text
    assert "┌" not in text
    boxed = format_sort_screen(SortMode.SCAN, theme=UiTheme.FRAME)
    assert "┌" in boxed
    assert parse_sort_mode("mtime") is SortMode.MTIME
    assert parse_sort_input("").mode is SortMode.SCAN
    assert parse_sort_input("q").cancel is True
    assert parse_sort_input("nope").error


def test_pick_table_fits_width_and_keeps_about() -> None:
    rows = [
        _row("MT5_building_bot", Path("a"), "SYNCED (UNCOMMITTED)"),
    ]
    rows[0] = ProjectStatusRow(
        name=rows[0].name,
        path=rows[0].path,
        project=rows[0].project,
        facts=None,
        state=rows[0].state,
        match=rows[0].match,
        github_label="itmo-webdev/lab6_Yutkin_nikita",
        is_remote_only=False,
    )
    text = format_pick_table(rows, set(), width=100)
    header = text.splitlines()[0]
    assert "Ab..." not in header
    assert "About" in header
    for line in text.splitlines():
        if line.startswith("Selected") or line == "":
            continue
        assert len(line) <= 100


def test_five_ui_themes_are_distinct() -> None:
    rows = [_row("Alpha", Path("a"), "LOCAL_ONLY")]
    looks = {
        UiTheme.FRAME: format_pick_screen(
            rows, set(), SortMode.SCAN, theme=UiTheme.FRAME, width=120
        ),
        UiTheme.MINIMAL: format_pick_screen(
            rows, set(), SortMode.SCAN, theme=UiTheme.MINIMAL, width=120
        ),
        UiTheme.HUD: format_pick_screen(
            rows, set(), SortMode.SCAN, theme=UiTheme.HUD, width=120
        ),
        UiTheme.CARDS: format_pick_screen(
            rows, set(), SortMode.SCAN, theme=UiTheme.CARDS, width=120
        ),
        UiTheme.POSTER: format_pick_screen(
            rows, set(), SortMode.SCAN, theme=UiTheme.POSTER, width=120
        ),
    }
    assert "┌" in looks[UiTheme.FRAME]
    assert "╔" in looks[UiTheme.HUD]
    assert "┌" not in looks[UiTheme.MINIMAL]
    assert "╔" not in looks[UiTheme.MINIMAL]
    assert " · " in looks[UiTheme.CARDS]
    assert looks[UiTheme.POSTER].splitlines()[0] == "GET GITED"
    assert len(set(looks.values())) == 5


def test_picker_switches_theme_live() -> None:
    rows = [_row("A", Path("a"), "LOCAL_ONLY")]
    answers = iter(["", "u3", "1", ""])
    seen: list[UiTheme] = []
    frames: list[str] = []
    outcome = run_workspace_picker(
        rows,
        read_line=lambda _prompt: next(answers),
        show=frames.append,
        ask_sort=True,
        on_theme=seen.append,
    )
    assert outcome.status == "selected"
    assert outcome.theme is UiTheme.HUD
    assert seen == [UiTheme.HUD]
    assert any("╔" in frame for frame in frames)


def test_readme_excerpt_preferred_over_guess(tmp_path: Path) -> None:
    project = tmp_path / "Demo"
    project.mkdir()
    (project / "README.md").write_text(
        "# Demo\n\nOne workspace. All your Git repos.\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndescription = "Should not win"\n',
        encoding="utf-8",
    )
    about = project_about(project, infer=False)
    assert "One workspace" in about
    assert "Should not win" not in about


def test_missing_readme_is_dash_until_infer(tmp_path: Path) -> None:
    project = tmp_path / "Bare"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "bare"\ndescription = "A tiny CLI."\n',
        encoding="utf-8",
    )
    assert project_about(project, infer=False) == "—"
    assert project_about(project, infer=True) == "A tiny CLI."


def test_scrub_redacts_tokens_only() -> None:
    fake_pat = "ghp_" + ("a" * 20)
    text = scrub_public_text(f"Uses {fake_pat} and then ships.")
    assert "ghp_" not in text
    assert "[redacted]" in text
    assert "ships" in text
