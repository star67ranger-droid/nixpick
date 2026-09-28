"""Validation de config.toml et chemins CLI (--print-config)."""

from __future__ import annotations

from pathlib import Path

import pytest

import config
from config import ConfigError, get_settings, reset_settings_cache
from nixpick import main


@pytest.fixture(autouse=True)
def _reset_settings() -> None:
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_get_settings_rejects_non_nix_packages_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(tmp_path / "packages.txt"))
    with pytest.raises(ValueError, match=r"\.nix"):
        get_settings()


def test_get_settings_rejects_empty_rebuild_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = tmp_path / "packages.nix"
    pkg.write_text("{ config, pkgs, ... }: { environment.systemPackages = with pkgs; [ ]; }\n")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    monkeypatch.setenv("NIXPICK_REBUILD_COMMAND", "   ")
    with pytest.raises(ValueError, match="vide"):
        get_settings()


def test_get_settings_raises_config_error_on_invalid_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "config.toml"
    bad.write_text("[[[not-valid-toml", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_FILE", bad)
    with pytest.raises(ConfigError, match="TOML invalide"):
        get_settings()


def test_main_refuses_invalid_packages_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(tmp_path / "wrong.yaml"))
    monkeypatch.setattr("sys.argv", ["nixpick", "doctor"])
    assert main() == 1
    assert "packages_file" in capsys.readouterr().err


def test_print_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pkg = tmp_path / "packages.nix"
    pkg.write_text("{ config, pkgs, ... }: { environment.systemPackages = with pkgs; [ ]; }\n")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    monkeypatch.setenv("NIXPICK_PACKAGES_ANCHOR", "environment.systemPackages")
    monkeypatch.setenv("NIXPICK_REBUILD_COMMAND", "sudo nixos-rebuild switch")
    monkeypatch.setattr("sys.argv", ["nixpick", "--print-config"])
    assert main() == 0
    out = capsys.readouterr().out
    assert f"packages_file={pkg}" in out
    assert "rebuild_command=" in out
