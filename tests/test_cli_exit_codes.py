"""Codes de sortie du CLI (audit TST-01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import reset_settings_cache
from nixpick import main


@pytest.fixture
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pkg = tmp_path / "packages.nix"
    pkg.write_text(
        "{ config, pkgs, ... }:\n"
        "{ environment.systemPackages = with pkgs; [ ]; }\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    monkeypatch.setenv("NIXPICK_PACKAGES_ANCHOR", "environment.systemPackages")
    reset_settings_cache()
    return pkg


def test_remove_sans_termne_renvoie_2(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sans terme, `--remove` tombait dans la TUI au lieu de refuser."""
    monkeypatch.setattr("sys.argv", ["nixpick", "--remove"])
    assert main() == 2
    err = capsys.readouterr().err
    assert "--remove" in err and "terme" in err


def test_rofi_sans_rofi_renvoie_1(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """rofi absent : code 1 + explication, pas un faux succès (exit 0)."""
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("sys.argv", ["nixpick", "--rofi"])
    assert main() == 1
    assert "rofi introuvable" in capsys.readouterr().err
