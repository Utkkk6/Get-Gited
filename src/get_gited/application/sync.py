"""Sync application: plan + dry-run + execute."""

from __future__ import annotations

from pathlib import Path

from get_gited.adapters.command import CommandRunner
from get_gited.adapters.config import AppConfig, load_config
from get_gited.application.executor import Executor, format_sync_report
from get_gited.application.planner import format_plan_preview, plan_operations
from get_gited.application.status import collect_workspace_status
from get_gited.domain.operations import (
    OperationResult,
    OperationType,
    PlannedOperation,
)


def build_sync_plan(
    runner: CommandRunner,
    cli_roots: list[Path] | None = None,
    *,
    config: AppConfig | None = None,
    clone_root: Path | None = None,
) -> list[PlannedOperation]:
    cfg = config if config is not None else load_config()
    rows = collect_workspace_status(runner, cli_roots, config=cfg, include_github=True)
    ops = plan_operations(rows)
    dest_root = clone_root
    if dest_root is None and cfg.roots:
        dest_root = cfg.roots[0].path
    if dest_root is None and cli_roots:
        dest_root = cli_roots[0]

    filled: list[PlannedOperation] = []
    for op in ops:
        if (
            op.type == OperationType.CLONE
            and op.destination is None
            and dest_root
            and op.nwo
        ):
            filled.append(
                PlannedOperation(
                    type=op.type,
                    name=op.name,
                    risk=op.risk,
                    reason=op.reason,
                    preconditions=op.preconditions,
                    preview=op.preview,
                    path=op.path,
                    nwo=op.nwo,
                    destination=dest_root / op.name,
                    visibility=op.visibility,
                )
            )
        else:
            filled.append(op)
    return filled


def run_sync(
    runner: CommandRunner,
    cli_roots: list[Path] | None = None,
    *,
    dry_run: bool = False,
    config: AppConfig | None = None,
) -> tuple[list[PlannedOperation], list[OperationResult], str]:
    ops = build_sync_plan(runner, cli_roots, config=config)
    if dry_run:
        return ops, [], format_plan_preview(ops)

    executor = Executor(runner)
    results = executor.execute_many(ops, dry_run=False)
    return ops, results, format_sync_report(results)
