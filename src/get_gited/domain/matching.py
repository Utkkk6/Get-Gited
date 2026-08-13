"""Match local projects to GitHub repositories."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from get_gited.adapters.fs import LocalProject
from get_gited.adapters.github import GitHubRepo, parse_github_nwo
from get_gited.domain.models import GitFacts, ProjectFlag


class MatchConfidence(StrEnum):
    EXACT_REMOTE = "exact_remote"
    EXACT_LIST = "exact_list"
    NAME_HINT = "name_hint"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ProjectMatch:
    confidence: MatchConfidence
    nwo: str | None
    repo: GitHubRepo | None = None


@dataclass(frozen=True, slots=True)
class MatchedWorkspaceItem:
    """Local or remote-only workspace row after matching."""

    kind: str  # "local" | "remote_only"
    project: LocalProject | None
    facts: GitFacts | None
    match: ProjectMatch
    flags: frozenset[ProjectFlag]
    primary_override: str | None = None


def match_local_project(
    project: LocalProject,
    facts: GitFacts | None,
    repos_by_nwo: dict[str, GitHubRepo],
    repos_by_name: dict[str, list[GitHubRepo]],
) -> ProjectMatch:
    if facts is not None:
        for remote in facts.remotes:
            nwo = parse_github_nwo(remote.url)
            if nwo is None:
                continue
            key = nwo.lower()
            repo = repos_by_nwo.get(key)
            return ProjectMatch(
                confidence=MatchConfidence.EXACT_REMOTE,
                nwo=nwo,
                repo=repo,
            )

    name_key = project.name.lower()
    candidates = repos_by_name.get(name_key, [])
    if len(candidates) == 1:
        repo = candidates[0]
        # name_hint only — never auto-bind for writes
        return ProjectMatch(
            confidence=MatchConfidence.NAME_HINT,
            nwo=repo.name_with_owner,
            repo=repo,
        )

    return ProjectMatch(confidence=MatchConfidence.NONE, nwo=None, repo=None)


def build_repo_indexes(
    repos: list[GitHubRepo],
) -> tuple[dict[str, GitHubRepo], dict[str, list[GitHubRepo]]]:
    by_nwo: dict[str, GitHubRepo] = {}
    by_name: dict[str, list[GitHubRepo]] = {}
    for repo in repos:
        by_nwo[repo.name_with_owner.lower()] = repo
        by_name.setdefault(repo.name.lower(), []).append(repo)
    return by_nwo, by_name


def find_duplicate_nwos(matches: list[ProjectMatch]) -> set[str]:
    counts: dict[str, int] = {}
    for match in matches:
        if (
            match.confidence
            in {
                MatchConfidence.EXACT_REMOTE,
                MatchConfidence.EXACT_LIST,
            }
            and match.nwo
        ):
            key = match.nwo.lower()
            counts[key] = counts.get(key, 0) + 1
    return {nwo for nwo, count in counts.items() if count > 1}


def remote_only_repos(
    repos: list[GitHubRepo],
    matched_nwos: set[str],
) -> list[GitHubRepo]:
    return [repo for repo in repos if repo.name_with_owner.lower() not in matched_nwos]
