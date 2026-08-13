"""Tests for the ``gg`` short-command parser."""

from __future__ import annotations

from pathlib import Path

from get_gited.application.shortcut import parse_gg_argv
from get_gited.application.sort import SortMode


def test_gg_no_args_prompts_cwd(tmp_path: Path) -> None:
    request = parse_gg_argv([], cwd=tmp_path)
    assert request.mode == "prompt"
    assert request.roots == (tmp_path,)


def test_gg_yes_scans_cwd(tmp_path: Path) -> None:
    request = parse_gg_argv(["-y"], cwd=tmp_path)
    assert request.mode == "pick"
    assert request.roots == (tmp_path,)
    request = parse_gg_argv(["--yes"], cwd=tmp_path)
    assert request.mode == "pick"
    assert request.roots == (tmp_path,)


def test_gg_path_picks_that_root(tmp_path: Path) -> None:
    target = tmp_path / "code"
    request = parse_gg_argv([str(target)], cwd=tmp_path)
    assert request.mode == "pick"
    assert request.roots == (target,)


def test_gg_yes_with_path(tmp_path: Path) -> None:
    target = tmp_path / "code"
    request = parse_gg_argv(["--yes", str(target)], cwd=tmp_path)
    assert request.mode == "pick"
    assert request.roots == (target,)


def test_gg_passthrough_commands(tmp_path: Path) -> None:
    for argv in (
        ["status", str(tmp_path)],
        ["scan", str(tmp_path)],
        ["doctor"],
        ["sync", str(tmp_path), "--dry-run"],
        ["acpt", "--help"],
        ["acpt", "--on"],
        ["ui"],
        ["ui", "cards"],
    ):
        request = parse_gg_argv(argv, cwd=tmp_path)
        assert request.mode == "passthrough"
        assert request.passthrough == tuple(argv)


def test_gg_sort_flag(tmp_path: Path) -> None:
    request = parse_gg_argv(["-y", "--sort", "mtime"], cwd=tmp_path)
    assert request.mode == "pick"
    assert request.sort is SortMode.MTIME
    request = parse_gg_argv(["--sort=size", "-y"], cwd=tmp_path)
    assert request.sort is SortMode.SIZE


def test_gg_unknown_sort(tmp_path: Path) -> None:
    request = parse_gg_argv(["--sort", "nope"], cwd=tmp_path)
    assert request.mode == "error"
