"""Git CLI adapter — machine-readable inspect only (Slice 2)."""

from __future__ import annotations

import re
from pathlib import Path

from get_gited.adapters.command import CommandRequest, CommandResult, CommandRunner
from get_gited.domain.models import GitFacts, RemoteInfo, WorkingTreeState

_BRANCH_AHEAD_BEHIND = re.compile(r"^# branch\.ab \+(\d+) \-(\d+)\s*$")
_BRANCH_HEAD = re.compile(r"^# branch\.head (.+)$")
_BRANCH_UPSTREAM = re.compile(r"^# branch\.upstream (.+)$")
_BRANCH_OID = re.compile(r"^# branch\.oid (.+)$")


class GitError(Exception):
    """Git command failed in an unexpected way."""


class GitAdapter:
    def __init__(self, runner: CommandRunner) -> None:
        self._runner = runner

    def inspect(self, path: Path) -> GitFacts:
        repo_root = self._rev_parse_toplevel(path)
        status = self._run(
            repo_root,
            [
                "status",
                "--porcelain=v2",
                "--branch",
                "--untracked-files=all",
            ],
        )
        branch, detached, upstream, ahead, behind, head_from_status = (
            _parse_branch_header(status.stdout)
        )
        working_tree = _parse_working_tree(status.stdout)
        head = head_from_status
        if head is None or head == "(unknown)":
            head = self._rev_parse_head(repo_root)
        remotes = self._list_remotes(repo_root)

        if upstream is not None and (ahead is None or behind is None):
            ahead, behind = self._left_right_count(repo_root, upstream)

        return GitFacts(
            repo_root=repo_root,
            head=head,
            branch=None if detached else branch,
            detached=detached,
            remotes=remotes,
            upstream=upstream,
            ahead=ahead,
            behind=behind,
            working_tree=working_tree,
        )

    def _run(self, cwd: Path, args: list[str], *, check: bool = True) -> CommandResult:
        result = self._runner.run(
            CommandRequest(
                argv=["git", "-c", "core.quotepath=false", *args],
                cwd=cwd,
            )
        )
        if result.spawn_error is not None:
            raise GitError(f"git failed to start: {result.spawn_error}")
        if result.timed_out:
            raise GitError("git timed out")
        if check and result.exit_code != 0:
            raise GitError(
                (result.stderr or result.stdout or f"exit {result.exit_code}").strip()
            )
        return result

    def _rev_parse_toplevel(self, path: Path) -> Path:
        result = self._run(path, ["rev-parse", "--show-toplevel"])
        text = result.stdout.strip()
        if not text:
            raise GitError("not a git repository")
        return Path(text)

    def _rev_parse_head(self, repo_root: Path) -> str | None:
        result = self._runner.run(
            CommandRequest(
                argv=["git", "-c", "core.quotepath=false", "rev-parse", "HEAD"],
                cwd=repo_root,
            )
        )
        if result.exit_code != 0:
            return None
        return result.stdout.strip() or None

    def _list_remotes(self, repo_root: Path) -> tuple[RemoteInfo, ...]:
        result = self._run(repo_root, ["remote", "-v"], check=False)
        if result.exit_code != 0:
            return ()
        remotes: dict[str, str] = {}
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] not in remotes:
                remotes[parts[0]] = parts[1]
        return tuple(RemoteInfo(name=n, url=u) for n, u in sorted(remotes.items()))

    def _left_right_count(
        self, repo_root: Path, upstream: str
    ) -> tuple[int | None, int | None]:
        result = self._runner.run(
            CommandRequest(
                argv=[
                    "git",
                    "-c",
                    "core.quotepath=false",
                    "rev-list",
                    "--left-right",
                    "--count",
                    f"{upstream}...HEAD",
                ],
                cwd=repo_root,
            )
        )
        if result.exit_code != 0:
            return None, None
        parts = result.stdout.strip().split()
        if len(parts) != 2:
            return None, None
        # left = upstream-only (behind), right = HEAD-only (ahead)
        behind_s, ahead_s = parts
        return int(ahead_s), int(behind_s)


def _parse_branch_header(
    stdout: str,
) -> tuple[str | None, bool, str | None, int | None, int | None, str | None]:
    branch: str | None = None
    detached = False
    upstream: str | None = None
    ahead: int | None = None
    behind: int | None = None
    head: str | None = None

    for line in stdout.splitlines():
        if not line.startswith("# "):
            continue
        m_head = _BRANCH_HEAD.match(line)
        if m_head:
            value = m_head.group(1).strip()
            if value == "(detached)":
                detached = True
                branch = None
            else:
                branch = value
            continue
        m_up = _BRANCH_UPSTREAM.match(line)
        if m_up:
            upstream = m_up.group(1).strip()
            continue
        m_ab = _BRANCH_AHEAD_BEHIND.match(line)
        if m_ab:
            ahead = int(m_ab.group(1))
            behind = int(m_ab.group(2))
            continue
        m_oid = _BRANCH_OID.match(line)
        if m_oid:
            oid = m_oid.group(1).strip()
            if oid != "(unknown)":
                head = oid
    return branch, detached, upstream, ahead, behind, head


def _parse_working_tree(stdout: str) -> WorkingTreeState:
    staged = 0
    unstaged = 0
    untracked = 0
    for line in stdout.splitlines():
        if not line or line.startswith("# "):
            continue
        if line.startswith("? ") or line.startswith("! "):
            untracked += 1
            continue
        if line.startswith("1 ") or line.startswith("2 "):
            # porcelain v2: "1 <XY> ..."
            parts = line.split(" ", 2)
            if len(parts) < 2:
                continue
            xy = parts[1]
            if len(xy) < 2:
                continue
            x, y = xy[0], xy[1]
            if x != ".":
                staged += 1
            if y != ".":
                unstaged += 1
            continue
        if line.startswith("u "):
            unstaged += 1
    return WorkingTreeState(
        staged_count=staged,
        unstaged_count=unstaged,
        untracked_count=untracked,
    )
