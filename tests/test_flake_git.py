"""Tests flake_git (dépôt git temporaire)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from config import reset_settings_cache
from flake_git import (
    check_flake_untracked,
    format_git_add_command,
    list_untracked_paths,
    rebuild_preflight_message,
    rebuild_preflight_notify_body,
)


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


def test_list_untracked(flake_repo: Path) -> None:
    new_file = flake_repo / "dotfiles" / "scripts" / "new.sh"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("#!/bin/sh\n", encoding="utf-8")
    paths = list_untracked_paths(flake_repo)
    assert paths == ["dotfiles/scripts/new.sh"]


def test_check_fails_with_untracked(flake_repo: Path) -> None:
    new_file = flake_repo / "dotfiles" / "foo.nix"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("", encoding="utf-8")
    ok, detail = check_flake_untracked()
    assert not ok
    assert "dotfiles/foo.nix" in detail
    assert "git -C" in detail
    assert "add" in detail


def test_check_ok_when_clean(flake_repo: Path) -> None:
    ok, detail = check_flake_untracked()
    assert ok
    assert "aucun fichier non suivi" in detail.lower()


def test_preflight_message(flake_repo: Path) -> None:
    (flake_repo / "orphan.nix").write_text("", encoding="utf-8")
    msg = rebuild_preflight_message()
    assert msg is not None
    assert "Rebuild bloqué" in msg


def test_format_git_add() -> None:
    cmd = format_git_add_command(Path("/etc/nixos"), ["dotfiles/a.sh", "b c.nix"])
    assert "git -C" in cmd and "/etc/nixos" in cmd and " add " in cmd
    assert "dotfiles/a.sh" in cmd
    assert "'b c.nix'" in cmd


def test_preflight_notify_body_clean(flake_repo: Path) -> None:
    assert rebuild_preflight_notify_body() is None


def test_preflight_notify_body_untracked(flake_repo: Path) -> None:
    (flake_repo / "orphan.nix").write_text("", encoding="utf-8")
    body = rebuild_preflight_notify_body()
    assert body is not None
    assert "Fichiers non suivis" in body
    assert "git -C" in body
    assert "orphan.nix" in body
    assert "nixpick rebuild" in body
