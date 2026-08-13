"""Public one-line project summaries. Never reads .env or source files."""

from __future__ import annotations

import json
import re
import tomllib
from datetime import datetime
from pathlib import Path

from get_gited.adapters.fs import MARKER_FILES, project_mtime
from get_gited.application.safety import SECRET_CONTENT_PATTERNS
from get_gited.application.status import ProjectStatusRow

README_NAMES: tuple[str, ...] = (
    "README.md",
    "README.rst",
    "README.txt",
    "README.ru.md",
    "Readme.md",
    "readme.md",
)

MARKER_GUESS: dict[str, str] = {
    "package.json": "Node.js project",
    "pyproject.toml": "Python package",
    "requirements.txt": "Python project",
    "Pipfile": "Python project",
    "poetry.lock": "Python package",
    "Cargo.toml": "Rust crate",
    "go.mod": "Go module",
    "CMakeLists.txt": "C/C++ project",
    "Makefile": "Make project",
    "Dockerfile": "Containerized app",
    "docker-compose.yml": "Compose app",
    "compose.yml": "Compose app",
}

_BADGE_LINE = re.compile(r"^\[!\[.*\]\(.*\)\]\(.*\)\s*$")


def format_project_date(path: Path | None) -> str:
    if path is None:
        return "—"
    stamp = project_mtime(path)
    if stamp <= 0:
        return "—"
    return datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")


def project_about(path: Path | None, *, infer: bool) -> str:
    """README excerpt, or ``—``. File guesses only when ``infer`` is True."""

    if path is None:
        return "—"
    excerpt = _readme_excerpt(path)
    if excerpt:
        return excerpt
    if not infer:
        return "—"
    guessed = _manifest_description(path) or _marker_guess(path)
    return guessed if guessed else "—"


def row_about(row: ProjectStatusRow, *, infer: bool) -> str:
    return project_about(row.path, infer=infer)


def row_date(row: ProjectStatusRow) -> str:
    return format_project_date(row.path)


def scrub_public_text(text: str) -> str:
    """Strip secret-shaped tokens; leave ordinary README prose intact."""

    cleaned = text
    for pattern, _label in SECRET_CONTENT_PATTERNS:
        cleaned = pattern.sub("[redacted]", cleaned)
    return " ".join(cleaned.split())


def _readme_excerpt(root: Path) -> str | None:
    for name in README_NAMES:
        file = root / name
        try:
            if not file.is_file():
                continue
            raw = file.read_text(encoding="utf-8", errors="replace")[:8000]
        except OSError:
            continue
        excerpt = _first_paragraph(raw)
        if excerpt:
            return scrub_public_text(excerpt)
    return None


def _first_paragraph(markdown: str) -> str | None:
    chunks: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("<!--"):
            continue
        if not line:
            if chunks:
                break
            continue
        if line.startswith("#"):
            if chunks:
                break
            continue
        if line.startswith("===") or line.startswith("---"):
            continue
        if _BADGE_LINE.match(line) or line.startswith("[!"):
            continue
        chunks.append(line.lstrip("> ").strip())
        if len(" ".join(chunks)) >= 160:
            break
    text = " ".join(chunks).strip()
    return text or None


def _manifest_description(root: Path) -> str | None:
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(
                pyproject.read_text(encoding="utf-8", errors="replace")[:20000]
            )
        except (OSError, tomllib.TOMLDecodeError):
            data = None
        if isinstance(data, dict):
            project = data.get("project")
            if isinstance(project, dict):
                description = project.get("description")
                if isinstance(description, str) and description.strip():
                    return scrub_public_text(description.strip())

    package = root / "package.json"
    if package.is_file():
        try:
            data = json.loads(
                package.read_text(encoding="utf-8", errors="replace")[:20000]
            )
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            description = data.get("description")
            if isinstance(description, str) and description.strip():
                return scrub_public_text(description.strip())

    cargo = root / "Cargo.toml"
    if cargo.is_file():
        try:
            data = tomllib.loads(
                cargo.read_text(encoding="utf-8", errors="replace")[:20000]
            )
        except (OSError, tomllib.TOMLDecodeError):
            data = None
        if isinstance(data, dict):
            package_meta = data.get("package")
            if isinstance(package_meta, dict):
                description = package_meta.get("description")
                if isinstance(description, str) and description.strip():
                    return scrub_public_text(description.strip())
    return None


def _marker_guess(root: Path) -> str | None:
    try:
        names = {entry.name for entry in root.iterdir()}
    except OSError:
        return None
    for marker in MARKER_FILES:
        if marker in names:
            return MARKER_GUESS.get(marker, marker)
    if any(name.endswith(".sln") or name.endswith(".csproj") for name in names):
        return ".NET project"
    return None
