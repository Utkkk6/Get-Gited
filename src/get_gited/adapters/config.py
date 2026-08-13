"""TOML configuration load and path resolution."""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Invalid or unreadable configuration."""


@dataclass(frozen=True, slots=True)
class WorkspaceRootConfig:
    path: Path
    profile: str | None = None
    default_visibility: str = "private"


@dataclass(frozen=True, slots=True)
class ScanConfig:
    max_depth: int = 6


@dataclass(frozen=True, slots=True)
class IgnoreConfig:
    paths: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class PrivacyConfig:
    infer_about: bool = False


@dataclass(frozen=True, slots=True)
class UiConfig:
    theme: str = "minimal"


@dataclass(frozen=True, slots=True)
class AppConfig:
    roots: tuple[WorkspaceRootConfig, ...] = ()
    scan: ScanConfig = field(default_factory=ScanConfig)
    ignore: IgnoreConfig = field(default_factory=IgnoreConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    source_path: Path | None = None
    exists: bool = False


def default_config_path(
    *,
    appdata: Path | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    """Return the default config.toml path for the current platform.

    Injectable path bases keep this pure and testable without touching the
    real user profile.
    """

    plat = (platform or sys.platform).lower()
    if plat.startswith("win"):
        base = appdata
        if base is None:
            env = os.environ.get("APPDATA")
            base = Path(env) if env else Path.home() / "AppData" / "Roaming"
        return base / "get-gited" / "config.toml"

    cfg_home = home if home is not None else Path.home()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if home is None and xdg:
        return Path(xdg) / "get-gited" / "config.toml"
    return cfg_home / ".config" / "get-gited" / "config.toml"


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from ``path`` or the platform default.

    Missing file → empty defaults (``exists=False``).
    Malformed TOML or invalid shape → ``ConfigError``.
    """

    config_path = path if path is not None else default_config_path()
    if not config_path.is_file():
        return AppConfig(source_path=config_path, exists=False)

    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Cannot read config: {config_path}: {exc}") from exc

    try:
        data = tomllib.loads(raw_text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a table: {config_path}")

    return _parse_config(data, config_path)


def _parse_config(data: dict[str, Any], source_path: Path) -> AppConfig:
    roots_raw = data.get("roots", [])
    if roots_raw is None:
        roots_raw = []
    if not isinstance(roots_raw, list):
        raise ConfigError("roots must be an array of tables")

    roots: list[WorkspaceRootConfig] = []
    for index, item in enumerate(roots_raw):
        if not isinstance(item, dict):
            raise ConfigError(f"roots[{index}] must be a table")
        path_value = item.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            raise ConfigError(f"roots[{index}].path must be a non-empty string")
        visibility = item.get("default_visibility", "private")
        if visibility not in {"private", "public"}:
            raise ConfigError(
                f"roots[{index}].default_visibility must be 'private' or 'public'"
            )
        profile = item.get("profile")
        if profile is not None and not isinstance(profile, str):
            raise ConfigError(f"roots[{index}].profile must be a string")
        roots.append(
            WorkspaceRootConfig(
                path=Path(path_value),
                profile=profile,
                default_visibility=visibility,
            )
        )

    scan_raw = data.get("scan", {})
    if scan_raw is None:
        scan_raw = {}
    if not isinstance(scan_raw, dict):
        raise ConfigError("scan must be a table")
    max_depth = scan_raw.get("max_depth", 6)
    if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth < 1:
        raise ConfigError("scan.max_depth must be a positive integer")

    ignore_raw = data.get("ignore", {})
    if ignore_raw is None:
        ignore_raw = {}
    if not isinstance(ignore_raw, dict):
        raise ConfigError("ignore must be a table")
    paths_raw = ignore_raw.get("paths", [])
    if paths_raw is None:
        paths_raw = []
    if not isinstance(paths_raw, list) or not all(
        isinstance(p, str) for p in paths_raw
    ):
        raise ConfigError("ignore.paths must be an array of strings")

    privacy_raw = data.get("privacy", {})
    if privacy_raw is None:
        privacy_raw = {}
    if not isinstance(privacy_raw, dict):
        raise ConfigError("privacy must be a table")
    infer_about = privacy_raw.get("infer_about", False)
    if not isinstance(infer_about, bool):
        raise ConfigError("privacy.infer_about must be a boolean")

    ui_raw = data.get("ui", {})
    if ui_raw is None:
        ui_raw = {}
    if not isinstance(ui_raw, dict):
        raise ConfigError("ui must be a table")
    theme = ui_raw.get("theme", "minimal")
    if not isinstance(theme, str) or not theme.strip():
        raise ConfigError("ui.theme must be a string")
    theme = theme.strip().lower()
    allowed = {"frame", "minimal", "hud", "cards", "poster"}
    if theme not in allowed:
        raise ConfigError("ui.theme must be frame, minimal, hud, cards, or poster")

    return AppConfig(
        roots=tuple(roots),
        scan=ScanConfig(max_depth=max_depth),
        ignore=IgnoreConfig(paths=tuple(Path(p) for p in paths_raw)),
        privacy=PrivacyConfig(infer_about=infer_about),
        ui=UiConfig(theme=theme),
        source_path=source_path,
        exists=True,
    )


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    """Persist config as TOML. Creates parent directories as needed."""

    import tomli_w

    target = path or config.source_path or default_config_path()
    payload: dict[str, Any] = {
        "roots": [
            {
                "path": str(root.path),
                **({"profile": root.profile} if root.profile else {}),
                "default_visibility": root.default_visibility,
            }
            for root in config.roots
        ],
        "scan": {"max_depth": config.scan.max_depth},
        "ignore": {"paths": [str(p) for p in config.ignore.paths]},
        "privacy": {"infer_about": config.privacy.infer_about},
        "ui": {"theme": config.ui.theme},
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(tomli_w.dumps(payload), encoding="utf-8")
    return target


def append_ignore_path(ignore_path: Path, config_path: Path | None = None) -> AppConfig:
    """Add a persistent ignore path and save config."""

    config = load_config(config_path)
    resolved = ignore_path.expanduser()
    existing = list(config.ignore.paths)
    if resolved not in existing and Path(str(resolved)) not in existing:
        # Compare as strings for Windows path forms
        existing_strs = {str(p) for p in existing}
        if str(resolved) not in existing_strs:
            existing.append(resolved)
    updated = AppConfig(
        roots=config.roots,
        scan=config.scan,
        ignore=IgnoreConfig(paths=tuple(existing)),
        privacy=config.privacy,
        ui=config.ui,
        source_path=config.source_path,
        exists=True,
    )
    save_config(updated, config.source_path)
    return updated


def set_ui_theme(theme: str, config_path: Path | None = None) -> AppConfig:
    """Persist the terminal UI theme. Explicit user action only."""

    allowed = {"frame", "minimal", "hud", "cards", "poster"}
    normalized = theme.strip().lower()
    if normalized not in allowed:
        raise ConfigError("ui.theme must be frame, minimal, hud, cards, or poster")

    config = load_config(config_path)
    updated = AppConfig(
        roots=config.roots,
        scan=config.scan,
        ignore=config.ignore,
        privacy=config.privacy,
        ui=UiConfig(theme=normalized),
        source_path=config.source_path,
        exists=True,
    )
    save_config(updated, config.source_path)
    return updated


def set_infer_about(enabled: bool, config_path: Path | None = None) -> AppConfig:
    """Persist About-column file-guess consent. Explicit user action only."""

    config = load_config(config_path)
    updated = AppConfig(
        roots=config.roots,
        scan=config.scan,
        ignore=config.ignore,
        privacy=PrivacyConfig(infer_about=enabled),
        ui=config.ui,
        source_path=config.source_path,
        exists=True,
    )
    save_config(updated, config.source_path)
    return updated
