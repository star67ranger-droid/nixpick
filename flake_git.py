"""Fichiers Git non suivis dans le dépôt flake NixOS (bloquent souvent nix build)."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from flake_lock import nixos_flake_root

_MAX_LISTED = 24
_GIT_ADD_BATCH = 200


def git_top_for_flake(flake_root: Path) -> Path | None:
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


def _flake_path_prefix(flake_root: Path, git_top: Path) -> str | None:
    """Préfixe relatif au dépôt git pour limiter les ?? au répertoire flake."""
    try:
        rel = flake_root.resolve().relative_to(git_top.resolve())
    except ValueError:
        return None
    if rel.parts == ():
        return ""
    return rel.as_posix()


def _path_under_flake_prefix(rel_path: str, prefix: str) -> bool:
    if prefix == "":
        return True
    norm = rel_path.replace("\\", "/")
    return norm == prefix or norm.startswith(prefix + "/")


def list_untracked_paths(flake_root: Path) -> tuple[list[str], str | None]:
    """
    Chemins ``??`` relatifs au dépôt git, filtrés sous ``flake_root``.
    Retourne ``(chemins, erreur)`` ; ``erreur`` si ``git status`` a échoué.
    """
    git_top = git_top_for_flake(flake_root)
    if git_top is None:
        return [], None
    try:
        proc = subprocess.run(
            ["git", "-C", str(git_top), "status", "--porcelain", "-u"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        return [], f"git status indisponible : {err}"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return [], f"git status a échoué (code {proc.returncode}). {err}".strip()

    prefix = _flake_path_prefix(flake_root, git_top)
    if prefix is None:
        return [], None

    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4 or not line.startswith("??"):
            continue
        rel = line[3:].strip()
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1].strip()
        if rel and _path_under_flake_prefix(rel, prefix):
            paths.append(rel)
    return sorted(paths), None


def untracked_git_add_target() -> tuple[Path, list[str]] | None:
    """``(dépôt git, chemins relatifs ??)`` ou ``None`` s'il n'y a rien à ajouter."""
    flake_root = nixos_flake_root()
    if flake_root is None:
        return None
    git_top = git_top_for_flake(flake_root)
    if git_top is None:
        return None
    paths, err = list_untracked_paths(flake_root)
    if err or not paths:
        return None
    return git_top, paths


def format_git_add_command(git_top: Path, rel_paths: list[str]) -> str:
    if not rel_paths:
        return f'git -C {shlex.quote(str(git_top))} add -- …'
    quoted = " ".join(shlex.quote(p) for p in rel_paths)
    return f"git -C {shlex.quote(str(git_top))} add -- {quoted}"


def git_add_untracked(git_top: Path, paths: list[str]) -> int:
    """``git add --`` par lots ; ignore les chemins invalides. Retourne code git."""
    safe = [
        p
        for p in paths
        if p and "\n" not in p and not p.startswith("-")
    ]
    if len(safe) < len(paths):
        print(
            f"Attention : {len(paths) - len(safe)} chemin(s) ignoré(s) (nom invalide).",
            file=__import__("sys").stderr,
        )
    if not safe:
        return 1
    code = 0
    for offset in range(0, len(safe), _GIT_ADD_BATCH):
        chunk = safe[offset : offset + _GIT_ADD_BATCH]
        proc = subprocess.run(
            ["git", "-C", str(git_top), "add", "--", *chunk],
            check=False,
            timeout=120,
        )
        if proc.returncode != 0:
            return int(proc.returncode or 1)
    return code


def check_flake_untracked() -> tuple[bool, str]:
    """
    Retourne (ok, detail).
    ok=False si le flake est dans un dépôt git avec des fichiers non suivis (sous le flake).
    """
    flake_root = nixos_flake_root()
    if flake_root is None:
        return True, "Pas de flake NixOS détecté (check Git ignoré)."

    git_top = git_top_for_flake(flake_root)
    if git_top is None:
        return True, f"{flake_root} : pas de dépôt git (check ignoré)."

    untracked, err = list_untracked_paths(flake_root)
    if err:
        return False, err

    if not untracked:
        rel_flake = flake_root
        try:
            rel_flake = flake_root.resolve().relative_to(git_top.resolve())
        except ValueError:
            rel_flake = flake_root
        return (
            True,
            f"Dépôt {git_top} : aucun fichier non suivi (??) sous le flake. Racine flake : {rel_flake}/",
        )

    shown = untracked[:_MAX_LISTED]
    extra = len(untracked) - len(shown)
    lines = [
        f"{len(untracked)} fichier(s) non suivi(s) sous le flake — Nix ne les voit pas tant qu'ils ne sont pas dans git :",
    ]
    for p in shown:
        lines.append(f"      • {p}")
    if extra > 0:
        lines.append(f"      … et {extra} autre(s).")
    lines.append("")
    cmd_paths = shown if extra == 0 else untracked
    lines.append(f"      {format_git_add_command(git_top, cmd_paths)}")
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
