"""Scan workspace roots for local projects."""

from __future__ import annotations

from pathlib import Path

from get_gited.adapters.config import AppConfig, load_config
from get_gited.adapters.fs import LocalProject, discover_projects


def resolve_scan_roots(
    cli_roots: list[Path] | None,
    config: AppConfig | None = None,
) -> list[Path]:
    """Prefer explicit CLI roots; otherwise use config roots."""

    if cli_roots:
        return list(cli_roots)
    cfg = config if config is not None else load_config()
    return [root.path for root in cfg.roots]


def scan_projects(
    cli_roots: list[Path] | None = None,
    *,
    config: AppConfig | None = None,
    config_path: Path | None = None,
) -> list[LocalProject]:
    """Load config (if needed) and discover projects."""

    cfg = config
    if cfg is None:
        cfg = load_config(config_path)

    roots = resolve_scan_roots(cli_roots, cfg)
    if not roots:
        return []

    return discover_projects(
        roots,
        ignore_paths=list(cfg.ignore.paths),
        max_depth=cfg.scan.max_depth,
    )


def format_scan_table(projects: list[LocalProject]) -> str:
    if not projects:
        return "No projects found."

    name_width = max(len("Project"), max(len(p.name) for p in projects))
    path_width = max(len("Path"), max(len(str(p.path)) for p in projects))
    header = f"{'Project':<{name_width}}  {'Path':<{path_width}}  Git"
    lines = [header, f"{'-' * name_width}  {'-' * path_width}  ---"]
    for project in projects:
        git = "yes" if project.has_git_dir else "no"
        lines.append(
            f"{project.name:<{name_width}}  {str(project.path):<{path_width}}  {git}"
        )
    lines.append("")
    lines.append(f"Projects: {len(projects)}")
    return "\n".join(lines)
