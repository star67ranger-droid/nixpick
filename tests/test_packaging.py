"""Modules racine importables (même liste que tool.setuptools.py-modules)."""

from __future__ import annotations

import importlib
from pathlib import Path
import tomllib

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


def test_all_root_modules_import() -> None:
    for name in ROOT_MODULES:
        importlib.import_module(name)


def test_pyproject_modules_match_root() -> None:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    py_modules = data["tool"]["setuptools"]["py-modules"]
    assert set(py_modules) == set(ROOT_MODULES)
