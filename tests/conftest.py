"""Fixtures partagées (git identité pour CI et environnements sans config globale)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from config import reset_settings_cache


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def flake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "nixos"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "nixpick@test.local")
    git(root, "config", "user.name", "nixpick")
    (root / "flake.nix").write_text("{ outputs = _: {}; }\n", encoding="utf-8")
    (root / "flake.lock").write_text('{"version": 0, "nodes": {}}\n', encoding="utf-8")
    modules = root / "modules"
    modules.mkdir()
    pkg = modules / "packages.nix"
    pkg.write_text(
        '{ config, pkgs, ... }:\n{ environment.systemPackages = with pkgs; [ ]; }\n',
        encoding="utf-8",
    )
    git(root, "add", "flake.nix", "flake.lock", "modules/packages.nix")
    git(root, "commit", "-m", "init")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    reset_settings_cache()
    return root
