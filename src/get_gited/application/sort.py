"""Workspace row sort modes. Pure ranking; filesystem work stays in adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from get_gited.adapters.fs import directory_size, project_mtime
from get_gited.application.status import ProjectStatusRow

SYNC_RANK: dict[str, int] = {
    "SYNCED": 0,
    "LOCAL_AHEAD": 1,
    "REMOTE_AHEAD": 2,
    "DIVERGED": 3,
    "NO_REMOTE": 4,
    "LOCAL_ONLY": 5,
    "REMOTE_ONLY": 6,
    "NO_GIT": 7,
    "BLOCKED": 8,
    "ERROR": 9,
}


class SortMode(StrEnum):
    SCAN = "scan"
    MTIME = "mtime"
    SYNC = "sync"
    PRESENCE = "presence"
    SIZE = "size"


@dataclass(frozen=True, slots=True)
class SortParse:
    mode: SortMode | None = None
    cancel: bool = False
    error: str = ""


def format_sort_menu() -> str:
    return "\n".join(
        [
            "Sort by:",
            "  1  Last modified (newest first)",
            "  2  Sync status",
            "  3  Local / Git presence",
            "  4  Size (largest first)",
            "",
            "Enter a number, or Enter to keep scan order, q to go back.",
        ]
    )


def sort_mode_label(mode: SortMode) -> str:
    labels = {
        SortMode.SCAN: "scan order",
        SortMode.MTIME: "last modified",
        SortMode.SYNC: "sync status",
        SortMode.PRESENCE: "local / Git presence",
        SortMode.SIZE: "size",
    }
    return labels[mode]


def parse_sort_mode(raw: str) -> SortMode | None:
    text = raw.strip().lower()
    aliases: dict[str, SortMode] = {
        "scan": SortMode.SCAN,
        "0": SortMode.SCAN,
        "1": SortMode.MTIME,
        "mtime": SortMode.MTIME,
        "date": SortMode.MTIME,
        "modified": SortMode.MTIME,
        "2": SortMode.SYNC,
        "sync": SortMode.SYNC,
        "status": SortMode.SYNC,
        "3": SortMode.PRESENCE,
        "presence": SortMode.PRESENCE,
        "local": SortMode.PRESENCE,
        "git": SortMode.PRESENCE,
        "4": SortMode.SIZE,
        "size": SortMode.SIZE,
        "files": SortMode.SIZE,
        "volume": SortMode.SIZE,
    }
    return aliases.get(text)


def parse_sort_input(raw: str) -> SortParse:
    text = raw.strip().lower()
    if text == "":
        return SortParse(mode=SortMode.SCAN)
    if text in {"q", "quit", "cancel"}:
        return SortParse(cancel=True)
    mode = parse_sort_mode(text)
    if mode is None:
        return SortParse(
            error="Enter 1-4, [Enter] for scan order, q to go back, or e to exit."
        )
    return SortParse(mode=mode)


def presence_rank(row: ProjectStatusRow) -> int:
    if row.is_remote_only:
        return 2
    if row.project is not None and row.project.has_git_dir:
        return 0
    if row.path is not None:
        return 1
    return 3


def sort_rows(
    rows: Sequence[ProjectStatusRow],
    mode: SortMode,
) -> list[ProjectStatusRow]:
    items = list(rows)
    if mode is SortMode.SCAN:
        return items

    def name_key(row: ProjectStatusRow) -> str:
        return row.name.casefold()

    if mode is SortMode.SYNC:
        items.sort(
            key=lambda row: (SYNC_RANK.get(row.state.primary, 99), name_key(row))
        )
        return items

    if mode is SortMode.PRESENCE:
        items.sort(key=lambda row: (presence_rank(row), name_key(row)))
        return items

    if mode is SortMode.MTIME:
        items.sort(
            key=lambda row: (
                -(_row_mtime(row)),
                name_key(row),
            )
        )
        return items

    items.sort(
        key=lambda row: (
            -(_row_size(row)),
            name_key(row),
        )
    )
    return items


def _row_mtime(row: ProjectStatusRow) -> float:
    if row.path is None:
        return 0.0
    return project_mtime(row.path)


def _row_size(row: ProjectStatusRow) -> int:
    if row.path is None:
        return 0
    return directory_size(row.path)
