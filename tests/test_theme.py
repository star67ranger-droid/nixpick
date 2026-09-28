"""Tests chargement des couleurs."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import reset_settings_cache
from rofi_theme import sync_rofi_themes
from theme import load_color_palette, reset_color_palette_cache


def test_default_palette() -> None:
    pal = load_color_palette()
    # Un seul accent (bleu zinc) : vert / rouge / ambre = états seuls.
    assert pal.tui.primary == "#7ba4e0"
    assert pal.tui.background == "#17181c"
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
    reset_settings_cache()
    reset_color_palette_cache()
    pal = load_color_palette()
    assert pal.tui.primary == "#ff00ff"
    assert pal.tui.accent == "#8ab7ea"


def test_invalid_color_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('[colors]\nprimary = "red"\n', encoding="utf-8")
    monkeypatch.setattr("config.CONFIG_FILE", cfg)
    reset_color_palette_cache()
    with pytest.raises(ValueError, match="invalide"):
        load_color_palette()


def test_sync_rofi_writes_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rofi_theme.CONFIG_DIR", tmp_path)
    paths = sync_rofi_themes()
    assert len(paths) == 2
    assert paths[0].exists()
    assert "#271d1b" in paths[0].read_text(encoding="utf-8")


def test_sync_rofi_skips_rewrite_when_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UX-08 : ne pas réécrire (mtime) un thème dont le contenu est identique."""
    import os

    monkeypatch.setattr("rofi_theme.CONFIG_DIR", tmp_path)
    paths = sync_rofi_themes()
    first = os.stat(paths[0]).st_mtime_ns
    sync_rofi_themes()
    assert os.stat(paths[0]).st_mtime_ns == first
    assert not list((tmp_path / "rofi").glob(".*.tmp"))
