"""Typer CLI for Get Gited."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from get_gited import __version__
from get_gited.adapters.command import SubprocessCommandRunner
from get_gited.adapters.config import (
    AppConfig,
    ConfigError,
    load_config,
    set_infer_about,
    set_ui_theme,
)
from get_gited.application.brand import (
    UiTheme,
    format_quit_screen,
    format_ui_menu,
    parse_ui_theme,
)
from get_gited.application.consent import format_acpt_status
from get_gited.application.doctor import format_doctor_report, run_doctor
from get_gited.application.executor import Executor, format_sync_report
from get_gited.application.planner import format_plan_preview, plan_operations
from get_gited.application.scan import format_scan_table, scan_projects
from get_gited.application.selection import (
    format_preview_screen,
    parse_preview_input,
    run_workspace_picker,
)
from get_gited.application.shortcut import parse_gg_argv
from get_gited.application.sort import SortMode, parse_sort_mode, sort_rows
from get_gited.application.status import (
    collect_workspace_status,
    format_status_table,
)
from get_gited.application.sync import run_sync
from get_gited.application.terminal import render_screen, terminal_columns
from get_gited.tui import run_tui

app = typer.Typer(
    name="get-gited",
    help="Get Gited - one workspace. All your Git repos.",
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
    context_settings={"help_option_names": ["--help", "-h"]},
)

GG_USAGE = """\
Get Gited short command (gg)

  gg                 Offer the current folder, then sort + select [*]
  gg PATH            Scan PATH, then sort + select [*]
  gg -y / gg --yes   Scan the current folder and show everything with [*]
  gg acpt --help     About-column file-guess consent (off by default)
  gg ui              Pick a terminal look (5 themes)
  gg ui 2            Select look by number (1-5)
  gg ui cards        Select look by name
  gg status PATH     Same as get-gited status PATH
  gg scan | doctor | sync ...
"""

SORT_HELP = "Sort rows: mtime, sync, presence, size, or scan."


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"get-gited {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Get Gited CLI. With no subcommand, opens the workspace TUI."""

    if ctx.invoked_subcommand is None:
        run_tui()


@app.command("doctor")
def doctor_command() -> None:
    """Check local toolchain, GitHub CLI auth, and config readability."""

    report = run_doctor(SubprocessCommandRunner())
    typer.echo(format_doctor_report(report))
    raise typer.Exit(code=0 if report.ok else 1)


@app.command("acpt")
def acpt_command(
    on: Annotated[
        bool,
        typer.Option("--on", "--grant", help="Grant About-column file-guess consent."),
    ] = False,
    off: Annotated[
        bool,
        typer.Option(
            "--off",
            "--revoke",
            help="Revoke About-column file-guess consent.",
        ),
    ] = False,
) -> None:
    """Consent for About-column file guesses (off by default).

    Default is OFF. About is a README excerpt or a dash. Other project
    files are not read unless you grant consent:

        gg acpt --on

    Revoke with gg acpt --off. Full explanation: gg acpt --help
    """

    if on and off:
        typer.echo("Use either --on or --off, not both.", err=True)
        raise typer.Exit(code=1)
    try:
        if on:
            config = set_infer_about(True)
            typer.echo(
                "Granted. About may use public manifests when README is missing."
            )
            typer.echo(f"Wrote {config.source_path}")
            raise typer.Exit(code=0)
        if off:
            config = set_infer_about(False)
            typer.echo("Revoked. About is README or —.")
            typer.echo(f"Wrote {config.source_path}")
            raise typer.Exit(code=0)
        config = load_config()
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    path = config.source_path
    typer.echo(
        format_acpt_status(
            granted=config.privacy.infer_about,
            config_path=path if path is not None else Path("config.toml"),
        )
    )


