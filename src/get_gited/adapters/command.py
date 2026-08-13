"""Subprocess command runner — the only process spawn boundary."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CommandRequest:
    """Request to run an external program without a shell."""

    argv: list[str]
    cwd: Path | None = None
    timeout_seconds: float | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Structured outcome of a command attempt."""

    argv: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: int
    spawn_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and self.spawn_error is None


class CommandRunner(Protocol):
    """Port for running external commands (real or fake in tests)."""

    def run(self, request: CommandRequest) -> CommandResult:
        """Execute ``request`` and return a structured result."""


def which(executable: str) -> str | None:
    """Resolve an executable on PATH, then well-known Windows install dirs.

    IDEs and ``Activate.ps1`` often keep a PATH snapshot from before
    ``winget install GitHub.cli``. ``gh.exe`` is still on disk.
    """

    found = shutil.which(executable)
    if found:
        return found
    extra = os.pathsep.join(str(path) for path in extra_tool_dirs() if path.is_dir())
    if not extra:
        return None
    return shutil.which(executable, path=extra)


def extra_tool_dirs() -> tuple[Path, ...]:
    """Install locations that winget uses but a stale PATH may omit."""

    if os.name != "nt":
        return ()
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    local = os.environ.get("LOCALAPPDATA", "")
    dirs = [Path(program_files) / "GitHub CLI"]
    if local:
        root = Path(local)
        dirs.append(root / "Programs" / "GitHub CLI")
        dirs.append(root / "GitHub CLI")
    return tuple(dirs)


def _path_with_extra_tools(current: str) -> str:
    prefix = [str(path) for path in extra_tool_dirs() if path.is_dir()]
    if not prefix:
        return current
    return os.pathsep.join([*prefix, current]) if current else os.pathsep.join(prefix)


class SubprocessCommandRunner:
    """stdlib subprocess implementation. Always uses shell=False."""

    def run(self, request: CommandRequest) -> CommandResult:
        if not request.argv:
            raise ValueError("CommandRequest.argv must not be empty")

        argv = tuple(request.argv)
        # Never log extra_env — may contain credentials in future callers.
        logger.debug("run argv=%s cwd=%s", argv, request.cwd)

        env = os.environ.copy()
        env["PATH"] = _path_with_extra_tools(env.get("PATH", ""))
        if request.extra_env:
            env.update(request.extra_env)

        started = time.perf_counter()
        try:
            completed = subprocess.run(
                list(argv),
                cwd=str(request.cwd) if request.cwd is not None else None,
                capture_output=True,
                shell=False,
                timeout=request.timeout_seconds,
                env=env,
                check=False,
            )
        except FileNotFoundError as exc:
            duration_ms = _elapsed_ms(started)
            message = str(exc)
            logger.debug("spawn failed argv=%s error=%s", argv, message)
            return CommandResult(
                argv=argv,
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                duration_ms=duration_ms,
                spawn_error=message,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = _elapsed_ms(started)
            stdout = _decode(exc.stdout)
            stderr = _decode(exc.stderr)
            logger.debug("timeout argv=%s duration_ms=%s", argv, duration_ms)
            return CommandResult(
                argv=argv,
                exit_code=None,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                duration_ms=duration_ms,
                spawn_error=None,
            )

        duration_ms = _elapsed_ms(started)
        return CommandResult(
            argv=argv,
            exit_code=completed.returncode,
            stdout=_decode(completed.stdout),
            stderr=_decode(completed.stderr),
            timed_out=False,
            duration_ms=duration_ms,
            spawn_error=None,
        )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="surrogateescape")
