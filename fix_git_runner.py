"""``nixpick fix-git`` : git add des fichiers non suivis du dépôt flake."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from flake_git import (
    check_flake_untracked,
    format_git_add_command,
    untracked_git_add_target,
)


def run_fix_git(*, yes: bool = False, dry_run: bool = False) -> int:
    target = untracked_git_add_target()
    if target is None:
        ok, detail = check_flake_untracked()
        if ok:
            print("Aucun fichier non suivi (??) dans le dépôt du flake.")
            return 0
        print(detail, file=sys.stderr)
        return 1

    git_top, paths = target
    shown = paths[:20]
    extra = len(paths) - len(shown)

    if dry_run:
        print(f"[dry-run] {format_git_add_command(git_top, paths)}")
        return 0

    if not yes:
        if not sys.stdin.isatty():
            print(
                "fix-git non lancé : pas de terminal interactif.\n"
                f"  {format_git_add_command(git_top, paths)}\n"
                "Utilise : nixpick fix-git --yes",
                file=sys.stderr,
            )
            return 1
        print(f"Ajouter {len(paths)} fichier(s) non suivi(s) au dépôt {git_top} ?")
        for p in shown:
            print(f"  • {p}")
        if extra > 0:
            print(f"  … et {extra} autre(s).")
        try:
            answer = input("[o/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return 1
        if answer not in ("o", "oui", "y", "yes"):
            return 0

    try:
        proc = subprocess.run(
            ["git", "-C", str(git_top), "add", *paths],
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        print(f"git add a échoué : {err}", file=sys.stderr)
        return 1

    if proc.returncode != 0:
        print(f"git add a quitté avec le code {proc.returncode}.", file=sys.stderr)
        return int(proc.returncode or 1)

    print(f"{len(paths)} fichier(s) ajoutés au suivi git.")
    print("Étape suivante : git commit (si tu veux versionner), puis nixpick rebuild")
    return 0
