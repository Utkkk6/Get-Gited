"""Pure operation planner."""

from __future__ import annotations

from get_gited.application.status import ProjectStatusRow
from get_gited.domain.matching import MatchConfidence
from get_gited.domain.models import ProjectFlag
from get_gited.domain.operations import OperationType, PlannedOperation, Risk


def suggest_operation(row: ProjectStatusRow) -> PlannedOperation:
    """Suggest a default operation for a workspace row (not executed)."""

    primary = row.state.primary
    flags = row.state.flags

    if primary in {"BLOCKED", "ERROR", "DIVERGED"} or ProjectFlag.DETACHED in flags:
        return PlannedOperation(
            type=OperationType.SKIP,
            name=row.name,
            risk=Risk.BLOCKED,
            reason="Manual resolution required",
            preconditions=(),
            preview=("No automatic write operation",),
            path=row.path,
            nwo=row.match.nwo,
        )

    if primary == "REMOTE_ONLY" and row.match.nwo:
        dest = None
        return PlannedOperation(
            type=OperationType.CLONE,
            name=row.name,
            risk=Risk.SAFE,
            reason="Remote-only repository",
            preconditions=("destination must not exist",),
            preview=(f"Clone {row.match.nwo}",),
            nwo=row.match.nwo,
            destination=dest,
        )

    if primary == "NO_GIT" and row.path is not None:
        return PlannedOperation(
            type=OperationType.INIT_GIT,
            name=row.name,
            risk=Risk.WARNING,
            reason="Project has no Git repository",
            preconditions=("user confirmed preview",),
            preview=("git init",),
            path=row.path,
        )

    if primary in {"LOCAL_ONLY", "NO_REMOTE"} and row.path is not None:
        if row.facts and row.facts.remotes:
            return PlannedOperation(
                type=OperationType.SKIP,
                name=row.name,
                risk=Risk.BLOCKED,
                reason="Remotes already exist; will not replace",
                preconditions=(),
                preview=("Blocked: existing remotes",),
                path=row.path,
            )
        return PlannedOperation(
            type=OperationType.PUBLISH,
            name=row.name,
            risk=Risk.WARNING,
            reason="Local project without GitHub remote",
            preconditions=("secret scan", "large file scan", "private default"),
            preview=("Create private GitHub repo", "add origin", "push"),
            path=row.path,
            visibility="private",
        )

    if primary == "LOCAL_AHEAD" and row.path is not None:
        risk = Risk.WARNING if ProjectFlag.UNCOMMITTED in flags else Risk.SAFE
        return PlannedOperation(
            type=OperationType.PUSH,
            name=row.name,
            risk=risk,
            reason="Local commits ahead of upstream",
            preconditions=("not diverged", "not detached", "upstream exists"),
            preview=("git push",),
            path=row.path,
            nwo=row.match.nwo,
        )

    if primary == "REMOTE_AHEAD" and row.path is not None:
        if ProjectFlag.UNCOMMITTED in flags:
            return PlannedOperation(
                type=OperationType.SKIP,
                name=row.name,
                risk=Risk.BLOCKED,
                reason="Dirty working tree; refuse pull",
                preconditions=("working tree clean",),
                preview=("Blocked: dirty tree",),
                path=row.path,
            )
        return PlannedOperation(
            type=OperationType.PULL,
            name=row.name,
            risk=Risk.SAFE,
            reason="Remote ahead; fast-forward possible",
            preconditions=("ahead == 0", "clean working tree", "ff-only"),
            preview=("git pull --ff-only",),
            path=row.path,
            nwo=row.match.nwo,
        )

    if primary == "SYNCED":
        return PlannedOperation(
            type=OperationType.SKIP,
            name=row.name,
            risk=Risk.SAFE,
            reason="Already synced",
            preconditions=(),
            preview=("No write needed",),
            path=row.path,
            nwo=row.match.nwo,
        )

    return PlannedOperation(
        type=OperationType.SKIP,
        name=row.name,
        risk=Risk.SAFE,
        reason="No suggested write operation",
        preconditions=(),
        preview=("Skip",),
        path=row.path,
        nwo=row.match.nwo,
    )


def plan_operations(rows: list[ProjectStatusRow]) -> list[PlannedOperation]:
    return [suggest_operation(row) for row in rows]


def format_plan_preview(operations: list[PlannedOperation]) -> str:
    if not operations:
        return "No operations planned."

    counts = {
        "Would push": 0,
        "Would pull": 0,
        "Would publish": 0,
        "Would clone": 0,
        "Would init": 0,
        "Blocked": 0,
        "Skipped": 0,
    }
    lines = ["OPERATION PREVIEW", ""]
    for op in operations:
        if op.risk == Risk.BLOCKED:
            counts["Blocked"] += 1
        elif op.type == OperationType.PUSH:
            counts["Would push"] += 1
        elif op.type == OperationType.PULL:
            counts["Would pull"] += 1
        elif op.type == OperationType.PUBLISH:
            counts["Would publish"] += 1
        elif op.type == OperationType.CLONE:
            counts["Would clone"] += 1
        elif op.type == OperationType.INIT_GIT:
            counts["Would init"] += 1
        else:
            counts["Skipped"] += 1
        lines.append(f"{op.type:<10} {op.risk:<8} {op.name} — {op.reason}")

    lines.append("")
    for label, value in counts.items():
        if value:
            lines.append(f"{label}: {value}")
    lines.append("")
    lines.append("Dry-run: no Git refs, GitHub, or config were changed.")
    return "\n".join(lines)


def open_github_allowed(row: ProjectStatusRow) -> bool:
    return bool(
        row.match.nwo
        and row.match.confidence
        in {MatchConfidence.EXACT_REMOTE, MatchConfidence.EXACT_LIST}
    )
