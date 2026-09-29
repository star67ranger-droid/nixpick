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
        print("rebuild_command vide — configure config.toml ou NIXPICK_REBUILD_COMMAND.", file=sys.stderr)
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
                "Rebuild non lancé : pas de terminal interactif.\n"
                f"  {display_cmd}\n"
                "Utilise : nixpick rebuild --yes",
                file=sys.stderr,
            )
            return 1
        try:
            answer = input(f"Lancer le rebuild ?\n  {display_cmd}\n[o/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return 1
        if not is_affirmative(answer):
            return 0

    if in_terminal:
        configured = os.environ.get("NIXPICK_REBUILD_TERMINAL", "").strip()
        if configured and shutil.which(configured) is None:
            print(
                f"NIXPICK_REBUILD_TERMINAL={configured} introuvable — "
                "repli sur le terminal détecté.",
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
            "Rebuild terminal : aucun émulateur trouvé (kitty, foot, alacritty, wezterm).",
            file=sys.stderr,
        )
        print(f"Lance manuellement : {display_cmd}", file=sys.stderr)
        return 1

    proc = subprocess.run(argv, check=False)
    code = int(proc.returncode or 0)
    if code != 0:
        _print_rebuild_hints()
    return code


def _print_rebuild_hints() -> None:
    print("\n— Aide nixpick (relis l’erreur Nix ci-dessus) —", file=sys.stderr)
    ok_git, git_detail = check_flake_untracked()
    if not ok_git:
        print("  • Fichiers non suivis par Git :", file=sys.stderr)
        for line in git_detail.splitlines():
            print(f"    {line}", file=sys.stderr)
    else:
        root = nixos_flake_root()
        hint_root = str(root) if root else "/etc/nixos"
        print(
            f"  • Fichier « not tracked by Git » : le flake ne voit que ce qui est "
            f"dans git — ex. git -C {hint_root} add dotfiles/…/fichier",
            file=sys.stderr,
        )
    ok, _detail = check_nixpick_flake_lock()
    if not ok:
        root = nixos_flake_root()
        if root:
            print(
                "  • Si le message cite « NAR hash mismatch » et nixpick :",
                file=sys.stderr,
            )
            print(f"      {flake_lock_update_hint(root)}", file=sys.stderr)
        else:
            print(
                "  • Input path nixpick : mets à jour flake.lock après changement du code.",
                file=sys.stderr,
            )

