"""nixpick sync : parsing du profil, diff, confirmations (nix mocké)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import sync_runner
from sync_runner import is_installed, missing_refs, parse_profile_list, run_sync

PROFILE_SAMPLE = """Name:               htop
Flake attribute:    legacyPackages.x86_64-linux.htop
Original flake URL: flake:nixpkgs
Locked flake URL:   github:NixOS/nixpkgs/abc123
Store paths:        /nix/store/xxx-htop-3.0

Name:               \x1b[1mvim\x1b[0m
Flake attribute:    legacyPackages.x86_64-linux.vim
Original flake URL: flake:nixpkgs
Locked flake URL:   github:NixOS/nixpkgs/abc123
Store paths:        /nix/store/yyy-vim-9.1
"""


def test_parse_profile_list() -> None:
    entries = parse_profile_list(PROFILE_SAMPLE)
    assert len(entries) == 2
    # Codes ANSI éventuels (sortie non redirigée) nettoyés.
    assert entries[0]["name"] == "htop"
    assert entries[1]["name"] == "vim"
    assert entries[0]["flake_attribute"] == "legacyPackages.x86_64-linux.htop"
    assert parse_profile_list("") == []


def test_is_installed() -> None:
    entries = parse_profile_list(PROFILE_SAMPLE)
    assert is_installed("htop", entries)  # suffixe .htop
    assert is_installed("vim", entries)  # nom exact malgré ANSI
    assert not is_installed("firefox", entries)
    # ".htop" exige le point : pas de faux positif sur préfixe.
    assert not is_installed("top", entries)
    assert not is_installed("ht", entries)


def test_missing_refs() -> None:
    entries = parse_profile_list(PROFILE_SAMPLE)
    assert missing_refs(["htop", "firefox"], entries) == ["nixpkgs#firefox"]
    assert missing_refs(["htop"], entries) == []


def _patch_nix(
    monkeypatch: pytest.MonkeyPatch,
    *,
    profile_stdout: str = PROFILE_SAMPLE,
    profile_code: int = 0,
    install_code: int = 0,
    upgrade_code: int = 0,
    have_nix: bool = True,
    tty: bool = True,
    answers: list[str] | None = None,
    listed: list[str] | None = None,
) -> list[list[str]]:
    calls: list[list[str]] = []
    if answers is not None:
        it = iter(answers)
        monkeypatch.setattr("builtins.input", lambda _p="": next(it))
    monkeypatch.setattr("sys.stdin.isatty", lambda: tty)
    monkeypatch.setattr(
        "shutil.which", lambda name: "/usr/bin/nix" if have_nix else None
    )
    monkeypatch.setattr(
        "sync_runner.list_installed_attrs",
        lambda: set(listed if listed is not None else ["htop", "firefox"]),
    )

    def fake_run(argv: list[str], **kwargs: object) -> SimpleNamespace:
        if argv[:3] == ["nix", "profile", "list"]:
            return SimpleNamespace(
                returncode=profile_code, stdout=profile_stdout, stderr="oups"
            )
        if argv[:3] == ["nix", "profile", "install"]:
            calls.append(argv)
            return SimpleNamespace(returncode=install_code, stdout="")
        if argv[:3] == ["nix", "profile", "upgrade"]:
            calls.append(argv)
            return SimpleNamespace(returncode=upgrade_code, stdout="")
        raise AssertionError(f"appel inattendu : {argv}")

    monkeypatch.setattr("subprocess.run", fake_run)
    return calls


def test_sync_sans_nix(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_nix(monkeypatch, have_nix=False)
    assert run_sync() == 1


def test_sync_liste_vide(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_nix(monkeypatch, listed=[])
    assert run_sync() == 0
    assert calls == []


def test_sync_profil_illisible(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_nix(monkeypatch, profile_code=1)
    assert run_sync() == 1


def test_sync_a_jour(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_nix(monkeypatch, listed=["htop"])
    assert run_sync() == 0
    assert calls == []


def test_sync_dry_run_n_execute_rien(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _patch_nix(monkeypatch)
    assert run_sync(dry_run=True) == 0
    assert calls == []
    # shlex.join quote nixpkgs#… (# = commentaire shell) : forme copiable telle quelle.
    assert "nix profile install 'nixpkgs#firefox'" in capsys.readouterr().out


def test_sync_refuse_sans_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _patch_nix(monkeypatch, tty=False)
    assert run_sync() == 1
    assert calls == []
    assert "nixpick sync --yes" in capsys.readouterr().err


def test_sync_decline(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_nix(monkeypatch, answers=["n"])
    assert run_sync() == 0
    assert calls == []


def test_sync_confirme_installe(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _patch_nix(monkeypatch, answers=["o"])
    assert run_sync() == 0
    assert calls == [["nix", "profile", "install", "nixpkgs#firefox"]]
    assert "Installé" in capsys.readouterr().out


def test_sync_echec_install(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_nix(monkeypatch, answers=["o"], install_code=1)
    assert run_sync() == 1
    assert "code 1" in capsys.readouterr().err


def test_sync_yes_sans_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_nix(monkeypatch, tty=False)
    assert run_sync(yes=True) == 0
    assert calls == [["nix", "profile", "install", "nixpkgs#firefox"]]


def test_upgradeable_refs() -> None:
    from sync_runner import upgradeable_refs

    entries = parse_profile_list(PROFILE_SAMPLE)
    assert upgradeable_refs(["htop", "firefox"], entries) == [
        "legacyPackages.x86_64-linux.htop"
    ]
    assert upgradeable_refs(["firefox"], entries) == []
    # Entrée sans flake attribute : ignorée (pas de cible fiable).
    assert upgradeable_refs(["x"], [{"name": "x"}]) == []


def test_sync_upgrade_installe_puis_met_a_jour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_nix(monkeypatch, answers=["o"])
    assert run_sync(upgrade=True) == 0
    assert calls == [
        ["nix", "profile", "install", "nixpkgs#firefox"],
        ["nix", "profile", "upgrade", "legacyPackages.x86_64-linux.htop"],
    ]


def test_sync_upgrade_dry_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _patch_nix(monkeypatch)
    assert run_sync(upgrade=True, dry_run=True) == 0
    assert calls == []
    out = capsys.readouterr().out
    assert "nix profile install 'nixpkgs#firefox'" in out
    assert "nix profile upgrade legacyPackages.x86_64-linux.htop" in out


def test_sync_upgrade_echec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_nix(monkeypatch, answers=["o"], upgrade_code=1)
    assert run_sync(upgrade=True) == 1
    assert calls[-1][:3] == ["nix", "profile", "upgrade"]


def test_install_profile_refs_erreur_os(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(argv: list[str], **kwargs: object) -> SimpleNamespace:
        raise OSError("pas de nix")

    monkeypatch.setattr("subprocess.run", boom)
    assert sync_runner.install_profile_refs(["nixpkgs#htop"]) == 1
    assert "pas de nix" in capsys.readouterr().err


def test_upgrade_profile_refs_erreur_os(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(argv: list[str], **kwargs: object) -> SimpleNamespace:
        raise OSError("pas de nix")

    monkeypatch.setattr("subprocess.run", boom)
    assert sync_runner.upgrade_profile_refs(["legacyPackages.x86_64-linux.htop"]) == 1
    assert "pas de nix" in capsys.readouterr().err


def test_sync_profile_list_os_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_nix(monkeypatch)

    def boom(argv: list[str], **kwargs: object) -> SimpleNamespace:
        if argv[:3] == ["nix", "profile", "list"]:
            raise OSError("nix absent")
        raise AssertionError(argv)

    monkeypatch.setattr("subprocess.run", boom)
    assert run_sync() == 1
    assert "nix absent" in capsys.readouterr().err


def test_sync_upgrade_seul_sans_install(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tous listés déjà installés : --upgrade ne lance que profile upgrade."""
    calls = _patch_nix(monkeypatch, listed=["htop"], answers=["o"])
    assert run_sync(upgrade=True) == 0
    assert calls == [
        ["nix", "profile", "upgrade", "legacyPackages.x86_64-linux.htop"],
    ]
    assert "mis à jour" in capsys.readouterr().out.lower()


def test_sync_interruption_prompt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _patch_nix(monkeypatch, listed=["htop", "firefox"])

    def interrupt(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", interrupt)
    assert run_sync(upgrade=True) == 1
    assert calls == []
    capsys.readouterr()
