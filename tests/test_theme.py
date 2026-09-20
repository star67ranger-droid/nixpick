"""Tests chargement des couleurs."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import CONFIG_FILE, reset_settings_cache
from theme import load_color_palette, reset_color_palette_cache
from rofi_theme import sync_rofi_themes


def test_default_palette() -> None:
    pal = load_color_palette()
    assert pal.tui.primary == "#57a5e5"
    assert pal.rofi.background == "#271d1b"


def test_custom_tui_color(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[colors]\nprimary = "#ff00ff"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("config.CONFIG_FILE", cfg)
    monkeypatch.setattr("theme.CONFIG_FILE", cfg)
    reset_settings_cache()
    reset_color_palette_cache()
    pal = load_color_palette()
    assert pal.tui.primary == "#ff00ff"
    assert pal.tui.accent == "#51a8b3"


def test_invalid_color_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('[colors]\nprimary = "red"\n', encoding="utf-8")
    monkeypatch.setattr("config.CONFIG_FILE", cfg)
    monkeypatch.setattr("theme.CONFIG_FILE", cfg)
    reset_color_palette_cache()
    with pytest.raises(ValueError, match="invalide"):
        load_color_palette()


def test_sync_rofi_writes_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rofi_theme.CONFIG_DIR", tmp_path)
    paths = sync_rofi_themes()
    assert len(paths) == 2
    assert paths[0].exists()
    assert "#271d1b" in paths[0].read_text(encoding="utf-8")
