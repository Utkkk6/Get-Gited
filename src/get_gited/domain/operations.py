"""Operation types and planned operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class OperationType(StrEnum):
    PUSH = "PUSH"
    PULL = "PULL"
    PUBLISH = "PUBLISH"
    CLONE = "CLONE"
    INIT_GIT = "INIT_GIT"
    SHOW_DIFF = "SHOW_DIFF"
    OPEN_GITHUB = "OPEN_GITHUB"
    SKIP = "SKIP"
    IGNORE_ONCE = "IGNORE_ONCE"
    IGNORE_ALWAYS = "IGNORE_ALWAYS"


class Risk(StrEnum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class PlannedOperation:
    type: OperationType
    name: str
    risk: Risk
    reason: str
    preconditions: tuple[str, ...]
    preview: tuple[str, ...]
    path: Path | None = None
    nwo: str | None = None
    destination: Path | None = None
    visibility: str | None = None


@dataclass(frozen=True, slots=True)
class OperationResult:
    name: str
    type: OperationType
    status: str  # success | failed | blocked | skipped
    verification: str  # passed | failed | not_applicable
    message: str
