"""Tests rebuild_runner (sans lancer Nix)."""

from __future__ import annotations

import io
from unittest import mock

import pytest

from config import reset_settings_cache
from engine import rebuild_command
from rebuild_runner import run_rebuild


@pytest.fixture(autouse=True)
def _env_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NIXPICK_REBUILD_COMMAND", "echo nixos-rebuild-test")
    monkeypatch.setattr("rebuild_runner.rebuild_preflight_message", lambda: None)
    reset_settings_cache()


def test_rebuild_command_argv() -> None:
    assert list(rebuild_command()) == ["echo", "nixos-rebuild-test"]


def test_run_rebuild_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_rebuild(dry_run=True) == 0
    assert "nixos-rebuild-test" in capsys.readouterr().out


def test_run_rebuild_declines_without_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert run_rebuild(yes=False) == 0


def test_run_rebuild_runs_with_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rebuild_runner.rebuild_preflight_message", lambda: None)
    with mock.patch("subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0)
        assert run_rebuild(yes=True) == 0
        run.assert_called_once_with(["echo", "nixos-rebuild-test"], check=False)


def test_rebuild_command_does_not_interpret_shell_syntax(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NIXPICK_REBUILD_COMMAND", "echo safe; touch /tmp/nixpick-pwned")
    reset_settings_cache()
    monkeypatch.setattr("rebuild_runner.rebuild_preflight_message", lambda: None)
    with mock.patch("subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0)
        assert run_rebuild(yes=True) == 0
        assert run.call_args.args[0] == ["echo", "safe;", "touch", "/tmp/nixpick-pwned"]


def test_run_rebuild_blocked_by_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rebuild_runner.rebuild_preflight_message",
        lambda: "Rebuild bloqué avant lancement",
    )
    assert run_rebuild(yes=True) == 1


def test_terminal_argv_kitty_sans_option_e() -> None:
    from rebuild_runner import _terminal_argv

    # kitty n'a pas d'option -e (vérifié) ; les autres la gardent.
    assert _terminal_argv("kitty", "echo hi") == ["kitty", "bash", "-lc", "echo hi"]
    assert _terminal_argv("alacritty", "echo hi") == [
        "alacritty",
        "-e",
        "bash",
        "-lc",
        "echo hi",
    ]


def test_run_rebuild_terminal_kitty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rebuild_runner._default_terminal", lambda: "kitty")
    with mock.patch("subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0)
        assert run_rebuild(yes=True, in_terminal=True) == 0
        argv = run.call_args.args[0]
        assert argv[:2] == ["kitty", "bash"]
        assert "-e" not in argv


def test_run_rebuild_terminal_env_invalide_repli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("NIXPICK_REBUILD_TERMINAL", "terminal-fantome")
    monkeypatch.setattr("rebuild_runner._default_terminal", lambda: "alacritty")
    with mock.patch("subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0)
        assert run_rebuild(yes=True, in_terminal=True) == 0
        assert run.call_args.args[0][0] == "alacritty"
    assert "introuvable" in capsys.readouterr().err


def test_run_rebuild_refuse_sans_tty_sans_yes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert run_rebuild(yes=False) == 1
    assert "nixpick rebuild --yes" in capsys.readouterr().err


def test_run_rebuild_commande_vide(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("rebuild_runner.rebuild_command", lambda: ())
    assert run_rebuild(yes=True) == 1
    assert "rebuild_command vide" in capsys.readouterr().err


def test_run_rebuild_terminal_sans_emulateur(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("rebuild_runner._default_terminal", lambda: None)
    monkeypatch.delenv("NIXPICK_REBUILD_TERMINAL", raising=False)
    assert run_rebuild(yes=True, in_terminal=True) == 1
    err = capsys.readouterr().err
    assert "aucun émulateur" in err
    assert "nixos-rebuild-test" in err
