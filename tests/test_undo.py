"""Tests undo (last-op.json + restauration)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import engine
from config import reset_settings_cache
from engine import (
    commit_add,
    commit_remove,
    plan_add,
    plan_remove,
    undo_last_write,
)
from nixpick import main

SAMPLE_NIX = """{ config, pkgs, ... }:
{
  environment.systemPackages = with pkgs; [
    firefox
    vim
  ];
}
"""


@pytest.fixture
def nix_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pkg = tmp_path / "packages.nix"
    pkg.write_text(SAMPLE_NIX, encoding="utf-8")
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    monkeypatch.setenv("NIXPICK_PACKAGES_ANCHOR", "environment.systemPackages")
    monkeypatch.setattr(engine, "CACHE_DIR", cache)
    monkeypatch.setattr(engine, "LAST_OP_FILE", cache / "last-op.json")
    reset_settings_cache()
    return pkg


def test_undo_restores_after_add(nix_env: Path) -> None:
    before = nix_env.read_text(encoding="utf-8")
    plan = plan_add("htop", "moniteur")
    assert not hasattr(plan, "outcome")
    commit_add(plan)
    assert "htop" in nix_env.read_text(encoding="utf-8")
    assert engine.LAST_OP_FILE.is_file()

    result = undo_last_write()
    assert result.code == 0
    assert result.stdout
    assert nix_env.read_text(encoding="utf-8") == before
    assert not engine.LAST_OP_FILE.exists()


def test_undo_restores_after_remove(nix_env: Path) -> None:
    before = nix_env.read_text(encoding="utf-8")
    plan = plan_remove("vim")
    assert not hasattr(plan, "outcome")
    commit_remove(plan)
    assert "vim" not in nix_env.read_text(encoding="utf-8")

    result = undo_last_write()
    assert result.code == 0
    assert nix_env.read_text(encoding="utf-8") == before


def test_undo_without_record(nix_env: Path) -> None:
    _ = nix_env
    result = undo_last_write()
    assert result.code == 1
    assert "Aucune" in result.stderr


def test_dry_run_does_not_record_last_op(nix_env: Path) -> None:
    plan = plan_add("htop", "")
    assert not hasattr(plan, "outcome")
    commit_add(plan, dry_run=True)
    assert not engine.LAST_OP_FILE.exists()


def test_undo_missing_backup(nix_env: Path, tmp_path: Path) -> None:
    missing = tmp_path / "packages.nix.bak.19990101-000000"
    engine.LAST_OP_FILE.write_text(
        json.dumps(
            {
                "timestamp": 1.0,
                "op": "add",
                "attr": "htop",
                "backup_path": str(missing),
                "packages_file": str(nix_env),
            }
        ),
        encoding="utf-8",
    )
    result = undo_last_write()
    assert result.code == 1
    assert "introuvable" in result.stderr.lower()


def test_undo_wrong_packages_file(nix_env: Path, tmp_path: Path) -> None:
    backup = nix_env.with_name("packages.nix.bak.test")
    backup.write_text(nix_env.read_text(encoding="utf-8"), encoding="utf-8")
    other = tmp_path / "other.nix"
    engine.LAST_OP_FILE.write_text(
        json.dumps(
            {
                "timestamp": 1.0,
                "op": "add",
                "attr": "htop",
                "backup_path": str(backup),
                "packages_file": str(other),
            }
        ),
        encoding="utf-8",
    )
    result = undo_last_write()
    assert result.code == 1
    assert "autre fichier" in result.stderr.lower()


def test_undo_cli_exit_code(nix_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = plan_add("htop", "")
    assert not hasattr(plan, "outcome")
    commit_add(plan)
    monkeypatch.setattr("sys.argv", ["nixpick", "--undo"])
    assert main() == 0
