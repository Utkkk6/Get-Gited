"""Config write / ignore persistence tests."""

from __future__ import annotations

from pathlib import Path

from get_gited.adapters.config import (
    AppConfig,
    IgnoreConfig,
    ScanConfig,
    WorkspaceRootConfig,
    append_ignore_path,
    load_config,
    save_config,
    set_infer_about,
    set_ui_theme,
)


def test_save_and_append_ignore(tmp_path: Path) -> None:
    path = tmp_path / "get-gited" / "config.toml"
    config = AppConfig(
        roots=(WorkspaceRootConfig(path=tmp_path / "Projects"),),
        scan=ScanConfig(max_depth=5),
        ignore=IgnoreConfig(),
        source_path=path,
        exists=False,
    )
    save_config(config, path)
    loaded = load_config(path)
    assert loaded.exists is True
    assert len(loaded.roots) == 1
    assert loaded.scan.max_depth == 5

    append_ignore_path(tmp_path / "archive", path)
    again = load_config(path)
    assert any(p.name == "archive" for p in again.ignore.paths)
    assert again.privacy.infer_about is False


def test_set_infer_about(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    granted = set_infer_about(True, path)
    assert granted.privacy.infer_about is True
    loaded = load_config(path)
    assert loaded.privacy.infer_about is True
    revoked = set_infer_about(False, path)
    assert revoked.privacy.infer_about is False
    assert revoked.ui.theme == "minimal"


def test_set_ui_theme(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    updated = set_ui_theme("hud", path)
    assert updated.ui.theme == "hud"
    loaded = load_config(path)
    assert loaded.ui.theme == "hud"
    assert loaded.privacy.infer_about is False
