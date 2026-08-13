"""Derive compositional project status from Git facts."""

from __future__ import annotations

from get_gited.domain.models import (
    GitFacts,
    ProjectFlag,
    ProjectState,
    SyncState,
)


def sync_state_from_ahead_behind(ahead: int | None, behind: int | None) -> SyncState:
    if ahead is None or behind is None:
        return SyncState.UNKNOWN
    if ahead > 0 and behind > 0:
        return SyncState.DIVERGED
    if ahead > 0 and behind == 0:
        return SyncState.LOCAL_AHEAD
    if ahead == 0 and behind > 0:
        return SyncState.REMOTE_AHEAD
    return SyncState.SYNCED


def derive_local_project_state(
    facts: GitFacts | None,
    *,
    has_git: bool,
    error: str | None = None,
    match_confidence: object | None = None,
    matched_nwo: str | None = None,
) -> ProjectState:
    """Derive status for a local project."""

    if error:
        return ProjectState(
            sync=None,
            flags=frozenset({ProjectFlag.ERROR}),
            primary="ERROR",
            error=error,
        )

    if not has_git or facts is None:
        return ProjectState(
            sync=None,
            flags=frozenset({ProjectFlag.NO_GIT}),
            primary="NO_GIT",
        )

    flags: set[ProjectFlag] = set()
    if facts.detached:
        flags.add(ProjectFlag.DETACHED)
    if not facts.working_tree.clean:
        flags.add(ProjectFlag.UNCOMMITTED)
    if not facts.remotes:
        flags.add(ProjectFlag.NO_REMOTE)

    sync = sync_state_from_ahead_behind(facts.ahead, facts.behind)

    exact_match = False
    if match_confidence is not None:
        confidence_value = getattr(match_confidence, "value", str(match_confidence))
        exact_match = confidence_value in {"exact_remote", "exact_list"}

    if facts.detached:
        flags.add(ProjectFlag.BLOCKED)
        primary = "BLOCKED"
    elif sync == SyncState.DIVERGED:
        flags.add(ProjectFlag.BLOCKED)
        primary = "DIVERGED"
    elif sync == SyncState.LOCAL_AHEAD:
        primary = "LOCAL_AHEAD"
    elif sync == SyncState.REMOTE_AHEAD:
        primary = "REMOTE_AHEAD"
    elif ProjectFlag.NO_REMOTE in flags:
        primary = "NO_REMOTE"
        if not exact_match:
            flags.add(ProjectFlag.LOCAL_ONLY)
    elif sync == SyncState.SYNCED:
        primary = "SYNCED"
    else:
        # Remotes may exist without upstream (UNKNOWN sync) or unmatched GitHub.
        flags.add(ProjectFlag.LOCAL_ONLY)
        primary = "LOCAL_ONLY"

    return ProjectState(
        sync=sync if sync != SyncState.UNKNOWN else None,
        flags=frozenset(flags),
        primary=primary,
        ahead=facts.ahead,
        behind=facts.behind,
    )
