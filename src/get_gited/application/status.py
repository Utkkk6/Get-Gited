"""Workspace status service — local Git + GitHub matching."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from get_gited.adapters.command import CommandRunner
from get_gited.adapters.config import AppConfig, load_config
from get_gited.adapters.fs import LocalProject, discover_projects
from get_gited.adapters.git import GitAdapter, GitError
from get_gited.adapters.github import GitHubAdapter, GitHubError, GitHubRepo
from get_gited.application.scan import resolve_scan_roots
from get_gited.domain.matching import (
    MatchConfidence,
    ProjectMatch,
    build_repo_indexes,
    find_duplicate_nwos,
    match_local_project,
    remote_only_repos,
)
from get_gited.domain.models import GitFacts, ProjectFlag, ProjectState
from get_gited.domain.state import derive_local_project_state


@dataclass(frozen=True, slots=True)
class ProjectStatusRow:
    name: str
    path: Path | None
    project: LocalProject | None
    facts: GitFacts | None
    state: ProjectState
    match: ProjectMatch
    github_label: str
    is_remote_only: bool = False


def collect_workspace_status(
    runner: CommandRunner,
    cli_roots: list[Path] | None = None,
    *,
    config: AppConfig | None = None,
    config_path: Path | None = None,
    include_github: bool = True,
) -> list[ProjectStatusRow]:
    cfg = config if config is not None else load_config(config_path)
    roots = resolve_scan_roots(cli_roots, cfg)
    if not roots and not include_github:
        return []

    projects = (
        discover_projects(
            roots,
            ignore_paths=list(cfg.ignore.paths),
            max_depth=cfg.scan.max_depth,
        )
        if roots
        else []
    )

    git = GitAdapter(runner)
    local_facts: list[tuple[LocalProject, GitFacts | None, str | None]] = []
    for project in projects:
        facts: GitFacts | None = None
        error: str | None = None
        if project.has_git_dir:
            try:
                facts = git.inspect(project.path)
            except GitError as exc:
                error = str(exc)
        local_facts.append((project, facts, error))

    repos: list[GitHubRepo] = []
    github_error: str | None = None
    if include_github:
        gh = GitHubAdapter(runner)
        try:
            if gh.is_installed():
                repos = gh.list_repos()
        except GitHubError as exc:
            github_error = str(exc)

    by_nwo, by_name = build_repo_indexes(repos)
    local_matches: list[ProjectMatch] = []
    rows: list[ProjectStatusRow] = []

    for project, facts, error in local_facts:
        match = match_local_project(project, facts, by_nwo, by_name)
        local_matches.append(match)
        state = derive_local_project_state(
            facts,
            has_git=project.has_git_dir,
            error=error,
            match_confidence=match.confidence,
            matched_nwo=match.nwo,
        )
        github_label = _github_label(match, github_error)
        rows.append(
            ProjectStatusRow(
                name=project.name,
                path=project.path,
                project=project,
                facts=facts,
                state=state,
                match=match,
                github_label=github_label,
            )
        )

    duplicate_nwos = find_duplicate_nwos(local_matches)
    if duplicate_nwos:
        rows = [
            _with_duplicate_flag(row, duplicate_nwos) if not row.is_remote_only else row
            for row in rows
        ]

    matched_exact = {
        m.nwo.lower()
        for m in local_matches
        if m.nwo
        and m.confidence in {MatchConfidence.EXACT_REMOTE, MatchConfidence.EXACT_LIST}
    }
    for repo in remote_only_repos(repos, matched_exact):
        state = ProjectState(
            sync=None,
            flags=frozenset({ProjectFlag.REMOTE_ONLY}),
            primary="REMOTE_ONLY",
        )
        match = ProjectMatch(
            confidence=MatchConfidence.EXACT_LIST,
            nwo=repo.name_with_owner,
            repo=repo,
        )
        rows.append(
            ProjectStatusRow(
                name=repo.name,
                path=None,
                project=None,
                facts=None,
                state=state,
                match=match,
                github_label=repo.name_with_owner,
                is_remote_only=True,
            )
        )

    return rows


# Backwards-compatible alias used by earlier Slice 2 call sites/tests.
def collect_local_status(
    runner: CommandRunner,
    cli_roots: list[Path] | None = None,
    *,
    config: AppConfig | None = None,
    config_path: Path | None = None,
) -> list[ProjectStatusRow]:
    return collect_workspace_status(
        runner,
        cli_roots,
        config=config,
        config_path=config_path,
        include_github=False,
    )


def format_status_table(rows: list[ProjectStatusRow]) -> str:
    if not rows:
        return "No projects found."

    name_w = max(len("Project"), max(len(r.name) for r in rows))
    local_w = len("Local")
    github_w = max(len("GitHub"), max(len(r.github_label) for r in rows))
    status_w = max(len("Status"), max(len(status_label(r)) for r in rows))

    header = (
        f"{'Project':<{name_w}}  {'Local':<{local_w}}  "
        f"{'GitHub':<{github_w}}  {'Status':<{status_w}}"
    )
    lines = [
        header,
        f"{'-' * name_w}  {'-' * local_w}  {'-' * github_w}  {'-' * status_w}",
    ]
    for row in rows:
        local = "no" if row.is_remote_only else "yes"
        lines.append(
            f"{row.name:<{name_w}}  {local:<{local_w}}  "
            f"{row.github_label:<{github_w}}  {status_label(row):<{status_w}}"
        )
    lines.append("")
    lines.append(f"Projects: {len(rows)}")
    return "\n".join(lines)


def _github_label(match: ProjectMatch, github_error: str | None) -> str:
    if match.nwo and match.confidence != MatchConfidence.NONE:
        if match.confidence == MatchConfidence.NAME_HINT:
            return f"{match.nwo}?"
        return match.nwo
    if github_error:
        return "—"
    return "—"


def status_label(row: ProjectStatusRow) -> str:
    label = row.state.primary
    extras: list[str] = []
    if row.state.ahead is not None and row.state.primary == "LOCAL_AHEAD":
        extras.append(f"ahead={row.state.ahead}")
    if row.state.behind is not None and row.state.primary == "REMOTE_AHEAD":
        extras.append(f"behind={row.state.behind}")
    if ProjectFlag.UNCOMMITTED in row.state.flags:
        extras.append("UNCOMMITTED")
    if ProjectFlag.DUPLICATE_HINT in row.state.flags:
        extras.append("DUP")
    if extras:
        return f"{label} ({', '.join(extras)})"
    return label


def _with_duplicate_flag(
    row: ProjectStatusRow, duplicate_nwos: set[str]
) -> ProjectStatusRow:
    if not row.match.nwo or row.match.nwo.lower() not in duplicate_nwos:
        return row
    if row.match.confidence not in {
        MatchConfidence.EXACT_REMOTE,
        MatchConfidence.EXACT_LIST,
    }:
        return row
    flags = set(row.state.flags)
    flags.add(ProjectFlag.DUPLICATE_HINT)
    state = ProjectState(
        sync=row.state.sync,
        flags=frozenset(flags),
        primary=row.state.primary,
        ahead=row.state.ahead,
        behind=row.state.behind,
        error=row.state.error,
    )
    return ProjectStatusRow(
        name=row.name,
        path=row.path,
        project=row.project,
        facts=row.facts,
        state=state,
        match=row.match,
        github_label=row.github_label,
        is_remote_only=row.is_remote_only,
    )
