"""Tests flake_lock (JSON mock, sans Nix)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config import reset_settings_cache
from flake_lock import _locked_nixpick_path, check_nixpick_flake_lock


def test_locked_nixpick_path_parses() -> None:
    data = {
        "nodes": {
            "nixpick": {
                "locked": {
                    "type": "path",
                    "path": "/home/pikeo/Projets/nixpick",
                    "narHash": "sha256-abc",
                }
            }
        }
    }
    assert _locked_nixpick_path(data) == (Path("/home/pikeo/Projets/nixpick"), "sha256-abc")


def test_check_skips_without_flake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = tmp_path / "packages.nix"
    pkg.write_text("{ }\n", encoding="utf-8")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    reset_settings_cache()
    ok, detail = check_nixpick_flake_lock()
    assert ok is True
    assert "ignoré" in detail.lower() or "pas de flake" in detail.lower()


def test_check_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flake = tmp_path / "flake"
    flake.mkdir()
    (flake / "flake.nix").write_text("{ }\n", encoding="utf-8")
    nixpick = tmp_path / "nixpick"
    nixpick.mkdir()
    nixpick.joinpath("flake.nix").write_text("{ }\n", encoding="utf-8")
    lock = {
        "nodes": {
            "nixpick": {
                "locked": {
                    "type": "path",
                    "path": str(nixpick),
                    "narHash": "sha256-deadbeef",
                }
            }
        }
    }
    (flake / "flake.lock").write_text(json.dumps(lock), encoding="utf-8")
    pkg = flake / "modules" / "packages.nix"
    pkg.parent.mkdir()
    pkg.write_text("{ }\n", encoding="utf-8")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    reset_settings_cache()

    def fake_hash(path: Path) -> str | None:
        return "sha256-current"

    monkeypatch.setattr("flake_lock._path_nar_hash", fake_hash)
    ok, detail = check_nixpick_flake_lock()
    assert ok is False
    assert "flake lock" in detail.lower() or "périmé" in detail.lower()


def test_check_volatile_change_is_not_an_alarm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UX-04 : un commit (.git) ne doit pas déclencher l'alarme flake.lock."""
    import os

    flake = tmp_path / "flake"
    flake.mkdir()
    (flake / "flake.nix").write_text("{ }\n", encoding="utf-8")
    nixpick = tmp_path / "nixpick"
    nixpick.mkdir()
    (nixpick / "flake.nix").write_text("{ }\n", encoding="utf-8")
    lock = {
        "nodes": {
            "nixpick": {
                "locked": {
                    "type": "path",
                    "path": str(nixpick),
                    "narHash": "sha256-deadbeef",
                }
            }
        }
    }
    lock_path = flake / "flake.lock"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    pkg = flake / "modules" / "packages.nix"
    pkg.parent.mkdir()
    pkg.write_text("{ }\n", encoding="utf-8")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    reset_settings_cache()
    monkeypatch.setattr("flake_lock._path_nar_hash", lambda p: "sha256-current")

    # Un commit : seul le contenu de .git est plus récent que le lock.
    git_dir = nixpick / ".git"
    git_dir.mkdir()
    head = git_dir / "HEAD"
    head.write_text("ref: refs/heads/main\n", encoding="utf-8")
    newer = lock_path.stat().st_mtime + 10
    os.utime(head, (newer, newer))

    ok, detail = check_nixpick_flake_lock()
    assert ok is True
    assert "volatil" in detail.lower()

    # Par contre, une source modifiée après le lock doit alerter.
    source = nixpick / "engine.py"
    source.write_text("# changed\n", encoding="utf-8")
    os.utime(source, (newer + 10, newer + 10))
    ok, detail = check_nixpick_flake_lock()
    assert ok is False
    assert "périmé" in detail.lower()
