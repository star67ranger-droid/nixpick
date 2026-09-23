"""Tests fix-git (git temporaire)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from config import reset_settings_cache
from fix_git_runner import run_fix_git


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def flake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "nixos"
    root.mkdir()
    _git(root, "init")
    (root / "flake.nix").write_text("{ outputs = _: {}; }\n", encoding="utf-8")
    (root / "flake.lock").write_text('{"version": 0, "nodes": {}}\n', encoding="utf-8")
    modules = root / "modules"
    modules.mkdir()
    pkg = modules / "packages.nix"
    pkg.write_text(
        '{ config, pkgs, ... }:\n{ environment.systemPackages = with pkgs; [ ]; }\n',
        encoding="utf-8",
    )
    _git(root, "add", "flake.nix", "flake.lock", "modules/packages.nix")
    _git(root, "commit", "-m", "init")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    reset_settings_cache()
    return root


def test_fix_git_dry_run(flake_repo: Path) -> None:
    (flake_repo / "dotfiles" / "new.nix").parent.mkdir(parents=True)
    (flake_repo / "dotfiles" / "new.nix").write_text("", encoding="utf-8")
    assert run_fix_git(dry_run=True) == 0


def test_fix_git_yes_stages(flake_repo: Path) -> None:
    path = flake_repo / "dotfiles" / "new.nix"
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    assert run_fix_git(yes=True) == 0
    proc = subprocess.run(
        ["git", "-C", str(flake_repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "A  dotfiles/new.nix" in proc.stdout or "A dotfiles/new.nix" in proc.stdout


def test_fix_git_clean(flake_repo: Path) -> None:
    assert run_fix_git(yes=True) == 0


def test_fix_git_no_tty(flake_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (flake_repo / "x.nix").write_text("", encoding="utf-8")
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert run_fix_git(yes=False) == 1
