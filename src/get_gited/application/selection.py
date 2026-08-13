"""Interactive numbered project picker (CLI). Domain rules stay in the planner."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from get_gited.application.brand import (
    UiTheme,
    content_width,
    format_frame,
    next_ui_theme,
    parse_ui_theme,
)
from get_gited.application.planner import suggest_operation
from get_gited.application.sort import (
    SortMode,
    parse_sort_input,
    parse_sort_mode,
    sort_mode_label,
    sort_rows,
)
from get_gited.application.status import ProjectStatusRow, status_label
from get_gited.application.summaries import row_about, row_date
from get_gited.domain.operations import OperationType


class PickAction(StrEnum):
    DONE = "done"
    BACK = "back"
    QUIT = "quit"
    TOGGLE = "toggle"
    SORT = "sort"
    THEME = "theme"
    INFER = "infer"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PickParse:
    action: PickAction
    number: int | None = None
    sort_mode: SortMode | None = None
    theme: UiTheme | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class PickerOutcome:
    status: str  # selected | quit
    rows: tuple[ProjectStatusRow, ...]
    sort_mode: SortMode
    selected_keys: frozenset[str]
    infer: bool = False
    theme: UiTheme = UiTheme.MINIMAL


def row_key(row: ProjectStatusRow) -> str:
    if row.path is not None:
        return str(row.path)
    return f"remote:{row.match.nwo or row.name}"


def publish_candidates(rows: Sequence[ProjectStatusRow]) -> list[ProjectStatusRow]:
    """Local Git projects the planner would publish (not clone/push/skip)."""

    return [row for row in rows if suggest_operation(row).type == OperationType.PUBLISH]


def parse_inline_sort(raw: str) -> SortMode | None:
    """``s1``–``s4`` (optional space) while the project list is open."""

    text = raw.strip().lower()
    if len(text) < 2 or not text.startswith("s"):
        return None
    return parse_sort_mode(text[1:].strip())


def parse_pick_input(raw: str, count: int) -> PickParse:
    text = raw.strip().lower()
    if text == "":
        return PickParse(action=PickAction.DONE)
    if text in {"q", "back"}:
        return PickParse(action=PickAction.BACK)
    if text in {"exit", "x", "e"}:
        return PickParse(action=PickAction.QUIT)
    inline = parse_inline_sort(text)
    if inline is not None:
        return PickParse(action=PickAction.SORT, sort_mode=inline)
    if text in {"u", "ui"}:
        return PickParse(action=PickAction.THEME)
    if text.startswith("u") and len(text) >= 2:
        themed = parse_ui_theme(text[1:].strip())
        if themed is not None:
            return PickParse(action=PickAction.THEME, theme=themed)
    if text in {"i", "infer", "guess"}:
        return PickParse(action=PickAction.INFER)
    if not text.isdigit():
        return PickParse(
            action=PickAction.ERROR,
            message=(
                "Number to toggle, s1-s4 to sort, u1-u5 for UI, "
                "Enter to continue, q back."
            ),
        )
    number = int(text)
    if number < 1 or number > count:
        return PickParse(
            action=PickAction.ERROR,
            message=f"Enter a project number from 1 to {count}.",
        )
    return PickParse(action=PickAction.TOGGLE, number=number)


def toggle_selection(selected: set[int], number: int) -> None:
    if number in selected:
        selected.remove(number)
    else:
        selected.add(number)


def selected_rows(
    rows: Sequence[ProjectStatusRow],
    selected: set[int],
) -> list[ProjectStatusRow]:
    """Return marked rows in original table order (1-based indices)."""

    return [rows[index - 1] for index in sorted(selected)]


def selected_indices_for_keys(
    rows: Sequence[ProjectStatusRow],
    keys: set[str],
) -> set[int]:
    return {index + 1 for index, row in enumerate(rows) if row_key(row) in keys}


ABOUT_HEADER_LOCKED = "About (gg acpt --help)"
ABOUT_HEADER_OPEN = "About"
_MIN_ABOUT = 12
_GAPS = 12  # two spaces between each of the seven columns


def format_pick_table(
    rows: Sequence[ProjectStatusRow],
    selected: set[int],
    *,
    numbers: Sequence[int] | None = None,
    infer: bool = False,
    width: int = 120,
    layout: str = "table",
) -> str:
    if not rows:
        return "No projects found."

    indices = list(numbers) if numbers is not None else list(range(1, len(rows) + 1))
    if len(indices) != len(rows):
        raise ValueError("numbers length must match rows")

    if layout == "cards":
        return _format_pick_cards(rows, selected, indices, infer=infer, width=width)

    dates = [row_date(row) for row in rows]
    abouts = [row_about(row, infer=infer) for row in rows]
    names = [row.name for row in rows]
    githubs = [row.github_label for row in rows]
    statuses = [status_label(row) for row in rows]
    num_w, name_w, github_w, status_w, date_w, about_w = _table_widths(
        indices, names, githubs, statuses, dates, width
    )
    about_header = about_column_header(infer, about_w)

    header = (
        f"{'#':>{num_w}}  {'Sel':<3}  {'Project':<{name_w}}  "
        f"{'GitHub':<{github_w}}  {'Status':<{status_w}}  "
        f"{'Date':<{date_w}}  {about_header:<{about_w}}"
    )
    rule = (
        f"{'-' * num_w}  {'---'}  {'-' * name_w}  {'-' * github_w}  "
        f"{'-' * status_w}  {'-' * date_w}  {'-' * about_w}"
    )
    lines = [header, rule]
    for number, row, date, about in zip(indices, rows, dates, abouts, strict=True):
        mark = "[*]" if number in selected else "[ ]"
        lines.append(
            f"{number:>{num_w}}  {mark:<3}  "
            f"{clip(row.name, name_w):<{name_w}}  "
            f"{clip(row.github_label, github_w):<{github_w}}  "
            f"{clip(status_label(row), status_w):<{status_w}}  "
            f"{date:<{date_w}}  "
            f"{clip(about, about_w):<{about_w}}"
        )
    lines.append("")
    lines.append(f"Selected: {len(selected)} / {len(indices)}")
    return "\n".join(lines)


def _table_widths(
    indices: Sequence[int],
    names: Sequence[str],
    githubs: Sequence[str],
    statuses: Sequence[str],
    dates: Sequence[str],
    width: int,
) -> tuple[int, int, int, int, int, int]:
    num_w = max(len("#"), max(len(str(n)) for n in indices))
    date_w = max(len("Date"), max(len(value) for value in dates))
    flex = max(40, width - num_w - 3 - date_w - _GAPS)
    name_w = min(24, max(len("Project"), max(len(name) for name in names)))
    github_w = min(22, max(len("GitHub"), max(len(label) for label in githubs)))
    status_w = min(20, max(len("Status"), max(len(label) for label in statuses)))
    about_w = flex - name_w - github_w - status_w
    if about_w < _MIN_ABOUT:
        deficit = _MIN_ABOUT - about_w
        for current, floor in (
            ("github", 10),
            ("name", 10),
            ("status", 8),
        ):
            if deficit <= 0:
                break
            if current == "github" and github_w > floor:
                cut = min(deficit, github_w - floor)
                github_w -= cut
                deficit -= cut
            elif current == "name" and name_w > floor:
                cut = min(deficit, name_w - floor)
                name_w -= cut
                deficit -= cut
            elif current == "status" and status_w > floor:
                cut = min(deficit, status_w - floor)
                status_w -= cut
                deficit -= cut
        about_w = flex - name_w - github_w - status_w
    about_w = max(4, about_w)
    return num_w, name_w, github_w, status_w, date_w, about_w


def _format_pick_cards(
    rows: Sequence[ProjectStatusRow],
    selected: set[int],
    indices: Sequence[int],
    *,
    infer: bool,
    width: int,
) -> str:
    lines: list[str] = []
    for number, row in zip(indices, rows, strict=True):
        mark = "[*]" if number in selected else "[ ]"
        top = f"{number:>3}  {mark}  {row.name}   {status_label(row)}   {row_date(row)}"
        about = row_about(row, infer=infer)
        github = row.github_label
        bottom = f"       {github}  ·  {about}"
        lines.append(clip(top, width))
        lines.append(clip(bottom, width))
        lines.append("")
    lines.append(f"Selected: {len(selected)} / {len(indices)}")
    return "\n".join(lines)


def about_column_header(infer: bool, about_width: int = 40) -> str:
    if infer or about_width < len(ABOUT_HEADER_LOCKED):
        return ABOUT_HEADER_OPEN
    return ABOUT_HEADER_LOCKED


def clip(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"


def format_sort_screen(
    current: SortMode,
    hint: str = "",
    *,
    theme: UiTheme = UiTheme.MINIMAL,
    width: int = 120,
) -> str:
    marker = {mode: " " for mode in SortMode}
    marker[current] = "*"
    body = "\n".join(
        [
            f" {marker[SortMode.MTIME]} 1  Last modified",
            f" {marker[SortMode.SYNC]} 2  Sync status",
            f" {marker[SortMode.PRESENCE]} 3  Local / Git presence",
            f" {marker[SortMode.SIZE]} 4  Size",
            f" {marker[SortMode.SCAN]} Enter  scan order",
        ]
    )
    return format_frame(
        section="sort",
        body=body,
        footer="q  back    e  exit    u1-u5  ui",
        hint=hint,
        theme=theme,
        width=width,
    )


def format_pick_screen(
    rows: Sequence[ProjectStatusRow],
    keys: set[str],
    mode: SortMode,
    hint: str = "",
    *,
    infer: bool = False,
    theme: UiTheme = UiTheme.MINIMAL,
    width: int = 120,
) -> str:
    indices = selected_indices_for_keys(rows, keys)
    inner = content_width(theme, width)
    layout = "cards" if theme is UiTheme.CARDS else "table"
    table = format_pick_table(rows, indices, infer=infer, width=inner, layout=layout)
    guess = "on" if infer else "off"
    footer = "\n".join(
        [
            "number  toggle   s1-s4  sort   u1-u5  ui   [Enter]  continue",
            "q  back   e  exit   gg acpt --help  About consent",
        ]
    )
    return format_frame(
        section=f"{sort_mode_label(mode)}  ·  {theme}  ·  guess {guess}",
        body=table,
        footer=footer,
        hint=hint,
        theme=theme,
        width=width,
    )


def format_preview_screen(
    preview: str,
    count: int,
    *,
    theme: UiTheme = UiTheme.MINIMAL,
    width: int = 120,
) -> str:
    body = "\n".join(
        line for line in preview.splitlines() if not line.startswith("Dry-run:")
    ).rstrip()
    return format_frame(
        section=f"preview  ·  {count} selected",
        body=body,
        footer="\n".join(
            [
                "[Enter] - execute",
                "q - back",
                "e - exit",
            ]
        ),
        theme=theme,
        width=width,
    )


def parse_preview_input(raw: str) -> str:
    text = raw.strip().lower()
    if text in {"", "y", "yes", "enter"}:
        return "execute"
    if text in {"q", "n", "no", "back"}:
        return "back"
    if text in {"e", "exit", "x"}:
        return "quit"
    return "error"


def run_workspace_picker(
    rows: Sequence[ProjectStatusRow],
    *,
    read_line: Callable[[str], str],
    show: Callable[[str], None],
    sort_mode: SortMode | None = None,
    ask_sort: bool = True,
    selected_keys: set[str] | None = None,
    infer: bool = False,
    theme: UiTheme = UiTheme.MINIMAL,
    on_theme: Callable[[UiTheme], None] | None = None,
    columns: Callable[[], int] | None = None,
) -> PickerOutcome:
    """Sort menu and numbered [*] picker. ``q`` returns to the previous screen."""

    original = list(rows)
    chosen = sort_mode if sort_mode is not None else SortMode.SCAN
    keys: set[str] = set(selected_keys or ())
    screen = "sort" if ask_sort else "pick"
    visited_pick = not ask_sort
    hint = ""
    guess = infer
    look = theme

    def width() -> int:
        return columns() if columns is not None else 120

    def finish(status: str, picked: tuple[ProjectStatusRow, ...] = ()) -> PickerOutcome:
        return PickerOutcome(status, picked, chosen, frozenset(keys), guess, look)

    if not original:
        show("No projects found.")
        return finish("quit")

    while True:
        ordered = sort_rows(original, chosen)
        cols = width()
        if screen == "sort":
            show(format_sort_screen(chosen, hint, theme=look, width=cols))
            hint = ""
            raw = read_line("Sort: ")
            stripped = raw.strip().lower()
            if stripped in {"exit", "x", "e"}:
                return finish("quit")
            theme_pick = parse_pick_input(raw, 1)
            if theme_pick.action is PickAction.THEME:
                look = (
                    theme_pick.theme
                    if theme_pick.theme is not None
                    else next_ui_theme(look)
                )
                if on_theme is not None:
                    on_theme(look)
                hint = f"UI: {look}"
                continue
            parsed = parse_sort_input(raw)
            if parsed.cancel:
                if visited_pick:
                    screen = "pick"
                else:
                    hint = "Choose 1-4, [Enter] to continue, or e to exit."
                continue
            if parsed.error:
                hint = parsed.error
                continue
            if parsed.mode is not None:
                chosen = parsed.mode
            screen = "pick"
            visited_pick = True
            continue

        show(
            format_pick_screen(
                ordered, keys, chosen, hint, infer=guess, theme=look, width=cols
            )
        )
        hint = ""
        raw = read_line("Number: ")
        pick = parse_pick_input(raw, len(ordered))
        if pick.action is PickAction.QUIT:
            return finish("quit")
        if pick.action is PickAction.BACK:
            screen = "sort"
            continue
        if pick.action is PickAction.SORT:
            assert pick.sort_mode is not None
            chosen = pick.sort_mode
            continue
        if pick.action is PickAction.THEME:
            look = pick.theme if pick.theme is not None else next_ui_theme(look)
            if on_theme is not None:
                on_theme(look)
            hint = f"UI: {look}"
            continue
        if pick.action is PickAction.INFER:
            if guess:
                hint = "File guesses are on. Revoke with: gg acpt --off"
            else:
                hint = "File guesses are off. See: gg acpt --help"
            continue
        if pick.action is PickAction.DONE:
            if not keys:
                hint = "Select at least one project, or q to go back."
                continue
            picked = tuple(row for row in ordered if row_key(row) in keys)
            return finish("selected", picked)
        if pick.action is PickAction.ERROR:
            hint = pick.message
            continue
        assert pick.number is not None
        key = row_key(ordered[pick.number - 1])
        if key in keys:
            keys.remove(key)
        else:
            keys.add(key)
