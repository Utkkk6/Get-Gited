"""Git adapter and status derivation tests (acceptance B–F)."""

from __future__ import annotations

from pathlib import Path

from get_gited.adapters.command import SubprocessCommandRunner
from get_gited.adapters.git import GitAdapter
from get_gited.domain.models import ProjectFlag, SyncState
from get_gited.domain.state import derive_local_project_state
from tests.gitutil import (
    add_remote,
    commit_file,
    fetch,
    init_repo,
    run_git,
)


def test_acceptance_b_synced(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    local = init_repo(tmp_path / "local")
    commit_file(local, "a.txt", "1\n", "init")
    add_remote(local, "origin", str(bare))
    run_git(local, "push", "-u", "origin", "main")

    facts = GitAdapter(SubprocessCommandRunner()).inspect(local)
    state = derive_local_project_state(facts, has_git=True)
    assert state.primary == "SYNCED"
    assert state.sync == SyncState.SYNCED
    assert state.ahead == 0
    assert state.behind == 0


def test_acceptance_c_local_ahead(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    local = init_repo(tmp_path / "local")
    commit_file(local, "a.txt", "1\n", "init")
    add_remote(local, "origin", str(bare))
    run_git(local, "push", "-u", "origin", "main")
    commit_file(local, "b.txt", "2\n", "two")
    commit_file(local, "c.txt", "3\n", "three")

    facts = GitAdapter(SubprocessCommandRunner()).inspect(local)
    state = derive_local_project_state(facts, has_git=True)
    assert state.primary == "LOCAL_AHEAD"
    assert state.ahead == 2
    assert state.behind == 0


def test_acceptance_d_remote_ahead(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    local = init_repo(tmp_path / "local")
    other = init_repo(tmp_path / "other")
    commit_file(local, "a.txt", "1\n", "init")
    add_remote(local, "origin", str(bare))
    run_git(local, "push", "-u", "origin", "main")

    run_git(other, "remote", "add", "origin", str(bare))
    run_git(other, "fetch", "origin")
    run_git(other, "checkout", "-b", "main", "origin/main")
    commit_file(other, "b.txt", "remote\n", "remote commit")
    run_git(other, "push", "origin", "main")

    fetch(local, "origin")
    facts = GitAdapter(SubprocessCommandRunner()).inspect(local)
    state = derive_local_project_state(facts, has_git=True)
    assert state.primary == "REMOTE_AHEAD"
    assert state.behind == 1
    assert state.ahead == 0


def test_acceptance_e_diverged(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    local = init_repo(tmp_path / "local")
    other = init_repo(tmp_path / "other")
    commit_file(local, "a.txt", "1\n", "init")
    add_remote(local, "origin", str(bare))
    run_git(local, "push", "-u", "origin", "main")

    run_git(other, "remote", "add", "origin", str(bare))
    run_git(other, "fetch", "origin")
    run_git(other, "checkout", "-b", "main", "origin/main")
    commit_file(other, "remote.txt", "r\n", "remote side")
    run_git(other, "push", "origin", "main")

    commit_file(local, "local.txt", "l\n", "local side")
    fetch(local, "origin")

    facts = GitAdapter(SubprocessCommandRunner()).inspect(local)
    state = derive_local_project_state(facts, has_git=True)
    assert state.primary == "DIVERGED"
    assert ProjectFlag.BLOCKED in state.flags
    assert state.ahead == 1
    assert state.behind == 1


def test_acceptance_f_dirty(tmp_path: Path) -> None:
    bare = init_repo(tmp_path / "remote.git", bare=True)
    local = init_repo(tmp_path / "local")
    commit_file(local, "a.txt", "1\n", "init")
    add_remote(local, "origin", str(bare))
    run_git(local, "push", "-u", "origin", "main")
    (local / "dirty.txt").write_text("x\n", encoding="utf-8")

    facts = GitAdapter(SubprocessCommandRunner()).inspect(local)
    state = derive_local_project_state(facts, has_git=True)
    assert state.primary == "SYNCED"
    assert ProjectFlag.UNCOMMITTED in state.flags
    assert facts.working_tree.clean is False


def test_detached_head_blocked(tmp_path: Path) -> None:
    local = init_repo(tmp_path / "local")
    sha = commit_file(local, "a.txt", "1\n", "init")
    run_git(local, "checkout", "--detach", sha)

    facts = GitAdapter(SubprocessCommandRunner()).inspect(local)
    state = derive_local_project_state(facts, has_git=True)
    assert facts.detached is True
    assert state.primary == "BLOCKED"
    assert ProjectFlag.DETACHED in state.flags


def test_no_remote(tmp_path: Path) -> None:
    local = init_repo(tmp_path / "local")
    commit_file(local, "a.txt", "1\n", "init")
    facts = GitAdapter(SubprocessCommandRunner()).inspect(local)
    state = derive_local_project_state(facts, has_git=True)
    assert state.primary == "NO_REMOTE"
    assert ProjectFlag.NO_REMOTE in state.flags


def test_no_git_project(tmp_path: Path) -> None:
    state = derive_local_project_state(None, has_git=False)
    assert state.primary == "NO_GIT"
