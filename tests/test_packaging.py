"""Modules racine importables (même liste que tool.setuptools.py-modules)."""

from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent.parent

ROOT_MODULES = [
    "nixpick",
    "engine",
    "tui",
    "cli",
    "rofi_mode",
    "config",
    "messages",
    "doctor",
    "rebuild_runner",
    "flake_git",
    "fix_git_runner",
    "flake_lock",
    "rofi_theme",
    "tui_css",
    "theme",
]

DATA_FILES = [
    ROOT / "assets/rofi/nixpick.rasi",
    ROOT / "assets/rofi/nixpick-query.rasi",
    ROOT / "config.example.toml",
]


def test_all_root_modules_import() -> None:
    for name in ROOT_MODULES:
        importlib.import_module(name)


def test_pyproject_modules_match_root() -> None:
    pyproject_path = ROOT / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    py_modules = data["tool"]["setuptools"]["py-modules"]
    assert set(py_modules) == set(ROOT_MODULES)


def test_version_sync() -> None:
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    py_ver = data["project"]["version"]
    assert config.__version__ == py_ver
    flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
    assert re.search(rf'version = "{py_ver}"', flake)


def test_packaged_data_files_exist_in_repo() -> None:
    for path in DATA_FILES:
        assert path.is_file(), f"manquant : {path}"
