"""Fichiers Git non suivis dans le dépôt flake NixOS (bloquent souvent nix build)."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from flake_lock import nixos_flake_root

_MAX_LISTED = 24


def _git_root_for_flake(flake_root: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(flake_root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    top = proc.stdout.strip()
    return Path(top) if top else None


def list_untracked_paths(flake_root: Path) -> list[str]:
    """Chemins relatifs au dépôt git (lignes ``??`` de ``git status --porcelain``)."""
    git_top = _git_root_for_flake(flake_root)
    if git_top is None:
        return []
    try:
        proc = subprocess.run(
            ["git", "-C", str(git_top), "status", "--porcelain", "-u"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4 or not line.startswith("??"):
            continue
        rel = line[3:].strip()
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1].strip()
        if rel:
            paths.append(rel)
    return sorted(paths)


def untracked_git_add_target() -> tuple[Path, list[str]] | None:
    """``(dépôt git, chemins relatifs ??)`` ou ``None`` s'il n'y a rien à ajouter."""
    flake_root = nixos_flake_root()
    if flake_root is None:
        return None
    git_top = _git_root_for_flake(flake_root)
    if git_top is None:
        return None
    paths = list_untracked_paths(flake_root)
    if not paths:
        return None
    return git_top, paths


def format_git_add_command(git_top: Path, rel_paths: list[str]) -> str:
    if not rel_paths:
        return f'git -C {shlex.quote(str(git_top))} add …'
    quoted = " ".join(shlex.quote(p) for p in rel_paths)
    return f"git -C {shlex.quote(str(git_top))} add {quoted}"


def check_flake_untracked() -> tuple[bool, str]:
    """
    Retourne (ok, detail).
    ok=False si le flake est dans un dépôt git avec des fichiers non suivis.
    """
    flake_root = nixos_flake_root()
    if flake_root is None:
        return True, "Pas de flake NixOS détecté (check Git ignoré)."

    git_top = _git_root_for_flake(flake_root)
    if git_top is None:
        return True, f"{flake_root} : pas de dépôt git (check ignoré)."

    untracked = list_untracked_paths(flake_root)
    if not untracked:
        rel_flake = flake_root
        try:
            rel_flake = flake_root.resolve().relative_to(git_top.resolve())
        except ValueError:
            rel_flake = flake_root
        return (
            True,
            f"Dépôt {git_top} : aucun fichier non suivi (??). Flake : {rel_flake}/",
        )

    shown = untracked[:_MAX_LISTED]
    extra = len(untracked) - len(shown)
    lines = [
        f"{len(untracked)} fichier(s) non suivi(s) — le flake ne les voit pas tant qu'ils ne sont pas dans git :",
    ]
    for p in shown:
        lines.append(f"      • {p}")
    if extra > 0:
        lines.append(f"      … et {extra} autre(s).")
    lines.append("")
    lines.append(f"      {format_git_add_command(git_top, shown if extra == 0 else untracked)}")
    if extra > 0:
        lines.append("      (commande ci-dessus inclut tous les fichiers non suivis.)")
    return False, "\n".join(lines)


def rebuild_preflight_message() -> str | None:
    ok, detail = check_flake_untracked()
    if ok:
        return None
    return (
        "Rebuild bloqué avant lancement : des fichiers du flake ne sont pas suivis par Git.\n"
        f"{detail}\n"
        "Puis : nixpick fix-git   ou   nixpick rebuild"
    )


def rebuild_preflight_notify_body() -> str | None:
    """Résumé court pour notify-send / Rofi (1ère commande git utile)."""
    ok, detail = check_flake_untracked()
    if ok:
        return None
    for line in detail.splitlines():
        stripped = line.strip()
        if stripped.startswith("git -C"):
            return (
                "Fichiers non suivis dans le dépôt flake.\n"
                f"{stripped}\n"
                "Puis : nixpick fix-git\nou nixpick rebuild"
            )
    first = detail.splitlines()[0].strip() if detail else "Git flake"
    return f"{first}\nLance : nixpick fix-git ou nixpick doctor"
