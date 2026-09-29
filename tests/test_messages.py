"""messages.py : prédicat partagé + consignes selon la plateforme."""

from __future__ import annotations

from pathlib import Path

import pytest

from messages import apply_hint, cli_success_lines, is_affirmative


def test_is_affirmative() -> None:
    for yes in ("o", "oui", "y", "yes", "O", "OUI", " Yes ", "o\n"):
        assert is_affirmative(yes), yes
    for no in ("", "n", "non", "no", "yess", "oo", "1"):
        assert not is_affirmative(no), no


def test_apply_hint_suit_la_plateforme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("messages.is_nixos", lambda: True)
    assert apply_hint() == "nixpick rebuild"
    assert "rebuild" in " ".join(cli_success_lines(Path("/tmp/x")))
    monkeypatch.setattr("messages.is_nixos", lambda: False)
    assert apply_hint() == "nixpick sync"
    lines = " ".join(cli_success_lines(Path("/tmp/x")))
    assert "sync" in lines and "rebuild" not in lines
