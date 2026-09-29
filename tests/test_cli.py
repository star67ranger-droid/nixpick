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


def test_cli_remove_hors_nixos_indique_profile_remove(
    packages_nix: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Hors NixOS : pas de prompt rebuild, juste la commande manuelle."""
    packages_nix.write_text(
        SAMPLE.replace("    firefox\n", "    firefox\n    htop\n"), encoding="utf-8"
    )
    monkeypatch.setattr("cli.is_nixos", lambda: False)
    _answers(monkeypatch, "o")
    assert cli.run_cli_remove("htop", dry_run=False) == 0
    assert "htop" not in packages_nix.read_text(encoding="utf-8")
    assert "nix profile remove htop" in capsys.readouterr().err


def test_cli_add_propose_install_oui(
    packages_nix: Path, fake_index: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hors NixOS : accepter installe nixpkgs#attr dans le profil."""
    monkeypatch.setattr("cli.is_nixos", lambda: False)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "cli.install_profile_refs",
        lambda refs: calls.append(refs) or 0,
    )
    _answers(monkeypatch, "1", "o", "o")
    assert cli.run_cli("htop", refresh=False, dry_run=False) == 0
    assert calls == [["nixpkgs#htop"]]
    assert "htop" in packages_nix.read_text(encoding="utf-8")


def test_cli_add_propose_install_non(
    packages_nix: Path, fake_index: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuser : aucun appel nix, ajout conservé."""
    monkeypatch.setattr("cli.is_nixos", lambda: False)

    def boom(refs: list[str]) -> int:
        raise AssertionError("ne doit pas installer")

    monkeypatch.setattr("cli.install_profile_refs", boom)
    _answers(monkeypatch, "1", "o", "n")
    assert cli.run_cli("htop", refresh=False, dry_run=False) == 0
    assert "htop" in packages_nix.read_text(encoding="utf-8")


def test_cli_add_install_ko_code_install_ajout_garde(
    packages_nix: Path,
    fake_index: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Échec d'install : code d'install remonté, mais l'ajout reste acquis."""
    monkeypatch.setattr("cli.is_nixos", lambda: False)
    monkeypatch.setattr("cli.install_profile_refs", lambda refs: 1)
    _answers(monkeypatch, "1", "o", "o")
    assert cli.run_cli("htop", refresh=False, dry_run=False) == 1
    assert "htop" in packages_nix.read_text(encoding="utf-8")
    assert "échoué" in capsys.readouterr().err
