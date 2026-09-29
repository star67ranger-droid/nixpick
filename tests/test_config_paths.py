"""Résolution du fichier packages par défaut (NixOS vs hors NixOS)."""

from __future__ import annotations

from pathlib import Path

import pytest

import config
from config import (
    default_packages_file,
    fallback_packages_file,
    get_settings,
    reset_settings_cache,
)


def test_fallback_packages_file_sous_home() -> None:
    path = fallback_packages_file()
    assert path == Path.home() / ".config" / "nixpick" / "packages.nix"
    assert path.suffix == ".nix"


def test_default_packages_file_selon_nixos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr(config, "is_nixos", lambda: True)
    reset_settings_cache()
    assert default_packages_file() == config.DEFAULT_PACKAGES_FILE

    monkeypatch.setattr(config, "is_nixos", lambda: False)
    reset_settings_cache()
    assert default_packages_file() == fallback_packages_file()


def test_env_packages_file_prime_sur_defaut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = tmp_path / "custom.nix"
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(custom))
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    reset_settings_cache()
    assert get_settings().packages_file == custom.resolve()
