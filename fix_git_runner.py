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
from i18n import t
from messages import is_affirmative


def run_fix_git(*, yes: bool = False, dry_run: bool = False) -> int:
    flake_root = nixos_flake_root()
    if flake_root is None:
        print(t("git.no_flake"), file=sys.stderr)
        return 1

    if git_top_for_flake(flake_root) is None:
        print(t("git.no_repo", root=flake_root), file=sys.stderr)
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

    # Inventaire toujours affiché — y compris avec -y : on ne devine jamais
    # ce qui va être ajouté au dépôt.
    print(t("git.inventory", top=git_top, n=len(paths)))
    for p in shown:
        print(f"  • {p}")
    if extra > 0:
        print(t("git.inventory_more", n=extra))

    if not yes:
        if not sys.stdin.isatty():
            print(
                t("git.no_tty", cmd=format_git_add_command(git_top, paths)),
                file=sys.stderr,
            )
            return 1
        try:
            answer = input(t("git.confirm", n=len(paths))).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return 1
        if not is_affirmative(answer):
            return 0

    code = git_add_untracked(git_top, paths)
    if code != 0:
        print(t("git.exit_code", code=code), file=sys.stderr)
        return code

    print(t("git.added", n=len(paths)))
    print(t("git.next"))
    return 0
