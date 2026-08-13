"""Filesystem discovery of local projects."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        ".next",
        ".idea",
        ".vscode",
        "__pycache__",
        "vendor",
        "target",
        "coverage",
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".cache",
        "eggs",
        ".eggs",
    }
)

MARKER_FILES: frozenset[str] = frozenset(
    {
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
        "poetry.lock",
        "Cargo.toml",
        "go.mod",
        "CMakeLists.txt",
        "Makefile",
        "Dockerfile",
        "docker-compose.yml",
        "compose.yml",
    }
)

MARKER_SUFFIXES: frozenset[str] = frozenset({".sln", ".csproj"})


@dataclass(frozen=True, slots=True)
class LocalProject:
    """A discovered project directory."""

    path: Path
    name: str
    has_git_dir: bool
    markers: tuple[str, ...]


def discover_projects(
    roots: list[Path],
    *,
    ignore_paths: list[Path] | None = None,
    max_depth: int = 6,
) -> list[LocalProject]:
    """Recursively find project candidates under ``roots``.

    Does not read file contents. Skips heavy directories and configured ignores.
    """

    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")

    ignore_resolved = _resolved_ignore_set(ignore_paths or [])
    found: dict[Path, LocalProject] = {}

    for root in roots:
        root_path = root.expanduser()
        try:
            root_resolved = root_path.resolve()
        except OSError:
            continue
        if not root_resolved.is_dir():
            continue
        if _is_ignored(root_resolved, ignore_resolved):
            continue
        _walk(
            root_resolved,
            depth=0,
            max_depth=max_depth,
            ignore_resolved=ignore_resolved,
            found=found,
        )

    return sorted(found.values(), key=lambda p: str(p.path).lower())


def _walk(
    directory: Path,
    *,
    depth: int,
    max_depth: int,
    ignore_resolved: set[Path],
    found: dict[Path, LocalProject],
) -> None:
    if depth > max_depth:
        return
    if _is_ignored(directory, ignore_resolved):
        return

    git_entry = directory / ".git"
    if git_entry.is_dir():
        found[directory] = LocalProject(
            path=directory,
            name=directory.name,
            has_git_dir=True,
            markers=(".git/",),
        )
        # Do not recurse into git project roots for nested projects.
        return

    # Submodule / worktree pointer: not a workspace project by itself.
    # Keep walking children only when this is not treated as a project root.
    markers = _collect_markers(directory)
    if markers and not git_entry.is_file():
        found[directory] = LocalProject(
            path=directory,
            name=directory.name,
            has_git_dir=False,
            markers=markers,
        )
        # Marker projects: still recurse? Architecture says if .git dir don't
        # recurse. For marker-only projects, nested projects can exist
        # (monorepo without root git). Continue walking.
    elif git_entry.is_file():
        # Not a project; continue into children of the parent walk only —
        # we are already inside the parent. Children of a submodule dir are
        # usually not separate workspace projects; still skip treating this
        # dir as a project and do not descend into nested .git content.
        # Descend to find sibling-style markers is unusual; skip children
        # of submodule checkouts to avoid noise.
        return

    if depth == max_depth:
        return

    try:
        entries = list(directory.iterdir())
    except OSError:
        return

    for entry in entries:
        try:
            if not entry.is_dir():
                continue
        except OSError:
            continue
        name = entry.name
        if name in SKIP_DIR_NAMES or name.startswith("."):
            # Allow walking non-skip hidden only if needed — MVP skips all
            # dot-directories except we already handled .git above.
            continue
        if _is_ignored(entry, ignore_resolved):
            continue
        _walk(
            entry,
            depth=depth + 1,
            max_depth=max_depth,
            ignore_resolved=ignore_resolved,
            found=found,
        )


def _collect_markers(directory: Path) -> tuple[str, ...]:
    markers: list[str] = []
    try:
        for entry in directory.iterdir():
            try:
                if not entry.is_file():
                    continue
            except OSError:
                continue
            if entry.name in MARKER_FILES or entry.suffix.lower() in MARKER_SUFFIXES:
                markers.append(entry.name)
    except OSError:
        return ()
    return tuple(sorted(markers))


def _resolved_ignore_set(ignore_paths: list[Path]) -> set[Path]:
    resolved: set[Path] = set()
    for path in ignore_paths:
        try:
            resolved.add(path.expanduser().resolve())
        except OSError:
            continue
    return resolved


def project_mtime(path: Path) -> float:
    """Best-effort last-modified time for a project directory."""

    stamps: list[float] = []
    try:
        stamps.append(path.stat().st_mtime)
    except OSError:
        return 0.0
    for relative in (".git/index", ".git/HEAD", ".git"):
        candidate = path / relative
        try:
            if candidate.exists():
                stamps.append(candidate.stat().st_mtime)
        except OSError:
            continue
    return max(stamps) if stamps else 0.0


def directory_size(path: Path) -> int:
    """Sum file sizes under ``path``, skipping heavy dirs from discovery."""

    total = 0
    try:
        if path.is_file():
            return path.stat().st_size
        if not path.is_dir():
            return 0
        for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
            for name in filenames:
                file_path = Path(dirpath) / name
                try:
                    total += file_path.stat().st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def _is_ignored(path: Path, ignore_resolved: set[Path]) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for ignored in ignore_resolved:
        if resolved == ignored or ignored in resolved.parents:
            return True
        # Also ignore if path is under an ignore prefix
        try:
            resolved.relative_to(ignored)
            return True
        except ValueError:
            continue
    return False
