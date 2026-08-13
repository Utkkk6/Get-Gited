"""Toolchain diagnostics for ``get-gited doctor`` (Slice 0)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from get_gited.adapters.command import CommandRequest, CommandRunner, which
from get_gited.adapters.config import AppConfig, ConfigError, load_config


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DoctorReport:
    checks: tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


def run_doctor(
    runner: CommandRunner,
    *,
    config_path: Path | None = None,
) -> DoctorReport:
    """Collect bootstrap diagnostics. Never raises for missing git/gh."""

    checks: list[DoctorCheck] = [
        DoctorCheck(
            name="Python",
            ok=True,
            detail=f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}",
        ),
        _check_tool_version(runner, name="Git", executable="git"),
        _check_tool_version(runner, name="GitHub CLI", executable="gh"),
        _check_gh_auth(runner),
        _check_config(config_path),
    ]
    return DoctorReport(checks=tuple(checks))


def format_doctor_report(report: DoctorReport) -> str:
    width = max(len(check.name) for check in report.checks)
    lines: list[str] = []
    for check in report.checks:
        mark = "OK" if check.ok else "FAIL"
        lines.append(f"{check.name:<{width}}  {mark}  {check.detail}")
    return "\n".join(lines)


def _check_tool_version(
    runner: CommandRunner,
    *,
    name: str,
    executable: str,
) -> DoctorCheck:
    resolved = which(executable)
    if resolved is None:
        return DoctorCheck(
            name=name,
            ok=False,
            detail=f"{executable} not found on PATH",
        )

    result = runner.run(CommandRequest(argv=[executable, "--version"]))
    if result.spawn_error is not None:
        return DoctorCheck(
            name=name,
            ok=False,
            detail=f"failed to start {executable}: {result.spawn_error}",
        )
    if result.timed_out:
        return DoctorCheck(name=name, ok=False, detail=f"{executable} timed out")
    if result.exit_code != 0:
        err = (result.stderr or result.stdout).strip() or f"exit {result.exit_code}"
        return DoctorCheck(name=name, ok=False, detail=err)

    lines = (result.stdout or result.stderr).strip().splitlines()
    detail = lines[0].strip() if lines else f"{executable} available"
    return DoctorCheck(name=name, ok=True, detail=detail)


def _check_gh_auth(runner: CommandRunner) -> DoctorCheck:
    if which("gh") is None:
        return DoctorCheck(
            name="GitHub auth",
            ok=False,
            detail="gh not installed",
        )

    result = runner.run(CommandRequest(argv=["gh", "auth", "status"]))
    if result.spawn_error is not None:
        return DoctorCheck(
            name="GitHub auth",
            ok=False,
            detail=f"failed to start gh: {result.spawn_error}",
        )
    if result.timed_out:
        return DoctorCheck(
            name="GitHub auth",
            ok=False,
            detail="gh auth status timed out",
        )

    combined = f"{result.stdout}\n{result.stderr}".strip()
    if result.exit_code == 0:
        login = _extract_gh_login(combined)
        detail = f"authenticated as {login}" if login else "authenticated"
        return DoctorCheck(name="GitHub auth", ok=True, detail=detail)

    detail = _summarize_gh_auth_failure(combined) or "not authenticated"
    return DoctorCheck(name="GitHub auth", ok=False, detail=detail)


def _extract_gh_login(text: str) -> str | None:
    """Best-effort parse of ``gh auth status`` without dumping tokens."""

    for line in text.splitlines():
        lowered = line.lower()
        if "logged in to" in lowered and "as" in lowered:
            # Example: "✓ Logged in to github.com account Utkkk6 (keyring)"
            parts = line.split(" as ")
            if len(parts) >= 2:
                account = parts[-1].strip()
                account = account.split()[0] if account else ""
                account = account.strip("()")
                if account:
                    return account
        if "account" in lowered:
            tokens = line.split()
            for index, token in enumerate(tokens):
                if token.lower() == "account" and index + 1 < len(tokens):
                    return tokens[index + 1].strip("()")
    return None


def _summarize_gh_auth_failure(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if "token" in lower or "password" in lower:
            continue
        return stripped
    return "not authenticated (run: gh auth login)"


def _check_config(config_path: Path | None) -> DoctorCheck:
    try:
        config: AppConfig = load_config(config_path)
    except ConfigError as exc:
        return DoctorCheck(name="Config", ok=False, detail=str(exc))

    path = config.source_path
    path_display = str(path) if path is not None else "(unknown)"
    if not config.exists:
        return DoctorCheck(
            name="Config",
            ok=True,
            detail=f"not found (using defaults): {path_display}",
        )

    root_count = len(config.roots)
    ignore_count = len(config.ignore.paths)
    return DoctorCheck(
        name="Config",
        ok=True,
        detail=f"OK ({root_count} roots, {ignore_count} ignores): {path_display}",
    )
