"""Traducteur d'erreurs : chaque panne connue gagne un conseil (FR/EN)."""

from __future__ import annotations

import json
import subprocess

import pytest

from errors import explain_error
from i18n import set_language


@pytest.fixture(autouse=True)
def _french():
    set_language("fr")
    yield
    set_language("fr")


def test_timeout() -> None:
    advice = explain_error(subprocess.TimeoutExpired("nix", 600))
    assert advice is not None and "Ctrl+R" in advice


def test_index_corrompu() -> None:
    advice = explain_error(json.JSONDecodeError("attendu", "{oups", 0))
    assert advice is not None and "index.json" in advice


def test_binaire_manquant() -> None:
    advice = explain_error(FileNotFoundError(2, "absent", "rofi"))
    assert advice is not None and "rofi" in advice


def test_cache_io() -> None:
    advice = explain_error(OSError("disque plein"))
    assert advice is not None and ".cache" in advice


def test_sigkill_code() -> None:
    advice = explain_error(subprocess.CalledProcessError(-9, ["nix-env"]))
    assert advice is not None and "RAM" in advice


def test_sigkill_texte_vm() -> None:
    """Cas réel VM : nix-env tué par l'OOM-killer."""
    advice = explain_error(
        RuntimeError("Command '['nix-env', '-qaP', '--json']' died with SIGKILL.")
    )
    assert advice is not None and "RAM" in advice


def test_channel_manquant() -> None:
    advice = explain_error(
        RuntimeError("error: file 'nixpkgs' was not found in the Nix search path")
    )
    assert advice is not None and "nix-channel" in advice


def test_git_non_suivi() -> None:
    advice = explain_error(RuntimeError("not tracked by Git"))
    assert advice is not None and "fix-git" in advice


def test_inconnu_silencieux() -> None:
    assert explain_error(RuntimeError("panne jamais vue")) is None
    assert explain_error(ValueError("x")) is None


def test_conseils_en_anglais() -> None:
    set_language("en")
    advice = explain_error(subprocess.CalledProcessError(-9, ["nix-env"]))
    assert advice is not None and "RAM" in advice
    assert explain_error(RuntimeError("not tracked by Git")) is not None
