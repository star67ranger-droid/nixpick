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
