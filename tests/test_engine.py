"""Tests hors Nix (parsing, recherche, validation)."""

from __future__ import annotations

from pathlib import Path

import pytest

import engine as engine_module
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


def test_parser_rejects_unsupported_or_multiple_blocks(packages_nix: Path) -> None:
    from engine import _find_insertion_point

    multiple = SAMPLE_NIX.replace(
        "}\n",
        "  environment.systemPackages = with pkgs; [\n  ];\n}\n",
    )
    with pytest.raises(LookupError, match="multiple|non prise en charge"):
        _find_insertion_point(multiple.splitlines(keepends=True))

    unsupported = "{ environment.systemPackages = old ++ [ ]; }\n"
    with pytest.raises(LookupError, match="non prise en charge"):
        _find_insertion_point(unsupported.splitlines(keepends=True))


def test_parser_counts_nested_lists_and_ignores_comment_brackets(packages_nix: Path) -> None:
    from engine import _find_insertion_point

    lines = [
        "{ config, pkgs, ... }:\n",
        "{\n",
        "  environment.systemPackages = with pkgs; [\n",
        "    firefox # ] ignored\n",
        "    (foo.override { bar = [ 1 ]; })\n",
        "  ];\n",
        "}\n",
    ]
    insert_at, _indent = _find_insertion_point(lines)
    assert insert_at == 5


def test_fetch_descriptions_skips_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    from engine import fetch_descriptions

    monkeypatch.setattr(
        "engine.subprocess.run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("nix should not run")),
    )
    assert fetch_descriptions(["bad;attr"]) == {}


def test_run_nix_command_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    from engine import NixCommandError, run

    monkeypatch.setattr(
        "engine.subprocess.run",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()),
    )
    with pytest.raises(NixCommandError, match="introuvable"):
        run(["nix-env", "-qaP"], timeout=1)

    monkeypatch.setattr(
        "engine.subprocess.run",
        lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("nix-env", 1)),
    )
    with pytest.raises(NixCommandError, match="dépassé"):
        run(["nix-env", "-qaP"], timeout=1)

    err = subprocess.CalledProcessError(1, "nix-env", stderr="flake error")
    monkeypatch.setattr(
        "engine.subprocess.run",
        lambda *a, **k: (_ for _ in ()).throw(err),
    )
    with pytest.raises(NixCommandError, match="flake error"):
        run(["nix-env", "-qaP"], timeout=1)


def test_atomic_write_preserves_mode(tmp_path: Path) -> None:
    """UX-06 : la réécriture atomique ne doit pas passer le fichier en 0600."""
    import os
    import stat

    from engine import _atomic_write_text

    path = tmp_path / "packages.nix"
    path.write_text(SAMPLE_NIX)
    path.chmod(0o644)
    _atomic_write_text(path, SAMPLE_NIX + "\n")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o644
    assert path.read_text().endswith("\n")


# ── audit 2 : crochets dans les chaînes, fuzzy, sauvegardes ────────────────


def test_bloc_trouve_meme_avec_crochets_dans_une_chaine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un « [ » dans une chaîne ne doit pas déséquilibrer le bloc."""
    path = tmp_path / "packages.nix"
    path.write_text(
        "{ config, pkgs, ... }:\n"
        "{\n"
        "  environment.systemPackages = with pkgs; [\n"
        "    firefox\n"
        '    (pkgs.writeText "note" "voir [l\'annexe")\n'
        "  ];\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(path))
    monkeypatch.setenv("NIXPICK_PACKAGES_ANCHOR", "environment.systemPackages")
    reset_settings_cache()

    plan = plan_add("htop", "process viewer")
    assert not hasattr(plan, "outcome"), getattr(plan, "message", "")


def test_plan_add_attribut_invalide_nest_pas_un_bloc_manquant(
    packages_nix: Path,
) -> None:
    bad = plan_add("../evil", "")
    assert bad.outcome.name == "INVALID_ATTR"


def test_search_fuzzy_match_par_sous_sequence() -> None:
    rows = [
        PackageRow("firefox", "1", "firefox", "firefox"),
        PackageRow("firefox-esr", "1", "firefox-esr", "firefox-esr"),
        PackageRow("vim", "9", "vim", "vim"),
    ]
    index = _index(rows)
    # « frx » n'est nulle part contigu mais dans l'ordre → fzf le trouve.
    hits = [attr for attr, _ in search_index(index, "frx", limit=10)]
    assert "firefox" in hits
    # une correspondance contiguë reste toujours au-dessus.
    ranked = [attr for attr, _ in search_index(index, "fire", limit=10)]
    assert ranked[0] == "firefox"
    assert search_index(index, "zzzz", limit=10) == []


def test_fuzzy_ne_traite_pas_la_requete_comme_une_regex() -> None:
    """« a.c » matche l'attribut littéral « a.c », pas « abc »."""
    rows = [
        PackageRow("a.c", "1", "a.c", "a.c"),
        PackageRow("abc", "1", "abc", "abc"),
    ]
    hits = [attr for attr, _ in search_index(_index(rows), "a.c", limit=10)]
    assert "a.c" in hits
    assert "abc" not in hits


def test_commit_add_purge_les_anciennes_sauvegardes(
    packages_nix: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine import commit_add

    cache = packages_nix.parent / "cache"
    cache.mkdir()
    monkeypatch.setattr(engine_module, "CACHE_DIR", cache)
    monkeypatch.setattr(engine_module, "LAST_OP_FILE", cache / "last-op.json")

    for day in range(1, 9):
        (packages_nix.parent / f"packages.nix.bak.2020010{day}-000000").write_text(
            "# vieux\n", encoding="utf-8"
        )

    plan = plan_add("htop", "process viewer")
    assert not hasattr(plan, "outcome")
    commit_add(plan)

    remaining = sorted(
        p.name for p in packages_nix.parent.glob("packages.nix.bak.*")
    )
    assert len(remaining) == 5, remaining
    assert plan.backup_path.name in remaining
    # les plus anciennes sont parties
    assert "packages.nix.bak.20200101-000000" not in remaining
