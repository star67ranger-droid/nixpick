"""Préférences nixpick (~/.config/nixpick/config.toml)."""

from __future__ import annotations

import re
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "nixpick"
CONFIG_FILE = CONFIG_DIR / "config.toml"
SUPERFILE_CONFIG = Path.home() / ".config" / "superfile/config.toml"


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes", "on")


def _read_transparent_from_toml(path: Path) -> bool | None:
    if not path.exists():
        return None
    text = path.read_text()
    match = re.search(
        r"^\s*transparent_background\s*=\s*(true|false)\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return None
    return _parse_bool(match.group(1))


def load_transparent_background() -> bool:
    """Charge la préférence. Au premier lancement, reprend superfile si présent."""
    own = _read_transparent_from_toml(CONFIG_FILE)
    if own is not None:
        return own
    sf = _read_transparent_from_toml(SUPERFILE_CONFIG)
    if sf is not None:
        return sf
    return False


def save_transparent_background(enabled: bool) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        "# Préférences nixpick\n"
        "# transparent_background : laisse voir le fond du terminal (Kitty, etc.)\n"
        "# Comme superfile : ça ne marche que si ton émulateur a un fond transparent.\n"
        f"transparent_background = {'true' if enabled else 'false'}\n"
    )
