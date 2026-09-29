"""Hors NixOS : repli local + création du fichier au premier ajout."""

from __future__ import annotations

from pathlib import Path

import pytest

import config
import doctor
import engine
from config import get_settings, reset_settings_cache
from engine import AddOutcome


@pytest.fixture
def no_nixos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Simule une machine sans /etc/nixos et sans config existante."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Le shell de dev exporte NIXPICK_PACKAGES_FILE : le retirer pour tester
    # la résolution par défaut.
    monkeypatch.delenv("NIXPICK_PACKAGES_FILE", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr(config, "is_nixos", lambda: False)
    monkeypatch.setattr(engine, "is_nixos", lambda: False)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(engine, "CACHE_DIR", cache)
    monkeypatch.setattr(engine, "LAST_OP_FILE", cache / "last-op.json")
    reset_settings_cache()
    return home, tmp_path


def test_repli_local_hors_nixos(no_nixos: tuple[Path, Path]) -> None:
    home, _tmp = no_nixos
    assert get_settings().packages_file == (
        home / ".config" / "nixpick" / "packages.nix"
    )


def test_defaut_nixos_inchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr(config, "is_nixos", lambda: True)
    reset_settings_cache()
    assert get_settings().packages_file == Path("/etc/nixos/modules/packages.nix")


def test_plan_add_cree_le_squelette(
    no_nixos: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    home, _tmp = no_nixos
    plan = engine.plan_add("htop", "")
    assert not isinstance(plan, engine.AddFailure)
    assert plan.created_file is True
    target = home / ".config" / "nixpick" / "packages.nix"
    assert target.exists()
    assert "environment.systemPackages = with pkgs;" in target.read_text(
        encoding="utf-8"
    )
    engine.commit_add(plan, dry_run=False)
    assert "htop" in engine.list_installed_attrs()
    again = engine.plan_add("htop", "")
    assert isinstance(again, engine.AddFailure)
    assert again.outcome == AddOutcome.ALREADY_LISTED


def test_plan_add_fichier_manquant_sur_nixos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nixos" / "packages.nix"
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(missing))
    monkeypatch.setattr(config, "is_nixos", lambda: True)
    monkeypatch.setattr(engine, "is_nixos", lambda: True)
    reset_settings_cache()
    plan = engine.plan_add("htop", "")
    assert isinstance(plan, engine.AddFailure)
    assert plan.outcome == AddOutcome.FILE_MISSING
    assert not missing.exists()


def test_plan_remove_ne_cree_rien(
    no_nixos: tuple[Path, Path],
) -> None:
    home, _tmp = no_nixos
    plan = engine.plan_remove("htop")
    assert isinstance(plan, engine.RemoveFailure)
    assert plan.outcome == engine.RemoveOutcome.FILE_MISSING
    assert not (home / ".config" / "nixpick" / "packages.nix").exists()


def test_doctor_annonce_creation_hors_nixos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "packages.nix"
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(missing))
    monkeypatch.setattr(doctor, "is_nixos", lambda: False)
    reset_settings_cache()
    check = doctor._check_packages_file()
    assert check.ok is True
    assert "créé au premier ajout" in check.detail
