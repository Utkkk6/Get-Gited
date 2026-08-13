"""Parse the ``gg`` short-command argv. No I/O."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from get_gited.application.sort import SortMode, parse_sort_mode

KNOWN_COMMANDS: frozenset[str] = frozenset(
    {"doctor", "scan", "status", "sync", "acpt", "ui"}
)
PASSTHROUGH_FLAGS: frozenset[str] = frozenset({"--help", "--version", "-h"})


@dataclass(frozen=True, slots=True)
class GgRequest:
    mode: str  # passthrough | pick | prompt | error
    passthrough: tuple[str, ...] = ()
    roots: tuple[Path, ...] = ()
    sort: SortMode | None = None
    error: str = ""


def parse_gg_argv(argv: list[str], *, cwd: Path) -> GgRequest:
    """Resolve ``gg`` arguments into a passthrough, picker, or cwd prompt."""

    if argv and argv[0] in KNOWN_COMMANDS:
        return GgRequest(mode="passthrough", passthrough=tuple(argv))
    if argv and argv[0] in PASSTHROUGH_FLAGS:
        return GgRequest(mode="passthrough", passthrough=tuple(argv))

    yes = False
    sort: SortMode | None = None
    paths: list[Path] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"-y", "--yes"}:
            yes = True
            index += 1
            continue
        if token == "--sort":
            if index + 1 >= len(argv):
                return GgRequest(mode="error", error="--sort needs a value.")
            mode = parse_sort_mode(argv[index + 1])
            if mode is None:
                return GgRequest(
                    mode="error",
                    error="Unknown --sort value. Use mtime, sync, presence, or size.",
                )
            sort = mode
            index += 2
            continue
        if token.startswith("--sort="):
            mode = parse_sort_mode(token.split("=", 1)[1])
            if mode is None:
                return GgRequest(
                    mode="error",
                    error="Unknown --sort value. Use mtime, sync, presence, or size.",
                )
            sort = mode
            index += 1
            continue
        if token in KNOWN_COMMANDS or token in PASSTHROUGH_FLAGS:
            return GgRequest(mode="passthrough", passthrough=tuple(argv[index:]))
        paths.append(Path(token))
        index += 1

    if yes:
        roots = tuple(paths) if paths else (cwd,)
        return GgRequest(mode="pick", roots=roots, sort=sort)
    if paths:
        return GgRequest(mode="pick", roots=tuple(paths), sort=sort)
    return GgRequest(mode="prompt", roots=(cwd,), sort=sort)
