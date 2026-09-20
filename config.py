"""Configuration nixpick (~/.config/nixpick/config.toml + variables d'environnement)."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

__version__ = "0.1.0"

PACKAGE_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = Path.home() / ".config" / "nixpick"
CONFIG_FILE = CONFIG_DIR / "config.toml"
SUPERFILE_CONFIG = Path.home() / ".config" / "superfile/config.toml"

DEFAULT_PACKAGES_FILE = Path("/etc/nixos/modules/packages.nix")
DEFAULT_ANCHOR = "environment.systemPackages"
DEFAULT_REBUILD = "sudo nixos-rebuild switch"


@dataclass(frozen=True)
class Settings:
    packages_file: Path
    packages_anchor: str
    rebuild_command: str


_settings: Settings | None = None


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
    """Préférence TUI. Au premier lancement, reprend superfile si présent."""
    own = _read_transparent_from_toml(CONFIG_FILE)
    if own is not None:
        return own
    sf = _read_transparent_from_toml(SUPERFILE_CONFIG)
    if sf is not None:
        return sf
    return False


def save_transparent_background(enabled: bool) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = CONFIG_FILE.read_text() if CONFIG_FILE.exists() else ""
    if "transparent_background" in existing:
        text = re.sub(
            r"^\s*transparent_background\s*=\s*.+$",
            f"transparent_background = {'true' if enabled else 'false'}",
            existing,
            flags=re.MULTILINE,
        )
    else:
        text = (
            existing.rstrip()
            + "\n\ntransparent_background = "
            + ("true" if enabled else "false")
            + "\n"
        )
    CONFIG_FILE.write_text(text if text.endswith("\n") else text + "\n")


def _load_toml() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with CONFIG_FILE.open("rb") as fh:
            data = tomllib.load(fh)
        return data if isinstance(data, dict) else {}
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def get_settings() -> Settings:
    global _settings
    if _settings is not None:
        return _settings

    data = _load_toml()
    nix = data.get("nixpick") if isinstance(data.get("nixpick"), dict) else data

    packages_raw = os.environ.get("NIXPICK_PACKAGES_FILE") or nix.get(
        "packages_file", str(DEFAULT_PACKAGES_FILE)
    )
    packages_path = Path(packages_raw).expanduser()
    if packages_path.suffix != ".nix":
        raise ValueError(
            f"packages_file doit être un fichier .nix, reçu : {packages_path}"
        )
    packages_path = packages_path.resolve()
    anchor = os.environ.get("NIXPICK_PACKAGES_ANCHOR") or nix.get(
        "packages_anchor", DEFAULT_ANCHOR
    )
    rebuild = os.environ.get("NIXPICK_REBUILD_COMMAND") or nix.get(
        "rebuild_command", DEFAULT_REBUILD
    )

    _settings = Settings(
        packages_file=packages_path,
        packages_anchor=str(anchor).strip(),
        rebuild_command=str(rebuild).strip(),
    )
    return _settings


def reset_settings_cache() -> None:
    """Tests / rechargement après écriture de config."""
    global _settings
    _settings = None


def asset_path(*parts: str) -> Path:
    return PACKAGE_ROOT.joinpath("assets", *parts)


def rofi_theme_paths(query_only: bool) -> list[Path]:
    """Ordre de recherche des thèmes Rofi."""
    names = (
        ("nixpick-query.rasi", "nixpick-query.rasi")
        if query_only
        else ("nixpick.rasi", "nixpick.rasi")
    )
    name = names[0]
    return [
        CONFIG_DIR / "rofi" / name,
        Path.home() / ".config/rofi" / name,
        asset_path("rofi", name),
    ]
