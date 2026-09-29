"""Les complétions shell suivent le CLI (sinon elles pourrissent en silence)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from nixpick import main

COMP_DIR = Path(__file__).resolve().parent.parent / "assets" / "completions"
FILES = ["nixpick.bash", "_nixpick", "nixpick.fish"]


def _help_text(
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    return capsys.readouterr().out


def test_completions_couvrent_le_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Chaque option de --help (global + sous-commandes) est complétée."""
    global_help = _help_text(["nixpick", "--help"], monkeypatch, capsys)
    usage = re.search(r"\{([^}]+)\}", global_help)
    assert usage is not None
    subcommands = usage.group(1).split(",")
    assert {"doctor", "rebuild", "fix-git", "sync"} <= set(subcommands)

    wanted = set(re.findall(r"--[\w-]+", global_help))
    for sub in subcommands:
        wanted |= set(
            re.findall(
                r"--[\w-]+",
                _help_text(["nixpick", sub, "--help"], monkeypatch, capsys),
            )
        )

    bodies = {name: (COMP_DIR / name).read_text(encoding="utf-8") for name in FILES}
    for opt in sorted(wanted):
        assert opt in bodies["nixpick.bash"], f"{opt} absent de nixpick.bash"
        assert opt in bodies["_nixpick"], f"{opt} absent de _nixpick"
        # fish sépare court/long : `--build-index-only` vit dans `-l build-index-only`.
        short = opt[2:] if opt.startswith("--") else opt[1:]
        fish = bodies["nixpick.fish"]
        assert f"-l {short}" in fish or f"-s {short}" in fish, (
            f"{opt} absent de nixpick.fish"
        )
    for sub in subcommands:
        for name, body in bodies.items():
            assert sub in body, f"sous-commande {sub} absente de {name}"
