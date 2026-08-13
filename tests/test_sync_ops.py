"""Planner, safety, executor, and sync tests."""

from __future__ import annotations

from pathlib import Path

from get_gited.adapters.command import (
    CommandRequest,
    CommandResult,
    SubprocessCommandRunner,
)
from get_gited.adapters.config import AppConfig, ScanConfig, WorkspaceRootConfig
from get_gited.adapters.fs import LocalProject
from get_gited.application.executor import Executor
from get_gited.application.planner import suggest_operation
from get_gited.application.safety import redact_secret, scan_tree_for_publish
from get_gited.application.status import ProjectStatusRow
from get_gited.application.sync import run_sync
from get_gited.domain.matching import MatchConfidence, ProjectMatch
from get_gited.domain.models import (
    GitFacts,
    ProjectFlag,
    ProjectState,
)
from get_gited.domain.operations import OperationType, PlannedOperation, Risk
from tests.gitutil import add_remote, commit_file, fetch, init_repo, run_git

# Assemble at runtime so this source file is not a contiguous PAT match
# for publish preflight of the Get Gited repo itself.
_FAKE_GITHUB_PAT = "ghp_" + "abcdefghijklmnopqrstuvwxyz012345"


def _row(
    *,
    name: str,
    path: Path | None,
    primary: str,
    flags: set[ProjectFlag] | None = None,
    ahead: int | None = None,
    behind: int | None = None,
    facts: GitFacts | None = None,
    match: ProjectMatch | None = None,
    remote_only: bool = False,
) -> ProjectStatusRow:
    return ProjectStatusRow(
        name=name,
        path=path,
        project=LocalProject(path, name, True, ()) if path else None,
        facts=facts,
        state=ProjectState(
            sync=None,
            flags=frozenset(flags or ()),
            primary=primary,
            ahead=ahead,
            behind=behind,
        ),
        match=match
        or ProjectMatch(confidence=MatchConfidence.NONE, nwo=None, repo=None),
        github_label="—",
        is_remote_only=remote_only,
    )


def test_planner_matrix() -> None:
    path = Path("x")
    push = suggest_operation(
        _row(name="A", path=path, primary="LOCAL_AHEAD", ahead=2, behind=0)
    )
    assert push.type == OperationType.PUSH
    assert push.risk == Risk.SAFE

    dirty_pull = suggest_operation(
        _row(
            name="B",
            path=path,
            primary="REMOTE_AHEAD",
            ahead=0,
            behind=1,
            flags={ProjectFlag.UNCOMMITTED},
        )
    )
    assert dirty_pull.risk == Risk.BLOCKED

    diverged = suggest_operation(
        _row(name="C", path=path, primary="DIVERGED", ahead=1, behind=1)
    )
    assert diverged.risk == Risk.BLOCKED

    remote = suggest_operation(
        _row(
            name="D",
            path=None,
            primary="REMOTE_ONLY",
            remote_only=True,
            match=ProjectMatch(MatchConfidence.EXACT_LIST, "Acme/D", None),
        )
    )
    assert remote.type == OperationType.CLONE


