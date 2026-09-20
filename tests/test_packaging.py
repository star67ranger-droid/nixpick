"""Modules racine importables (même liste que tool.setuptools.py-modules)."""

from __future__ import annotations

import importlib

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
    "flake_lock",
    "rofi_theme",
    "tui_css",
    "theme",
]


def test_all_root_modules_import() -> None:
    for name in ROOT_MODULES:
        importlib.import_module(name)
