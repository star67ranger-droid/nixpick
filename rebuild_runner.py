"""Lance la commande rebuild configurée (jamais sans confirmation explicite)."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys

from engine import rebuild_command
from flake_git import check_flake_untracked, rebuild_preflight_message
from flake_lock import (
    check_nixpick_flake_lock,
    flake_lock_update_hint,
    nixos_flake_root,
)
from i18n import t
from messages import is_affirmative


def _default_terminal() -> str | None:
    for name in ("kitty", "foot", "alacritty", "wezterm"):
        if shutil.which(name):
            return name
    return None


def _terminal_argv(term: str, inner: str) -> list[str]:
    """Argv par terminal : `kitty` n'a pas d'option `-e` (vérifié via
    `kitty --help` — `kitty prog…` directement). foot/alacritty/wezterm
    gardent `-e` (non vérifiés sur cette machine)."""
    if term == "kitty":
        return [term, "bash", "-lc", inner]
    return [term, "-e", "bash", "-lc", inner]


def run_rebuild(
    *,
    yes: bool = False,
    in_terminal: bool = False,
    dry_run: bool = False,
) -> int:
    """Exécute rebuild_command. Retourne le code de sortie du sous-processus."""
    argv = list(rebuild_command())
    if not argv:
        print(t("rb.empty_cmd"), file=sys.stderr)
        return 1
    display_cmd = shlex.join(argv)

    if dry_run:
        print(f"[dry-run] {display_cmd}")
        return 0

    preflight = rebuild_preflight_message()
    if preflight:
        print(preflight, file=sys.stderr)
        return 1

    if not yes:
        if not sys.stdin.isatty():
            print(
                t("rb.no_tty", cmd=display_cmd),
                file=sys.stderr,
            )
            return 1
        try:
            answer = input(t("rb.confirm", cmd=display_cmd)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return 1
        if not is_affirmative(answer):
            return 0

    if in_terminal:
        configured = os.environ.get("NIXPICK_REBUILD_TERMINAL", "").strip()
        if configured and shutil.which(configured) is None:
            print(
                t("rb.term_invalid", term=configured),
                file=sys.stderr,
            )
            configured = ""
        term = configured or _default_terminal()
        if term:
            inner = (
                f"{shlex.join(argv)}; status=$?; echo; "
                "read -r -p 'Terminé — Entrée pour fermer…' _; exit $status"
            )
            proc = subprocess.run(_terminal_argv(term, inner), check=False)
            return int(proc.returncode or 0)
        print(
            t("rb.no_term"),
            file=sys.stderr,
        )
        print(t("rb.manual", cmd=display_cmd), file=sys.stderr)
        return 1

    proc = subprocess.run(argv, check=False)
    code = int(proc.returncode or 0)
    if code != 0:
        _print_rebuild_hints()
    return code


def _print_rebuild_hints() -> None:
    print(t("rb.hints_title"), file=sys.stderr)
    ok_git, git_detail = check_flake_untracked()
    if not ok_git:
        print(t("rb.hints_untracked"), file=sys.stderr)
        for line in git_detail.splitlines():
            print(f"    {line}", file=sys.stderr)
    else:
        root = nixos_flake_root()
        hint_root = str(root) if root else "/etc/nixos"
        print(
            t("rb.hints_tracked", root=hint_root),
            file=sys.stderr,
        )
    ok, _detail = check_nixpick_flake_lock()
    if not ok:
        root = nixos_flake_root()
        if root:
            print(
                t("rb.hints_nar"),
                file=sys.stderr,
            )
            print(f"      {flake_lock_update_hint(root)}", file=sys.stderr)
        else:
            print(
                t("rb.hints_path_note"),
                file=sys.stderr,
            )

