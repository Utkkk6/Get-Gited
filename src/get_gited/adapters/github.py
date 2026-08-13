"""GitHub CLI (`gh`) adapter — auth and repository listing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from get_gited.adapters.command import CommandRequest, CommandRunner, which

_GITHUB_HTTPS = re.compile(
    r"^https?://(?:www\.)?github\.com/([^/]+)/([^/.]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)
_GITHUB_SSH = re.compile(
    r"^(?:ssh://)?git@github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class GitHubUser:
    login: str


@dataclass(frozen=True, slots=True)
class GitHubRepo:
    name: str
    name_with_owner: str
    url: str
    is_private: bool
    default_branch: str | None = None


class GitHubError(Exception):
    """GitHub CLI interaction failed."""


def parse_github_nwo(url: str) -> str | None:
    """Return ``owner/name`` if ``url`` points at GitHub, else None."""

    text = url.strip()
    for pattern in (_GITHUB_HTTPS, _GITHUB_SSH):
        match = pattern.match(text)
        if match:
            owner, name = match.group(1), match.group(2)
            return f"{owner}/{name}"
    return None


class GitHubAdapter:
    def __init__(self, runner: CommandRunner) -> None:
        self._runner = runner

    def is_installed(self) -> bool:
        return which("gh") is not None

    def current_user(self) -> GitHubUser:
        if not self.is_installed():
            raise GitHubError("gh not found on PATH")
        result = self._runner.run(
            CommandRequest(argv=["gh", "api", "user", "--jq", ".login"])
        )
        if result.spawn_error:
            raise GitHubError(f"failed to start gh: {result.spawn_error}")
        if result.exit_code != 0:
            # Fallback without jq for older/fixture paths
            result = self._runner.run(CommandRequest(argv=["gh", "api", "user"]))
            if result.exit_code != 0:
                raise GitHubError(
                    (result.stderr or result.stdout or "gh api user failed").strip()
                )
            data = json.loads(result.stdout)
            login = data.get("login")
            if not isinstance(login, str) or not login:
                raise GitHubError("gh api user returned no login")
            return GitHubUser(login=login)
        login = result.stdout.strip()
        if not login:
            raise GitHubError("gh api user returned empty login")
        return GitHubUser(login=login)

    def list_repos(self, *, limit: int = 1000) -> list[GitHubRepo]:
        if not self.is_installed():
            raise GitHubError("gh not found on PATH")
        repos: list[GitHubRepo] = []
        page_limit = min(100, max(1, limit))
        fetched = 0
        while fetched < limit:
            batch = min(page_limit, limit - fetched)
            result = self._runner.run(
                CommandRequest(
                    argv=[
                        "gh",
                        "repo",
                        "list",
                        "--limit",
                        str(batch),
                        "--json",
                        "name,nameWithOwner,url,isPrivate,defaultBranchRef",
                    ]
                )
            )
            if result.spawn_error:
                raise GitHubError(f"failed to start gh: {result.spawn_error}")
            if result.exit_code != 0:
                raise GitHubError(
                    (result.stderr or result.stdout or "gh repo list failed").strip()
                )
            raw = json.loads(result.stdout or "[]")
            if not isinstance(raw, list):
                raise GitHubError("gh repo list returned non-array JSON")
            if not raw:
                break
            for item in raw:
                repos.append(_parse_repo(item))
            fetched += len(raw)
            if len(raw) < batch:
                break
            # Simple pagination: gh repo list --limit N returns first N only.
            # For MVP one call with high limit is enough; break after one page
            # when using a single --limit request covering remaining.
            break
        return repos


def _parse_repo(item: dict[str, Any]) -> GitHubRepo:
    name = item.get("name")
    nwo = item.get("nameWithOwner")
    url = item.get("url")
    is_private = bool(item.get("isPrivate", True))
    default_branch = None
    ref = item.get("defaultBranchRef")
    if isinstance(ref, dict):
        branch_name = ref.get("name")
        if isinstance(branch_name, str):
            default_branch = branch_name
    if (
        not isinstance(name, str)
        or not isinstance(nwo, str)
        or not isinstance(url, str)
    ):
        raise GitHubError("invalid repo JSON item")
    return GitHubRepo(
        name=name,
        name_with_owner=nwo,
        url=url,
        is_private=is_private,
        default_branch=default_branch,
    )
