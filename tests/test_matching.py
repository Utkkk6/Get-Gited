"""GitHub matching and URL parsing tests."""

from __future__ import annotations

import json
from pathlib import Path

from get_gited.adapters.command import CommandResult, SubprocessCommandRunner
from get_gited.adapters.fs import LocalProject
from get_gited.adapters.github import GitHubAdapter, GitHubRepo, parse_github_nwo
from get_gited.application.status import collect_workspace_status
from get_gited.domain.matching import (
    MatchConfidence,
    build_repo_indexes,
    find_duplicate_nwos,
    match_local_project,
    remote_only_repos,
)
from get_gited.domain.models import GitFacts, RemoteInfo, WorkingTreeState
from tests.fakes import FakeCommandRunner
from tests.gitutil import add_remote, commit_file, init_repo


def test_parse_github_urls() -> None:
    assert parse_github_nwo("https://github.com/Acme/Demo.git") == "Acme/Demo"
    assert parse_github_nwo("git@github.com:Acme/Demo.git") == "Acme/Demo"
    assert parse_github_nwo("ssh://git@github.com/Acme/Demo.git") == "Acme/Demo"
    assert parse_github_nwo("https://gitlab.com/Acme/Demo.git") is None


def test_exact_remote_match() -> None:
    facts = GitFacts(
        repo_root=Path("."),
        head="abc",
        branch="main",
        detached=False,
        remotes=(RemoteInfo("origin", "https://github.com/Acme/Demo.git"),),
        upstream="origin/main",
        ahead=0,
        behind=0,
        working_tree=WorkingTreeState(0, 0, 0),
    )
    repo = GitHubRepo("Demo", "Acme/Demo", "https://github.com/Acme/Demo", True)
    by_nwo, by_name = build_repo_indexes([repo])
    project = LocalProject(Path("Demo"), "Demo", True, (".git/",))
    match = match_local_project(project, facts, by_nwo, by_name)
    assert match.confidence == MatchConfidence.EXACT_REMOTE
    assert match.nwo == "Acme/Demo"


def test_name_hint_does_not_exact_bind() -> None:
    repo = GitHubRepo("Demo", "Acme/Demo", "https://github.com/Acme/Demo", True)
    by_nwo, by_name = build_repo_indexes([repo])
    project = LocalProject(Path("Demo"), "Demo", True, (".git/",))
    facts = GitFacts(
        repo_root=Path("Demo"),
        head="abc",
        branch="main",
        detached=False,
        remotes=(),
        upstream=None,
        ahead=None,
        behind=None,
        working_tree=WorkingTreeState(0, 0, 0),
    )
    match = match_local_project(project, facts, by_nwo, by_name)
    assert match.confidence == MatchConfidence.NAME_HINT
    assert match.nwo == "Acme/Demo"


def test_remote_only_and_duplicates() -> None:
    demo = GitHubRepo("Demo", "Acme/Demo", "https://github.com/Acme/Demo", True)
    other = GitHubRepo("Other", "Acme/Other", "https://github.com/Acme/Other", True)
    unmatched = remote_only_repos([demo, other], {"acme/demo"})
    assert [r.name for r in unmatched] == ["Other"]

    from get_gited.domain.matching import ProjectMatch

    dups = find_duplicate_nwos(
        [
            ProjectMatch(MatchConfidence.EXACT_REMOTE, "Acme/Demo", demo),
            ProjectMatch(MatchConfidence.EXACT_REMOTE, "Acme/Demo", demo),
        ]
    )
    assert "acme/demo" in dups


def test_github_adapter_list_repos() -> None:
    payload = [
        {
            "name": "Demo",
            "nameWithOwner": "Acme/Demo",
            "url": "https://github.com/Acme/Demo",
            "isPrivate": True,
            "defaultBranchRef": {"name": "main"},
        }
    ]
    runner = FakeCommandRunner(
        {
            (
                "gh",
                "repo",
                "list",
                "--limit",
                "100",
                "--json",
                "name,nameWithOwner,url,isPrivate,defaultBranchRef",
            ): CommandResult(
                argv=("gh", "repo", "list"),
                exit_code=0,
                stdout=json.dumps(payload),
                stderr="",
                timed_out=False,
                duration_ms=1,
            )
        }
    )
    from unittest.mock import patch

    with patch("get_gited.adapters.github.which", return_value="/bin/gh"):
        repos = GitHubAdapter(runner).list_repos(limit=100)
    assert len(repos) == 1
    assert repos[0].name_with_owner == "Acme/Demo"


def test_status_includes_remote_only(tmp_path: Path) -> None:
    local = init_repo(tmp_path / "Demo")
    commit_file(local, "a.txt", "1\n", "init")
    add_remote(local, "origin", "https://github.com/Acme/Demo.git")

    payload = [
        {
            "name": "Demo",
            "nameWithOwner": "Acme/Demo",
            "url": "https://github.com/Acme/Demo",
            "isPrivate": True,
            "defaultBranchRef": {"name": "main"},
        },
        {
            "name": "OnlyRemote",
            "nameWithOwner": "Acme/OnlyRemote",
            "url": "https://github.com/Acme/OnlyRemote",
            "isPrivate": True,
            "defaultBranchRef": {"name": "main"},
        },
    ]
    json_fields = "name,nameWithOwner,url,isPrivate,defaultBranchRef"
    runner = FakeCommandRunner(
        {
            (
                "gh",
                "repo",
                "list",
                "--limit",
                "100",
                "--json",
                json_fields,
            ): CommandResult(
                argv=("gh", "repo", "list"),
                exit_code=0,
                stdout=json.dumps(payload),
                stderr="",
                timed_out=False,
                duration_ms=1,
            )
        },
        default=None,
    )

    # Mix: git commands fall through — need real runner for git, fake for gh.
    class HybridRunner:
        def __init__(self) -> None:
            self.real = SubprocessCommandRunner()
            self.fake = runner

        def run(self, request):  # type: ignore[no-untyped-def]
            if request.argv and request.argv[0] == "gh":
                return self.fake.run(request)
            return self.real.run(request)

    from unittest.mock import patch

    with patch("get_gited.adapters.github.which", return_value="/bin/gh"):
        rows = collect_workspace_status(
            HybridRunner(),  # type: ignore[arg-type]
            [tmp_path],
            include_github=True,
        )

    names = {r.name: r for r in rows}
    assert "Demo" in names
    assert names["Demo"].github_label == "Acme/Demo"
    assert "OnlyRemote" in names
    assert names["OnlyRemote"].is_remote_only is True
    assert names["OnlyRemote"].state.primary == "REMOTE_ONLY"
