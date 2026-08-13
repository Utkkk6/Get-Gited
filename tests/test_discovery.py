"""Discovery engine tests (acceptance A and related)."""

from __future__ import annotations

from pathlib import Path

from get_gited.adapters.fs import discover_projects


def _touch(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_acceptance_a_discovery(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    project_a = workspace / "project-a"
    project_b = workspace / "project-b"
    nested = workspace / "project-c" / "node_modules" / "something"

    (project_a / ".git").mkdir(parents=True)
    _touch(project_b / "pyproject.toml", "[project]\nname='b'\n")
    _touch(nested / "package.json", "{}\n")

    projects = discover_projects([workspace])
    names = {p.name for p in projects}

    assert "project-a" in names
    assert "project-b" in names
    assert "something" not in names
    assert not any(p.path == nested for p in projects)


def test_skip_dirs_and_ignore_paths(tmp_path: Path) -> None:
    root = tmp_path / "root"
    kept = root / "app"
    skipped = root / "node_modules" / "lib"
    archived = root / "archive" / "old"

    (kept / ".git").mkdir(parents=True)
    _touch(skipped / "package.json", "{}\n")
    (archived / ".git").mkdir(parents=True)

    projects = discover_projects([root], ignore_paths=[root / "archive"])
    paths = {p.path for p in projects}
    assert kept in paths
    assert archived not in paths
    assert not any("node_modules" in str(p.path) for p in projects)


def test_git_dir_not_recursed_for_nested(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    nested = root / "vendor-like" / "inner"
    _touch(nested / "pyproject.toml", "[project]\nname='inner'\n")

    projects = discover_projects([tmp_path])
    names = {p.name for p in projects}
    assert "repo" in names
    assert "inner" not in names


def test_git_file_submodule_not_project(tmp_path: Path) -> None:
    root = tmp_path / "mono"
    root.mkdir()
    _touch(root / "pyproject.toml", "[project]\nname='mono'\n")
    sub = root / "vendor-mod"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/vendor-mod\n", encoding="utf-8")
    _touch(sub / "package.json", "{}\n")

    projects = discover_projects([tmp_path], max_depth=6)
    paths = {p.path for p in projects}
    assert root in paths
    assert sub not in paths


def test_max_depth(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c"
    (deep / ".git").mkdir(parents=True)

    shallow = discover_projects([tmp_path], max_depth=1)
    assert all(p.path != deep for p in shallow)

    deep_found = discover_projects([tmp_path], max_depth=5)
    assert any(p.path == deep for p in deep_found)


def test_marker_suffixes(tmp_path: Path) -> None:
    proj = tmp_path / "dotnet"
    proj.mkdir()
    _touch(proj / "App.csproj", "<Project></Project>\n")
    projects = discover_projects([tmp_path])
    assert any(p.path == proj for p in projects)
