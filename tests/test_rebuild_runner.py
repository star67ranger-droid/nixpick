"""Tests rebuild_runner (sans lancer Nix)."""

from __future__ import annotations

import io
from unittest import mock

import pytest

from config import reset_settings_cache
from rebuild_runner import rebuild_command_argv, run_rebuild


@pytest.fixture(autouse=True)
def _env_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NIXPICK_REBUILD_COMMAND", "echo nixos-rebuild-test")
    reset_settings_cache()


def test_rebuild_command_argv() -> None:
    assert rebuild_command_argv() == ["echo", "nixos-rebuild-test"]


def test_run_rebuild_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_rebuild(dry_run=True) == 0
    assert "nixos-rebuild-test" in capsys.readouterr().out


def test_run_rebuild_declines_without_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert run_rebuild(yes=False) == 0


def test_run_rebuild_runs_with_yes() -> None:
    with mock.patch("subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0)
        assert run_rebuild(yes=True) == 0
        run.assert_called_once()
        assert run.call_args[0][0] == "echo nixos-rebuild-test"
