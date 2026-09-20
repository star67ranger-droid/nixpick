"""Détecte un flake.lock périmé pour l'input path nixpick (NAR hash mismatch au rebuild)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from engine import packages_file


def nixos_flake_root() -> Path | None:
    start = packages_file().resolve().parent
    for candidate in (start, *start.parents):
        if (candidate / "flake.nix").is_file() and (candidate / "flake.lock").is_file():
            return candidate
    return None


def _locked_nixpick_path(lock_data: dict) -> tuple[Path, str] | None:
    node = lock_data.get("nodes", {}).get("nixpick")
    if not node:
        return None
    locked = node.get("locked") or {}
    if locked.get("type") != "path":
        return None
    path_s = locked.get("path")
    nar = locked.get("narHash")
    if not path_s or not nar:
        return None
    return Path(path_s), str(nar)


def _path_nar_hash(path: Path) -> str | None:
    if not shutil.which("nix"):
        return None
    if not path.is_dir():
        return None
    try:
        proc = subprocess.run(
            ["nix", "hash", "path", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    # "sha256-..." ou chemin + hash selon version nix
    for part in line.split():
        if part.startswith("sha256-"):
            return part
    if line.startswith("sha256-"):
        return line
    return None


def flake_lock_update_hint(flake_root: Path, input_name: str = "nixpick") -> str:
    return f"cd {flake_root} && nix flake lock --update-input {input_name}"


def check_nixpick_flake_lock() -> tuple[bool, str]:
    """
    Retourne (ok, detail).
    ok=True si pas concerné ou lock à jour ; ok=False si hash diverge.
    """
    root = nixos_flake_root()
    if root is None:
        return True, "Pas de flake NixOS détecté à côté de packages_file (check ignoré)."

    lock_path = root / "flake.lock"
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return True, f"flake.lock illisible ({err}) — check ignoré."

    locked = _locked_nixpick_path(data)
    if locked is None:
        return True, "Aucun input path « nixpick » dans flake.lock (check ignoré)."

    nixpick_path, locked_hash = locked
    if not nixpick_path.is_dir():
        return (
            False,
            f"Input nixpick pointe vers {nixpick_path} (absent). "
            f"Corrige flake.nix ou le chemin.",
        )

    current = _path_nar_hash(nixpick_path)
    if current is None:
        return True, "Impossible de calculer le hash nix du dépôt nixpick (nix absent ?)."

    if current == locked_hash:
        return (
            True,
            f"flake.lock cohérent avec {nixpick_path.name} ({current[:20]}…).",
        )

    hint = flake_lock_update_hint(root)
    return (
        False,
        "flake.lock périmé pour l'input nixpick — le rebuild échouera "
        f"(NAR hash mismatch).\n"
        f"      lock : {locked_hash}\n"
        f"      actuel : {current}\n"
        f"      → {hint}",
    )
