"""Helpers for creating real temporary Git repositories in tests."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {completed.stderr}")
    return completed.stdout


def init_repo(path: Path, *, bare: bool = False) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    args = ["init"]
    if bare:
        args.append("--bare")
    else:
        args.extend(["-b", "main"])
    run_git(path, *args)
    if not bare:
        run_git(path, "config", "user.email", "test@example.com")
        run_git(path, "config", "user.name", "Get Gited Test")
    return path


def commit_file(repo: Path, relative: str, content: str, message: str) -> str:
    target = repo / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    run_git(repo, "add", relative)
    run_git(repo, "commit", "-m", message)
    return run_git(repo, "rev-parse", "HEAD").strip()


def add_remote(repo: Path, name: str, url: str) -> None:
    run_git(repo, "remote", "add", name, url)


def fetch(repo: Path, remote: str = "origin") -> None:
    run_git(repo, "fetch", remote)


def set_upstream(repo: Path, branch: str, upstream: str) -> None:
    run_git(repo, "branch", f"--set-upstream-to={upstream}", branch)