def test_secret_scan_blocks_env(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(f"TOKEN={_FAKE_GITHUB_PAT}\n", encoding="utf-8")
    report = scan_tree_for_publish(tmp_path)
    assert report.risk == "BLOCKED"
    text = " ".join(f.summary for f in report.findings)
    assert ".env" in text
    assert "abcdefghijklmnopqrstuvwxyz012345" not in text
    assert redact_secret(_FAKE_GITHUB_PAT).endswith("2345")


def test_secret_content_in_regular_file(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text(f"token={_FAKE_GITHUB_PAT}\n", encoding="utf-8")
    report = scan_tree_for_publish(tmp_path)
    assert report.risk == "BLOCKED"
    text = " ".join(f.summary for f in report.findings)
    assert "GitHub token" in text
    assert "abcdefghijklmnopqrstuvwxyz012345" not in text


def test_split_dummy_pat_in_source_is_not_a_scan_hit(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(
        'TOKEN = "ghp_" + "abcdefghijklmnopqrstuvwxyz012345"\n',
        encoding="utf-8",
    )
    report = scan_tree_for_publish(tmp_path)
    assert not any(f.kind == "secret_content" for f in report.findings)


def test_tool_cache_dirs_are_not_scanned_for_secrets(tmp_path: Path) -> None:
    cache = tmp_path / ".mypy_cache"
    cache.mkdir()
    (cache / "blob").write_text(_FAKE_GITHUB_PAT, encoding="utf-8")
    report = scan_tree_for_publish(tmp_path)
    assert not any(f.kind == "secret_content" for f in report.findings)


def test_acceptance_g_dry_run_no_ref_change(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    local = init_repo(tmp_path / "proj")
    commit_file(local, "a.txt", "1\n", "init")
    add_remote(local, "origin", str(bare))
    run_git(local, "push", "-u", "origin", "main")
    commit_file(local, "b.txt", "2\n", "two")
    head_before = run_git(local, "rev-parse", "HEAD").strip()
    remote_before = run_git(local, "rev-parse", "origin/main").strip()

    config = AppConfig(
        roots=(WorkspaceRootConfig(path=tmp_path),),
        scan=ScanConfig(max_depth=4),
        exists=True,
    )
    ops, results, text = run_sync(
        SubprocessCommandRunner(),
        [tmp_path],
        dry_run=True,
        config=config,
    )
    assert results == []
    assert "Dry-run" in text
    assert run_git(local, "rev-parse", "HEAD").strip() == head_before
    assert run_git(local, "rev-parse", "origin/main").strip() == remote_before
    assert any(op.type == OperationType.PUSH for op in ops)


def test_acceptance_i_safe_pull(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    local = init_repo(tmp_path / "local")
    other = init_repo(tmp_path / "other")
    commit_file(local, "a.txt", "1\n", "init")
    add_remote(local, "origin", str(bare))
    run_git(local, "push", "-u", "origin", "main")

    run_git(other, "remote", "add", "origin", str(bare))
    run_git(other, "fetch", "origin")
    run_git(other, "checkout", "-b", "main", "origin/main")
    commit_file(other, "b.txt", "remote\n", "remote")
    run_git(other, "push", "origin", "main")
    fetch(local)

    op = PlannedOperation(
        type=OperationType.PULL,
        name="local",
        risk=Risk.SAFE,
        reason="test",
        preconditions=(),
        preview=("pull",),
        path=local,
    )
    result = Executor(SubprocessCommandRunner()).execute_one(op)
    assert result.status == "success"
    assert result.verification == "passed"


def test_push_local_ahead(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    local = init_repo(tmp_path / "local")
    commit_file(local, "a.txt", "1\n", "init")
    add_remote(local, "origin", str(bare))
    run_git(local, "push", "-u", "origin", "main")
    commit_file(local, "b.txt", "2\n", "two")

    op = PlannedOperation(
        type=OperationType.PUSH,
        name="local",
        risk=Risk.SAFE,
        reason="test",
        preconditions=(),
        preview=("push",),
        path=local,
    )
    result = Executor(SubprocessCommandRunner()).execute_one(op)
    assert result.status == "success"


def test_clone_collision_blocked(tmp_path: Path) -> None:
    dest = tmp_path / "exists"
    dest.mkdir()
    op = PlannedOperation(
        type=OperationType.CLONE,
        name="exists",
        risk=Risk.SAFE,
        reason="test",
        preconditions=(),
        preview=("clone",),
        nwo="Acme/exists",
        destination=dest,
    )
    result = Executor(SubprocessCommandRunner()).execute_one(op)
    assert result.status == "blocked"
    assert dest.is_dir()


def test_clone_success(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    seed = init_repo(tmp_path / "seed")
    commit_file(seed, "a.txt", "1\n", "init")
    add_remote(seed, "origin", str(bare))
    run_git(seed, "push", "-u", "origin", "main")

    dest = tmp_path / "cloned"
    op = PlannedOperation(
        type=OperationType.CLONE,
        name="cloned",
        risk=Risk.SAFE,
        reason="test",
        preconditions=(),
        preview=("clone",),
        nwo=str(bare),
        destination=dest,
    )
    result = Executor(SubprocessCommandRunner()).execute_one(op)
    assert result.status == "success"
    assert (dest / ".git").exists()


def test_acceptance_j_failure_isolation(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    ok_repo = init_repo(tmp_path / "ok")
    commit_file(ok_repo, "a.txt", "1\n", "init")
    add_remote(ok_repo, "origin", str(bare))
    run_git(ok_repo, "push", "-u", "origin", "main")
    commit_file(ok_repo, "b.txt", "2\n", "two")

    class FlakyRunner:
        def __init__(self) -> None:
            self.real = SubprocessCommandRunner()
            self.calls = 0

        def run(self, request: CommandRequest) -> CommandResult:
            self.calls += 1
            # Fail the first push only
            if (
                request.argv[:2] == ["git", "-c"]
                and "push" in request.argv
                and not hasattr(self, "_failed")
            ):
                self._failed = True
                return CommandResult(
                    argv=tuple(request.argv),
                    exit_code=1,
                    stdout="",
                    stderr="simulated push failure",
                    timed_out=False,
                    duration_ms=1,
                )
            return self.real.run(request)

    runner = FlakyRunner()
    ops = [
        PlannedOperation(
            type=OperationType.PUSH,
            name="fail-first",
            risk=Risk.SAFE,
            reason="t",
            preconditions=(),
            preview=(),
            path=ok_repo,
        ),
        PlannedOperation(
            type=OperationType.PUSH,
            name="second",
            risk=Risk.SAFE,
            reason="t",
            preconditions=(),
            preview=(),
            path=ok_repo,
        ),
    ]
    # After first failure, second push should succeed (already may be pushed or not)
    # Recreate ahead state for second if first failed before push
    results = Executor(runner).execute_many(ops)  # type: ignore[arg-type]
    assert results[0].status == "failed"
    # Second may succeed or be success/noop-ish; ensure it ran and wasn't cancelled
    assert results[1].status in {"success", "failed", "blocked"}
    assert len(results) == 2


def test_publish_blocked_by_secret(tmp_path: Path) -> None:
    local = init_repo(tmp_path / "secretproj")
    commit_file(local, "a.txt", "ok\n", "init")
    (local / ".env").write_text(f"SECRET={_FAKE_GITHUB_PAT}\n", encoding="utf-8")
    op = PlannedOperation(
        type=OperationType.PUBLISH,
        name="secretproj",
        risk=Risk.WARNING,
        reason="publish",
        preconditions=(),
        preview=(),
        path=local,
        visibility="private",
    )
    result = Executor(SubprocessCommandRunner()).execute_one(op)
    assert result.status == "blocked"
    assert "blocked" in result.message.lower()
