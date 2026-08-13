"""CommandRunner tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from get_gited.adapters.command import (
    CommandRequest,
    SubprocessCommandRunner,
    which,
)


def test_successful_command() -> None:
    runner = SubprocessCommandRunner()
    result = runner.run(
        CommandRequest(argv=[sys.executable, "-c", "print('hello-gited')"])
    )
    assert result.ok
    assert result.exit_code == 0
    assert "hello-gited" in result.stdout
    assert result.stderr == ""
    assert result.timed_out is False
    assert result.spawn_error is None
    assert result.argv[0] == sys.executable


def test_nonzero_exit_code() -> None:
    runner = SubprocessCommandRunner()
    result = runner.run(
        CommandRequest(argv=[sys.executable, "-c", "raise SystemExit(7)"])
    )
    assert result.exit_code == 7
    assert result.ok is False
    assert result.spawn_error is None


def test_missing_executable() -> None:
    runner = SubprocessCommandRunner()
    result = runner.run(
        CommandRequest(argv=["get-gited-no-such-command-xyz", "--version"])
    )
    assert result.exit_code is None
    assert result.ok is False
    assert result.spawn_error is not None
    assert result.stdout == ""
    assert result.stderr == ""


def test_stdout_and_stderr() -> None:
    runner = SubprocessCommandRunner()
    code = "import sys;sys.stdout.write('out-line\\n');sys.stderr.write('err-line\\n')"
    result = runner.run(CommandRequest(argv=[sys.executable, "-c", code]))
    assert result.exit_code == 0
    assert "out-line" in result.stdout
    assert "err-line" in result.stderr


def test_windows_like_path_argument(tmp_path: Path) -> None:
    runner = SubprocessCommandRunner()
    # Path with spaces must remain a single argv element (no shell).
    target = tmp_path / "My Projects" / "note.txt"
    target.parent.mkdir(parents=True)
    target.write_text("ok", encoding="utf-8")
    code = (
        "import pathlib,sys;"
        "p=pathlib.Path(sys.argv[1]);"
        "print(p.read_text(encoding='utf-8'))"
    )
    result = runner.run(CommandRequest(argv=[sys.executable, "-c", code, str(target)]))
    assert result.ok
    assert result.stdout.strip() == "ok"


def test_cwd_is_honored(tmp_path: Path) -> None:
    runner = SubprocessCommandRunner()
    marker = tmp_path / "marker.txt"
    marker.write_text("here", encoding="utf-8")
    code = "import pathlib; print(pathlib.Path('marker.txt').read_text())"
    result = runner.run(CommandRequest(argv=[sys.executable, "-c", code], cwd=tmp_path))
    assert result.ok
    assert "here" in result.stdout


def test_empty_argv_rejected() -> None:
    runner = SubprocessCommandRunner()
    with pytest.raises(ValueError):
        runner.run(CommandRequest(argv=[]))


@pytest.mark.skipif(os.name != "nt", reason="Windows GitHub CLI install-dir lookup")
def test_which_finds_gh_in_extra_tool_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    target = tmp_path / "GitHub CLI" / "gh.exe"
    target.parent.mkdir()
    target.write_bytes(b"")
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    found = which("gh")
    assert found is not None
    assert Path(found).resolve() == target.resolve()
