"""Codes de sortie du CLI (audit TST-01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import reset_settings_cache
from messages import ISSUES_URL
from nixpick import main


@pytest.fixture
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pkg = tmp_path / "packages.nix"
    pkg.write_text(
        "{ config, pkgs, ... }:\n"
        "{ environment.systemPackages = with pkgs; [ ]; }\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(pkg))
    monkeypatch.setenv("NIXPICK_PACKAGES_ANCHOR", "environment.systemPackages")
    reset_settings_cache()
    return pkg


def test_remove_sans_termne_renvoie_2(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sans terme, `--remove` tombait dans la TUI au lieu de refuser."""
    monkeypatch.setattr("sys.argv", ["nixpick", "--remove"])
    assert main() == 2
    err = capsys.readouterr().err
    assert "--remove" in err and "terme" in err


def test_rofi_sans_rofi_renvoie_1(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """rofi absent : code 1 + explication, pas un faux succès (exit 0)."""
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("sys.argv", ["nixpick", "--rofi"])
    assert main() == 1
    assert "rofi introuvable" in capsys.readouterr().err


def test_print_affiche_meilleur_attr(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """--print : seul l'attr sur stdout (rien d'autre pour les scripts)."""
    monkeypatch.setattr(
        "nixpick.load_index",
        lambda refresh=False, on_status=None: {"htop": {"pname": "htop", "version": "3"}},
    )
    monkeypatch.setattr("sys.argv", ["nixpick", "--print", "htop"])
    assert main() == 0
    out = capsys.readouterr()
    assert out.out == "htop\n"
    assert out.err == ""


def test_print_sans_resultat(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("nixpick.load_index", lambda refresh=False, on_status=None: {})
    monkeypatch.setattr("sys.argv", ["nixpick", "--print", "zzz"])
    assert main() == 1


def test_print_index_indisponible(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from engine import NixCommandError

    def fail_index(*args: object, **kwargs: object) -> dict[str, object]:
        raise NixCommandError("nix-env a échoué")

    monkeypatch.setattr("nixpick.load_index", fail_index)
    monkeypatch.setattr("sys.argv", ["nixpick", "--print", "htop"])
    assert main() == 1
    err = capsys.readouterr().err
    assert "nix-env" in err or "échoué" in err


def test_erreur_inattendue_renvoie_1_avec_url(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Crash inattendu : traceback + URL de signalement, pas de propagation."""

    def boom(*args: object, **kwargs: object) -> int:
        raise RuntimeError("panne simulée")

    monkeypatch.setattr("nixpick.run_doctor", boom)
    monkeypatch.setattr("sys.argv", ["nixpick", "doctor"])
    assert main() == 1
    err = capsys.readouterr().err
    assert "panne simulée" in err
    assert ISSUES_URL in err