@app.command("ui")
def ui_command(
    theme: Annotated[
        str | None,
        typer.Argument(help="Look: 1-5, or frame, minimal, hud, cards, poster."),
    ] = None,
) -> None:
    """Pick a terminal look for the [*] picker.

    Default is minimal (wide table, leftover width goes to About).
    The original boxed chrome is theme 1 / frame. Switch live with u1-u5.
    """

    try:
        config = load_config()
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    current = parse_ui_theme(config.ui.theme) or UiTheme.MINIMAL
    if theme is None:
        typer.echo(format_ui_menu(current))
        raise typer.Exit(code=0)

    parsed = parse_ui_theme(theme)
    if parsed is None:
        typer.echo(
            "Unknown UI. Use 1-5 or frame, minimal, hud, cards, poster.",
            err=True,
        )
        raise typer.Exit(code=1)
    try:
        updated = set_ui_theme(parsed.value)
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"UI set to {parsed}.")
    typer.echo(f"Wrote {updated.source_path}")
    raise typer.Exit(code=0)


@app.command("scan")
def scan_command(
    roots: Annotated[
        list[Path] | None,
        typer.Argument(help="Workspace root directories (overrides config roots)."),
    ] = None,
) -> None:
    """Discover local projects under workspace roots."""

    try:
        config = load_config()
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    cli_roots = list(roots) if roots else None
    if not cli_roots and not config.roots:
        typer.echo(
            "No workspace roots. Pass directories to `get-gited scan` "
            "or add [[roots]] in the config file."
        )
        raise typer.Exit(code=1)

    projects = scan_projects(cli_roots, config=config)
    typer.echo(format_scan_table(projects))


@app.command("status")
def status_command(
    roots: Annotated[
        list[Path] | None,
        typer.Argument(help="Workspace root directories (overrides config roots)."),
    ] = None,
    sort: Annotated[
        str | None,
        typer.Option("--sort", help=SORT_HELP),
    ] = None,
) -> None:
    """Show local Git status for discovered projects."""

    try:
        config = load_config()
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    cli_roots = list(roots) if roots else None
    if not cli_roots and not config.roots:
        typer.echo(
            "No workspace roots. Pass directories to `get-gited status` "
            "or add [[roots]] in the config file."
        )
        raise typer.Exit(code=1)

    rows = collect_workspace_status(
        SubprocessCommandRunner(),
        cli_roots,
        config=config,
        include_github=True,
    )
    mode = _require_sort_mode(sort)
    if mode is not None and mode is not SortMode.SCAN:
        rows = sort_rows(rows, mode)
    typer.echo(format_status_table(rows))


@app.command("sync")
def sync_command(
    roots: Annotated[
        list[Path] | None,
        typer.Argument(help="Workspace root directories (overrides config roots)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview operations without changing anything."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Execute the full plan without interactive selection.",
        ),
    ] = False,
    sort: Annotated[
        str | None,
        typer.Option("--sort", help=SORT_HELP),
    ] = None,
) -> None:
    """Plan and optionally execute safe workspace sync operations."""

    try:
        config = load_config()
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    cli_roots = list(roots) if roots else None
    if not cli_roots and not config.roots:
        typer.echo(
            "No workspace roots. Pass directories to `get-gited sync` "
            "or add [[roots]] in the config file."
        )
        raise typer.Exit(code=1)

    runner = SubprocessCommandRunner()
    mode = _require_sort_mode(sort)
    if dry_run:
        _ops, _results, text = run_sync(runner, cli_roots, dry_run=True, config=config)
        typer.echo(text)
        raise typer.Exit(code=0)

    if not yes and _is_interactive():
        _run_interactive_session(
            runner,
            cli_roots,
            sort_mode=mode,
            ask_sort=mode is None,
        )
        return

    if not yes:
        _ops, _results, preview = run_sync(
            runner, cli_roots, dry_run=True, config=config
        )
        typer.echo(preview)
        typer.echo("")
        typer.echo("Re-run with --yes to execute, or use --dry-run only.")
        raise typer.Exit(code=0)

    _ops, results, text = run_sync(runner, cli_roots, dry_run=False, config=config)
    typer.echo(text)
    failed = any(r.status == "failed" for r in results)
    raise typer.Exit(code=1 if failed else 0)


def run() -> None:
    """Console-script entrypoint."""

    app()


def run_gg() -> None:
    """Short ``gg`` entrypoint: path-first shortcuts plus full commands."""

    try:
        _run_gg()
    except typer.Exit as exc:
        raise SystemExit(exc.exit_code) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None


