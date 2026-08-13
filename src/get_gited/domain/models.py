"""Git facts and working-tree models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkingTreeState:
    staged_count: int
    unstaged_count: int
    untracked_count: int

    @property
    def clean(self) -> bool:
        return (
            self.staged_count == 0
            and self.unstaged_count == 0
            and self.untracked_count == 0
        )


@dataclass(frozen=True, slots=True)
class RemoteInfo:
    name: str
    url: str


@dataclass(frozen=True, slots=True)
class GitFacts:
    repo_root: Path
    head: str | None
    branch: str | None
    detached: bool
    remotes: tuple[RemoteInfo, ...]
    upstream: str | None
    ahead: int | None
    behind: int | None
    working_tree: WorkingTreeState


class SyncState(StrEnum):
    SYNCED = "SYNCED"
    LOCAL_AHEAD = "LOCAL_AHEAD"
    REMOTE_AHEAD = "REMOTE_AHEAD"
    DIVERGED = "DIVERGED"
    UNKNOWN = "UNKNOWN"


class ProjectFlag(StrEnum):
    NO_GIT = "NO_GIT"
    NO_REMOTE = "NO_REMOTE"
    LOCAL_ONLY = "LOCAL_ONLY"
    REMOTE_ONLY = "REMOTE_ONLY"
    UNCOMMITTED = "UNCOMMITTED"
    DETACHED = "DETACHED"
    DUPLICATE_HINT = "DUPLICATE_HINT"
    STALE = "STALE"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class ProjectState:
    sync: SyncState | None
    flags: frozenset[ProjectFlag]
    primary: str
    ahead: int | None = None
    behind: int | None = None
    error: str | None = None
