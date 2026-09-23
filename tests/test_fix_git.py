"""Tests fix-git (git temporaire)."""

from __future__ import annotations

import subprocess
from pathlib import Path
import pytest

from fix_git_runner import run_fix_git
from tests.conftest import git


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


def test_fix_git_no_git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lone = tmp_path / "flakeonly"
    lone.mkdir()
    (lone / "flake.nix").write_text("{}", encoding="utf-8")
    (lone / "flake.lock").write_text("{}", encoding="utf-8")
    pkg = lone / "packages.nix"
    pkg.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    from config import reset_settings_cache

    reset_settings_cache()
    assert run_fix_git(yes=True) == 1
