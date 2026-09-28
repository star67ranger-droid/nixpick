"""Écriture packages.nix : concurrence logique et validation Nix."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import reset_settings_cache
from engine import (
    AddPlan,
    NixSyntaxError,
    commit_add,
    plan_add,
    validate_nix_syntax,
)

SAMPLE_NIX = """{ config, pkgs, ... }:
{
  environment.systemPackages = with pkgs; [
    firefox
  ];
}
"""


@pytest.fixture
def packages_nix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "packages.nix"
    path.write_text(SAMPLE_NIX, encoding="utf-8")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(path))
    monkeypatch.setenv("NIXPICK_PACKAGES_ANCHOR", "environment.systemPackages")
    reset_settings_cache()
    return path


def test_commit_add_raises_if_already_listed(packages_nix: Path) -> None:
    plan = plan_add("htop", "viewer")
    assert isinstance(plan, AddPlan)
    text = packages_nix.read_text(encoding="utf-8")
    packages_nix.write_text(text.replace("  ];\n", "    htop\n  ];\n"), encoding="utf-8")
    with pytest.raises(LookupError, match="déjà listé"):
        commit_add(plan, dry_run=False)


def test_validate_nix_syntax_skips_without_nix_instantiate(
    monkeypatch: pytest.MonkeyPatch, packages_nix: Path
) -> None:
    monkeypatch.setattr("engine.shutil.which", lambda _: None)
    assert validate_nix_syntax(packages_nix) is None


def test_commit_restores_backup_on_invalid_nix(
    packages_nix: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = plan_add("htop", "viewer")
    assert isinstance(plan, AddPlan)
    original = packages_nix.read_text(encoding="utf-8")

    def fake_validate(_path: Path) -> str | None:
        return "syntax error"

    monkeypatch.setattr("engine.validate_nix_syntax", fake_validate)
    with pytest.raises(NixSyntaxError):
        commit_add(plan, dry_run=False)
    assert packages_nix.read_text(encoding="utf-8") == original
