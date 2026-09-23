"""``nixpick fix-git`` : git add des fichiers non suivis du dépôt flake."""

from __future__ import annotations

import sys

from flake_git import (
    check_flake_untracked,
    format_git_add_command,
    git_add_untracked,
    git_top_for_flake,
    list_untracked_paths,
    untracked_git_add_target,
)
from flake_lock import nixos_flake_root


def run_fix_git(*, yes: bool = False, dry_run: bool = False) -> int:
    flake_root = nixos_flake_root()
    if flake_root is None:
        print("Pas de flake NixOS détecté (packages_file hors arbre flake).", file=sys.stderr)
        return 1

    if git_top_for_flake(flake_root) is None:
        print(f"{flake_root} : pas de dépôt git — fix-git impossible.", file=sys.stderr)
        return 1

    paths, err = list_untracked_paths(flake_root)
    if err:
        print(err, file=sys.stderr)
        return 1

    target = untracked_git_add_target()
    if target is None:
        ok, detail = check_flake_untracked()
        print(detail)
        return 0 if ok else 1

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

    code = git_add_untracked(git_top, paths)
    if code != 0:
        print(f"git add a quitté avec le code {code}.", file=sys.stderr)
        return code

    print(f"{len(paths)} fichier(s) ajoutés au suivi git.")
    print("Étape suivante : git commit (si tu veux versionner), puis nixpick rebuild")
    return 0