def _run_gg() -> None:
    request = parse_gg_argv(sys.argv[1:], cwd=Path.cwd())
    if request.mode == "error":
        typer.echo(request.error, err=True)
        raise typer.Exit(code=1)
    if request.mode == "passthrough":
        if request.passthrough and request.passthrough[0] in {"--help", "-h"}:
            typer.echo(GG_USAGE)
        sys.argv = [sys.argv[0], *request.passthrough]
        app()
        return

    if request.mode == "prompt":
        root = _offer_current_folder(request.roots[0] if request.roots else Path.cwd())
        if root is None:
            raise typer.Exit(code=0)
        roots = [root]
    else:
        roots = [path.expanduser() for path in request.roots]

    try:
        config = load_config()
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    runner = SubprocessCommandRunner()
    _run_interactive_session(
        runner,
        roots,
        sort_mode=request.sort,
        ask_sort=request.sort is None,
        config=config,
    )


def _run_interactive_session(
    runner: SubprocessCommandRunner,
    cli_roots: list[Path] | None,
    *,
    sort_mode: SortMode | None,
    ask_sort: bool,
    config: AppConfig | None = None,
) -> None:
    cfg = config if config is not None else load_config()
    rows = collect_workspace_status(
        runner,
        cli_roots,
        config=cfg,
        include_github=True,
    )
    if not _is_interactive():
        typer.echo(format_status_table(rows))
        typer.echo("Interactive selection requires a terminal.")
        raise typer.Exit(code=1)

    sort_mode = sort_mode
    ask = ask_sort
    selected_keys: set[str] | None = None
    infer = cfg.privacy.infer_about
    look = parse_ui_theme(cfg.ui.theme) or UiTheme.MINIMAL

    def persist_theme(theme: UiTheme) -> None:
        set_ui_theme(theme.value)

    while True:
        outcome = run_workspace_picker(
            rows,
            read_line=input,
            show=render_screen,
            sort_mode=sort_mode,
            ask_sort=ask,
            selected_keys=selected_keys,
            infer=infer,
            theme=look,
            on_theme=persist_theme,
            columns=terminal_columns,
        )
        if outcome.status == "quit":
            render_screen(format_quit_screen(outcome.theme, terminal_columns()))
            raise typer.Exit(code=0)

        ops = plan_operations(list(outcome.rows))
        preview = format_preview_screen(
            format_plan_preview(ops),
            len(outcome.rows),
            theme=outcome.theme,
            width=terminal_columns(),
        )
        while True:
            render_screen(preview)
            action = parse_preview_input(input("Action: "))
            if action == "error":
                preview = format_preview_screen(
                    format_plan_preview(ops),
                    len(outcome.rows),
                    theme=outcome.theme,
                    width=terminal_columns(),
                )
                preview += "\n\n[Enter] - execute\nq - back\ne - exit"
                continue
            if action == "back":
                sort_mode = outcome.sort_mode
                ask = False
                selected_keys = set(outcome.selected_keys)
                infer = outcome.infer
                look = outcome.theme
                break
            if action == "quit":
                render_screen(format_quit_screen(outcome.theme, terminal_columns()))
                raise typer.Exit(code=0)
            results = Executor(runner).execute_many(ops, dry_run=False)
            render_screen(format_sync_report(results))
            failed = any(result.status == "failed" for result in results)
            raise typer.Exit(code=1 if failed else 0)


def _offer_current_folder(cwd: Path) -> Path | None:
    typer.echo("No path given. Use current folder?")
    typer.echo(f"  {cwd}")
    raw = input("[Y/n] or another path: ").strip()
    if raw == "" or raw.lower() in {"y", "yes"}:
        return cwd
    if raw.lower() in {"n", "no", "q", "quit"}:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.exists():
        typer.echo(f"Path not found: {candidate}", err=True)
        return None
    return candidate


def _require_sort_mode(value: str | None) -> SortMode | None:
    if value is None:
        return None
    mode = parse_sort_mode(value)
    if mode is None:
        typer.echo(
            "Unknown --sort value. Use mtime, sync, presence, size, or scan.",
            err=True,
        )
        raise typer.Exit(code=1)
    return mode


def _is_interactive() -> bool:
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


if __name__ == "__main__":
    run()
