"""Tests flake_git (dépôt git temporaire)."""

from __future__ import annotations

from pathlib import Path

import pytest

from flake_git import (
    check_flake_untracked,
    format_git_add_command,
    list_untracked_paths,
    rebuild_preflight_message,
    rebuild_preflight_notify_body,
)
from tests.conftest import git


def test_list_untracked(flake_repo: Path) -> None:
    new_file = flake_repo / "dotfiles" / "scripts" / "new.sh"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("#!/bin/sh\n", encoding="utf-8")
    paths, err = list_untracked_paths(flake_repo)
    assert err is None
    assert paths == ["dotfiles/scripts/new.sh"]


def test_untracked_outside_flake_prefix_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from config import reset_settings_cache

    root = tmp_path / "monorepo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "nixpick@test.local")
    git(root, "config", "user.name", "nixpick")
    nixos = root / "nixos"
    nixos.mkdir()
    (nixos / "flake.nix").write_text("{ outputs = _: {}; }\n", encoding="utf-8")
    (nixos / "flake.lock").write_text('{"version": 0}\n', encoding="utf-8")
    modules = nixos / "modules"
    modules.mkdir()
    pkg = modules / "packages.nix"
    pkg.write_text("{}", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "init")
    (root / "outside.txt").write_text("x", encoding="utf-8")
    (nixos / "inside.nix").write_text("", encoding="utf-8")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    reset_settings_cache()
    paths, err = list_untracked_paths(nixos)
    assert err is None
    assert any(p.endswith("inside.nix") for p in paths)
    assert "outside.txt" not in paths


def test_check_fails_with_untracked(flake_repo: Path) -> None:
    new_file = flake_repo / "dotfiles" / "foo.nix"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("", encoding="utf-8")
    ok, detail = check_flake_untracked()
    assert not ok
    assert "dotfiles/foo.nix" in detail
    assert "git -C" in detail
    assert "add --" in detail


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
    assert "git -C" in cmd and "/etc/nixos" in cmd and " add -- " in cmd
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
