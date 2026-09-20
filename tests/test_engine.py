"""Tests hors Nix (parsing, recherche, validation)."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import reset_settings_cache
from engine import (
    PackageIndex,
    PackageRow,
    find_package_line_index,
    list_installed_attrs,
    plan_add,
    plan_remove,
    search_index,
)

SAMPLE_NIX = """{ config, pkgs, ... }:
{
  environment.systemPackages = with pkgs; [
    firefox
    vim # editor
  ];
}
"""


@pytest.fixture
def packages_nix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "packages.nix"
    path.write_text(SAMPLE_NIX)
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(path))
    monkeypatch.setenv("NIXPICK_PACKAGES_ANCHOR", "environment.systemPackages")
    reset_settings_cache()
    return path


def _index(rows: list[PackageRow]) -> PackageIndex:
    by_leading: dict[str, list[PackageRow]] = {}
    for row in rows:
        for ch in {row.attr_lc[:1], row.pname_lc[:1]} - {""}:
            by_leading.setdefault(ch, []).append(row)
    return PackageIndex(rows=rows, by_leading=by_leading)


def test_search_index_prefix_and_exact() -> None:
    rows = [
        PackageRow("firefox", "1", "firefox", "firefox"),
        PackageRow("firefox-esr", "1", "firefox-esr", "firefox-esr"),
        PackageRow("vim", "9", "vim", "vim"),
    ]
    index = _index(rows)
    hits = search_index(index, "firefox", limit=10)
    assert hits[0][0] == "firefox"
    assert any(a == "firefox-esr" for a, _ in hits)


def test_list_installed_and_find_line(packages_nix: Path) -> None:
    installed = list_installed_attrs()
    assert installed == {"firefox", "vim"}
    lines = packages_nix.read_text().splitlines()
    assert find_package_line_index(lines, "firefox") is not None
    assert find_package_line_index(lines, "missing") is None


def test_plan_add_and_remove(packages_nix: Path) -> None:
    add = plan_add("htop", "process viewer")
    assert not hasattr(add, "outcome")
    assert add.attr == "htop"

    dup = plan_add("firefox", "")
    assert dup.outcome.name == "ALREADY_LISTED"

    bad = plan_remove("../evil")
    assert bad.outcome.name == "INVALID_ATTR"

    rem = plan_remove("vim")
    assert rem.attr == "vim"


def test_fetch_descriptions_skips_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    from engine import fetch_descriptions

    monkeypatch.setattr(
        "engine.subprocess.run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("nix should not run")),
    )
    assert fetch_descriptions(["bad;attr"]) == {}
