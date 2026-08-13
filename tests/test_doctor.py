"""Doctor service tests (fake CommandRunner; no live GitHub)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from get_gited.adapters.command import CommandResult
from get_gited.application.doctor import run_doctor
from tests.fakes import FakeCommandRunner


def _ok(argv: tuple[str, ...], stdout: str) -> CommandResult:
    return CommandResult(
        argv=argv,
        exit_code=0,
        stdout=stdout,
        stderr="",
        timed_out=False,
        duration_ms=1,
    )


def _fail(
    argv: tuple[str, ...], *, exit_code: int = 1, stderr: str = ""
) -> CommandResult:
    return CommandResult(
        argv=argv,
        exit_code=exit_code,
        stdout="",
        stderr=stderr,
        timed_out=False,
        duration_ms=1,
    )


def test_doctor_all_ok(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[[roots]]\npath = "D:\\\\Projects"\n', encoding="utf-8")
    runner = FakeCommandRunner(
        {
            ("git", "--version"): _ok(
                ("git", "--version"), "git version 2.51.0.windows.1"
            ),
            ("gh", "--version"): _ok(
                ("gh", "--version"), "gh version 2.60.0 (2024-01-01)"
            ),
            ("gh", "auth", "status"): _ok(
                ("gh", "auth", "status"),
                "✓ Logged in to github.com account DemoUser (keyring)",
            ),
        }
    )
    with (
        patch(
            "get_gited.application.doctor.which", side_effect=lambda exe: f"/bin/{exe}"
        ),
    ):
        report = run_doctor(runner, config_path=config)

    by_name = {check.name: check for check in report.checks}
    assert by_name["Python"].ok
    assert by_name["Git"].ok
    assert "2.51" in by_name["Git"].detail
    assert by_name["GitHub CLI"].ok
    assert by_name["GitHub auth"].ok
    assert "DemoUser" in by_name["GitHub auth"].detail
    assert by_name["Config"].ok
    assert report.ok


def test_doctor_git_absent(tmp_path: Path) -> None:
    runner = FakeCommandRunner()
    with patch(
        "get_gited.application.doctor.which",
        side_effect=lambda exe: None if exe == "git" else f"/bin/{exe}",
    ):
        report = run_doctor(runner, config_path=tmp_path / "missing.toml")

    git = next(check for check in report.checks if check.name == "Git")
    assert git.ok is False
    assert "not found" in git.detail
    assert report.ok is False


def test_doctor_gh_absent(tmp_path: Path) -> None:
    runner = FakeCommandRunner(
        {
            ("git", "--version"): _ok(("git", "--version"), "git version 2.51.0"),
        }
    )
    with patch(
        "get_gited.application.doctor.which",
        side_effect=lambda exe: f"/bin/{exe}" if exe == "git" else None,
    ):
        report = run_doctor(runner, config_path=tmp_path / "missing.toml")

    gh = next(check for check in report.checks if check.name == "GitHub CLI")
    auth = next(check for check in report.checks if check.name == "GitHub auth")
    assert gh.ok is False
    assert auth.ok is False
    assert "not installed" in auth.detail


def test_doctor_gh_unauthenticated(tmp_path: Path) -> None:
    runner = FakeCommandRunner(
        {
            ("git", "--version"): _ok(("git", "--version"), "git version 2.51.0"),
            ("gh", "--version"): _ok(("gh", "--version"), "gh version 2.60.0"),
            ("gh", "auth", "status"): _fail(
                ("gh", "auth", "status"),
                stderr=(
                    "You are not logged into any GitHub hosts. "
                    "To log in, run: gh auth login"
                ),
            ),
        }
    )
    with patch(
        "get_gited.application.doctor.which", side_effect=lambda exe: f"/bin/{exe}"
    ):
        report = run_doctor(runner, config_path=tmp_path / "missing.toml")

    auth = next(check for check in report.checks if check.name == "GitHub auth")
    assert auth.ok is False
    assert "not logged" in auth.detail.lower() or "auth login" in auth.detail.lower()


def test_doctor_malformed_config(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("[[roots]\n", encoding="utf-8")
    runner = FakeCommandRunner(
        {
            ("git", "--version"): _ok(("git", "--version"), "git version 2.51.0"),
            ("gh", "--version"): _ok(("gh", "--version"), "gh version 2.60.0"),
            ("gh", "auth", "status"): _ok(("gh", "auth", "status"), "ok as Demo"),
        }
    )
    with patch(
        "get_gited.application.doctor.which", side_effect=lambda exe: f"/bin/{exe}"
    ):
        report = run_doctor(runner, config_path=bad)

    config = next(check for check in report.checks if check.name == "Config")
    assert config.ok is False
    assert "Invalid TOML" in config.detail
