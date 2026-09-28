"""Mode CLI interactif (cli.py) : prompts mockés, commits réels sur tmp."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import cli
import engine
from config import reset_settings_cache

SAMPLE = """{ config, pkgs, ... }:
{
  environment.systemPackages = with pkgs; [
    firefox
  ];
}
"""


@pytest.fixture
def packages_nix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "packages.nix"
    path.write_text(SAMPLE, encoding="utf-8")
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(path))
    monkeypatch.setenv("NIXPICK_PACKAGES_ANCHOR", "environment.systemPackages")
    # Même pattern que les autres tests : le cache réel (~/.cache) n'existe
    # pas forcément (bac à sable Nix, HOME en lecture seule).
    monkeypatch.setattr(engine, "CACHE_DIR", cache)
    monkeypatch.setattr(engine, "LAST_OP_FILE", cache / "last-op.json")
    reset_settings_cache()
    return path


def _answers(monkeypatch: pytest.MonkeyPatch, *replies: str) -> None:
    it: Iterator[str] = iter(replies)

    def fake_input(_prompt: str = "") -> str:
        return next(it)

    monkeypatch.setattr("builtins.input", fake_input)


@pytest.fixture
def fake_index(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli, "load_index", lambda refresh=False, on_status=None: {"htop": {"pname": "htop", "version": "3.0"}}
    )
    monkeypatch.setattr(cli, "fetch_descriptions", lambda attrs: {})


def test_cli_add_confirme_ecrit(
    packages_nix: Path, fake_index: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answers(monkeypatch, "1", "o", "n")
    assert cli.run_cli("htop", refresh=False, dry_run=False) == 0
    assert "htop" in packages_nix.read_text(encoding="utf-8")


def test_cli_add_dry_run_n_ecrit_pas(
    packages_nix: Path, fake_index: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answers(monkeypatch, "1")
    assert cli.run_cli("htop", refresh=False, dry_run=True) == 0
    assert "htop" not in packages_nix.read_text(encoding="utf-8")


def test_cli_add_annule_au_choix(
    packages_nix: Path, fake_index: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answers(monkeypatch, "")
    assert cli.run_cli("htop", refresh=False, dry_run=False) == 0
    assert "htop" not in packages_nix.read_text(encoding="utf-8")


def test_cli_add_choix_invalide(
    packages_nix: Path, fake_index: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answers(monkeypatch, "99")
    assert cli.run_cli("htop", refresh=False, dry_run=False) == 1


def test_cli_add_sans_resultat(
    packages_nix: Path, fake_index: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert cli.run_cli("zzzz-introuvable", refresh=False, dry_run=False) == 1


def test_cli_remove_confirme_retire(
    packages_nix: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packages_nix.write_text(
        SAMPLE.replace("    firefox\n", "    firefox\n    htop\n"), encoding="utf-8"
    )
    _answers(monkeypatch, "o", "n")
    assert cli.run_cli_remove("htop", dry_run=False) == 0
    assert "htop" not in packages_nix.read_text(encoding="utf-8")


def test_cli_remove_dry_run(
    packages_nix: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packages_nix.write_text(
        SAMPLE.replace("    firefox\n", "    firefox\n    htop\n"), encoding="utf-8"
    )
    assert cli.run_cli_remove("htop", dry_run=True) == 0
    assert "htop" in packages_nix.read_text(encoding="utf-8")


def test_cli_remove_non_liste(
    packages_nix: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert cli.run_cli_remove("htop", dry_run=False) == 0
