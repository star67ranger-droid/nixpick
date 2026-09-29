"""Configuration nixpick (~/.config/nixpick/config.toml + variables d'environnement)."""

from __future__ import annotations

import os
import re
import shlex
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__version__ = "0.4.0"

PACKAGE_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = Path.home() / ".config" / "nixpick"
CONFIG_FILE = CONFIG_DIR / "config.toml"
SUPERFILE_CONFIG = Path.home() / ".config" / "superfile/config.toml"

DEFAULT_PACKAGES_FILE = Path("/etc/nixos/modules/packages.nix")
DEFAULT_ANCHOR = "environment.systemPackages"
DEFAULT_REBUILD = "sudo nixos-rebuild switch --flake /etc/nixos#nixos"


def is_nixos() -> bool:
    """NixOS détecté par son dépôt de configuration."""
    return Path("/etc/nixos").exists()


def fallback_packages_file() -> Path:
    """Cible locale hors NixOS : utiliser nixpick sans /etc/nixos."""
    return Path.home() / ".config" / "nixpick" / "packages.nix"


def default_packages_file() -> Path:
    """Fichier cible sans config explicite (ni TOML ni variable d'env)."""
    if is_nixos():
        return DEFAULT_PACKAGES_FILE
    return fallback_packages_file()


@dataclass(frozen=True)
class Settings:
    packages_file: Path
    packages_anchor: str
    rebuild_command: tuple[str, ...]


_settings: Settings | None = None


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes", "on")


def _read_transparent_from_toml(path: Path) -> bool | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"^\s*transparent_background\s*=\s*(true|false)\s*(?:#.*)?$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return None
    return _parse_bool(match.group(1))


_ACTIVE_TRANSPARENT_RE = re.compile(r"^\s*transparent_background\s*=", re.MULTILINE)


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
    existing = CONFIG_FILE.read_text(encoding="utf-8") if CONFIG_FILE.exists() else ""
    # Ligne active uniquement : une clé en commentaire ne compte pas, sinon
    # le toggle serait silencieusement perdu (ni substitué, ni ajouté).
    if _ACTIVE_TRANSPARENT_RE.search(existing):
        text = re.sub(
            r"^\s*transparent_background\s*=.*$",
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
    content = text if text.endswith("\n") else text + "\n"
    _atomic_write_config(CONFIG_FILE, content)


def _atomic_write_config(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class ConfigError(ValueError):
    """config.toml présent mais illisible (TOML invalide ou lecture en échec)."""


def _load_toml() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with CONFIG_FILE.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as err:
        raise ConfigError(
            f"{CONFIG_FILE} : TOML invalide — {err} "
            "(compare avec config.example.toml)."
        ) from err
    except OSError as err:
        raise ConfigError(f"{CONFIG_FILE} illisible — {err}") from err
    return data if isinstance(data, dict) else {}


def get_settings() -> Settings:
    global _settings
    if _settings is not None:
        return _settings

    data = _load_toml()
    raw_nix = data.get("nixpick")
    nix: dict[str, Any] = raw_nix if isinstance(raw_nix, dict) else data

    packages_raw = os.environ.get("NIXPICK_PACKAGES_FILE") or nix.get(
        "packages_file", str(default_packages_file())
    )
    if not isinstance(packages_raw, str):
        raise ValueError("packages_file doit être une chaîne (chemin .nix)")
    packages_path = Path(packages_raw).expanduser()
    if packages_path.suffix != ".nix":
        raise ValueError(
            f"packages_file doit être un fichier .nix, reçu : {packages_path}"
        )
    packages_path = packages_path.resolve()
    anchor = os.environ.get("NIXPICK_PACKAGES_ANCHOR") or nix.get(
        "packages_anchor", DEFAULT_ANCHOR
    )
    if not isinstance(anchor, str) or not anchor.strip():
        raise ValueError("packages_anchor doit être une chaîne non vide")
    rebuild = os.environ.get("NIXPICK_REBUILD_COMMAND") or nix.get(
        "rebuild_command", DEFAULT_REBUILD
    )
    if isinstance(rebuild, str):
        # Backward compatibility: old configs used a shell-like command string.
        # Parse arguments, but never evaluate shell operators or substitutions.
        rebuild_argv = tuple(shlex.split(rebuild))
    elif isinstance(rebuild, list) and all(isinstance(arg, str) for arg in rebuild):
        rebuild_argv = tuple(rebuild)
    else:
        raise ValueError("rebuild_command doit être une chaîne ou une liste d'arguments")
    if not rebuild_argv or any(not arg for arg in rebuild_argv):
        raise ValueError("rebuild_command ne peut pas être vide")

    _settings = Settings(
        packages_file=packages_path,
        packages_anchor=anchor.strip(),
        rebuild_command=rebuild_argv,
    )
    return _settings


def reset_settings_cache() -> None:
    """Tests / rechargement après écriture de config."""
    global _settings
    _settings = None


def format_rebuild_command() -> str:
    """Affichage lisible de rebuild_command (argv, pas d'interprétation shell)."""
    return shlex.join(get_settings().rebuild_command)


def _installed_asset_roots() -> list[Path]:
    """Répertoires ``share/nixpick`` (venv, Nix store, /usr)."""
    roots: list[Path] = []
    seen: set[Path] = set()
    for base in PACKAGE_ROOT.parents:
        candidate = base / "share" / "nixpick"
        if candidate.is_dir() and candidate not in seen:
            roots.append(candidate)
            seen.add(candidate)
            break
    prefix_share = Path(__import__("sys").prefix) / "share" / "nixpick"
    if prefix_share.is_dir() and prefix_share not in seen:
        roots.append(prefix_share)
    return roots


def asset_path(*parts: str) -> Path:
    """Fichiers embarqués (dev : dépôt ; install : share/nixpick/)."""
    local = PACKAGE_ROOT.joinpath("assets", *parts)
    if local.exists():
        return local
    for root in _installed_asset_roots():
        installed = root.joinpath(*parts)
        if installed.exists():
            return installed
    return local


def rofi_theme_paths(query_only: bool) -> list[Path]:
    """Ordre de recherche des thèmes Rofi (générés dans CONFIG_DIR/rofi si présents)."""
    from rofi_theme import sync_rofi_themes

    sync_rofi_themes()
    name = "nixpick-query.rasi" if query_only else "nixpick.rasi"
    return [
        CONFIG_DIR / "rofi" / name,
        Path.home() / ".config/rofi" / name,
        asset_path("rofi", name),
    ]
