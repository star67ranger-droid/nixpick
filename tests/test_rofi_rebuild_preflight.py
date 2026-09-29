"""Rofi : rebuild bloqué si git preflight."""

from __future__ import annotations

from unittest import mock

import pytest

import rofi_mode


def test_offer_rebuild_stops_on_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    # Branche NixOS explicite : le bac à sable n'a pas /etc/nixos.
    monkeypatch.setattr("rofi_mode.is_nixos", lambda: True)
    monkeypatch.setattr(
        "rofi_mode._rofi",
        lambda *a, **k: rofi_mode.ROFI_REBUILD_NOW,
    )
    monkeypatch.setattr(
        "rofi_mode.rebuild_preflight_notify_body",
        lambda: "git -C /etc/nixos add foo",
    )
    preview = mock.Mock()
    notify = mock.Mock()
    rebuild = mock.Mock()
    monkeypatch.setattr(rofi_mode, "_rofi_preview", preview)
    monkeypatch.setattr(rofi_mode, "_notify", notify)
    monkeypatch.setattr(rofi_mode, "run_rebuild", rebuild)

    rofi_mode._offer_rebuild()

    notify.assert_called_once()
    preview.assert_called_once()
    rebuild.assert_not_called()


def test_offer_rebuild_fix_git_primary_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rofi_mode.is_nixos", lambda: True)
    monkeypatch.setattr("rofi_mode.check_flake_untracked", lambda: (False, "untracked files"))
    monkeypatch.setattr("rofi_mode._rofi", lambda *a, **k: rofi_mode.ROFI_FIX_GIT)
    fix_git = mock.Mock(return_value=0)
    monkeypatch.setattr("rofi_mode.run_fix_git", fix_git)
    notify = mock.Mock()
    rebuild = mock.Mock(return_value=0)
    monkeypatch.setattr(rofi_mode, "_notify", notify)
    monkeypatch.setattr(rofi_mode, "run_rebuild", rebuild)

    rofi_mode._offer_rebuild()

    fix_git.assert_called_once_with(yes=True)
    notify.assert_called_once()
    rebuild.assert_called_once_with(yes=True, in_terminal=True)


def test_offer_rebuild_fix_git_primary_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rofi_mode.is_nixos", lambda: True)
    monkeypatch.setattr("rofi_mode.check_flake_untracked", lambda: (False, "untracked files"))
    monkeypatch.setattr("rofi_mode._rofi", lambda *a, **k: rofi_mode.ROFI_FIX_GIT)
    fix_git = mock.Mock(return_value=1)
    monkeypatch.setattr("rofi_mode.run_fix_git", fix_git)
    notify = mock.Mock()
    rebuild = mock.Mock()
    monkeypatch.setattr(rofi_mode, "_notify", notify)
    monkeypatch.setattr(rofi_mode, "run_rebuild", rebuild)

    rofi_mode._offer_rebuild()

    fix_git.assert_called_once_with(yes=True)
    notify.assert_called_once()
    assert "Échec de fix-git" in notify.call_args[0][1]
    rebuild.assert_not_called()


def test_offer_rebuild_fix_git_from_preflight_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rofi_mode.is_nixos", lambda: True)
    rofi_responses = [rofi_mode.ROFI_REBUILD_NOW, rofi_mode.ROFI_FIX_GIT]
    monkeypatch.setattr("rofi_mode._rofi", lambda *a, **k: rofi_responses.pop(0))
    monkeypatch.setattr(
        "rofi_mode.rebuild_preflight_notify_body",
        lambda: "git -C /etc/nixos add foo",
    )
    fix_git = mock.Mock(return_value=0)
    monkeypatch.setattr("rofi_mode.run_fix_git", fix_git)
    notify = mock.Mock()
    rebuild = mock.Mock(return_value=0)
    monkeypatch.setattr(rofi_mode, "_notify", notify)
    monkeypatch.setattr(rofi_mode, "run_rebuild", rebuild)

    rofi_mode._offer_rebuild()

    fix_git.assert_called_once_with(yes=True)
    assert notify.call_count == 2
    rebuild.assert_called_once_with(yes=True, in_terminal=True)


def test_rofi_rebuild_choices_git_ok_toggle() -> None:
    from messages import ROFI_FIX_GIT, rofi_rebuild_choices

    assert ROFI_FIX_GIT in rofi_rebuild_choices(git_ok=False)
    assert ROFI_FIX_GIT not in rofi_rebuild_choices(git_ok=True)


def test_offer_sync_hors_nixos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rofi_mode.is_nixos", lambda: False)
    monkeypatch.setattr("config.is_nixos", lambda: False)
    monkeypatch.setattr("rofi_mode._rofi", lambda *a, **k: rofi_mode.ROFI_SYNC_NOW)
    sync = mock.Mock(return_value=0)
    monkeypatch.setattr("rofi_mode.run_sync", sync)
    notify = mock.Mock()
    monkeypatch.setattr(rofi_mode, "_notify", notify)

    rofi_mode._offer_rebuild()

    sync.assert_called_once_with(yes=True)
    # Une seule notif : l'annonce « en cours » (pas d'erreur, code 0).
    notify.assert_called_once()
    assert "en cours" in notify.call_args[0][1]


def test_offer_sync_refuse_hors_nixos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rofi_mode.is_nixos", lambda: False)
    monkeypatch.setattr("config.is_nixos", lambda: False)
    monkeypatch.setattr(
        "rofi_mode._rofi", lambda *a, **k: rofi_mode.ROFI_REBUILD_LATER
    )
    sync = mock.Mock()
    monkeypatch.setattr("rofi_mode.run_sync", sync)

    rofi_mode._offer_rebuild()

    sync.assert_not_called()

