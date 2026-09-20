"""Tests index-meta.json et --list-installed --json."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

import engine
from config import reset_settings_cache
from engine import INDEX_META_FILE, build_index, index_age_days

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


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(engine, "CACHE_DIR", cache)
    monkeypatch.setattr(engine, "INDEX_FILE", cache / "index.json")
    monkeypatch.setattr(engine, "INDEX_META_FILE", cache / "index-meta.json")
    return cache


def test_build_index_writes_meta(cache_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    slim = {"nixpkgs.firefox": {"pname": "firefox", "version": "1"}}
    monkeypatch.setattr(engine, "run", lambda *a, **k: json.dumps(slim))
    build_index()
    meta_path = cache_dir / "index-meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert "built_at" in meta
    assert "T" in meta["built_at"]


def test_index_age_from_meta(cache_dir: Path) -> None:
    built = time.time() - 3 * 86400
    engine._write_index_meta(built_at=built)
    (cache_dir / "index.json").write_text("{}")
    age = index_age_days()
    assert age is not None
    assert 2.9 < age < 3.1


def test_list_installed_json(
    packages_nix: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = packages_nix
    monkeypatch.setattr(sys, "argv", ["nixpick", "--list-installed", "--json"])
    from nixpick import main

    assert main() == 0
    data = json.loads(capsys.readouterr().out.strip())
    assert data["attrs"] == ["firefox"]
    assert data["count"] == 1
    assert data["packages_file"].endswith("packages.nix")
    assert "index_age_days" in data
