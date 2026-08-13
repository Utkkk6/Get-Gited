"""Config path resolution and loading tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from get_gited.adapters.config import ConfigError, default_config_path, load_config


def test_default_config_path_windows() -> None:
    path = default_config_path(
        appdata=Path(r"C:\Users\User\AppData\Roaming"),
        platform="win32",
    )
    assert path == Path(r"C:\Users\User\AppData\Roaming\get-gited\config.toml")


def test_default_config_path_posix() -> None:
    path = default_config_path(home=Path("/home/dev"), platform="linux")
    assert path == Path("/home/dev/.config/get-gited/config.toml")


def test_missing_config_uses_defaults(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    config = load_config(missing)
    assert config.exists is False
    assert config.roots == ()
    assert config.scan.max_depth == 6
    assert config.ignore.paths == ()
    assert config.privacy.infer_about is False
    assert config.ui.theme == "minimal"
    assert config.source_path == missing


def test_valid_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        "\n".join(
            [
                "[[roots]]",
                'path = "D:\\\\Personal"',
                'profile = "personal"',
                'default_visibility = "private"',
                "",
                "[scan]",
                "max_depth = 4",
                "",
                "[ignore]",
                'paths = ["D:\\\\Projects\\\\archive"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.exists is True
    assert len(config.roots) == 1
    assert config.roots[0].path == Path(r"D:\Personal")
    assert config.roots[0].profile == "personal"
    assert config.roots[0].default_visibility == "private"
    assert config.scan.max_depth == 4
    assert config.ignore.paths == (Path(r"D:\Projects\archive"),)


def test_malformed_toml(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("[[roots]\npath = ", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_config(path)


def test_invalid_visibility(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[[roots]]\npath = "D:\\\\Code"\ndefault_visibility = "secret"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="default_visibility"):
        load_config(path)


def test_missing_root_path(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[[roots]]\nprofile = "personal"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="path"):
        load_config(path)


def test_invalid_ui_theme(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[ui]\ntheme = "neon"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="ui.theme"):
        load_config(path)
