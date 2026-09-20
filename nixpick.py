#!/usr/bin/env python3
"""nixpick — chercher un paquet nixpkgs et l'ajouter à la config NixOS.

Sans argument : interface TUI.
Avec un terme : mode CLI rapide (comme avant).

Exemples :
    nixpick                  # TUI
    nixpick firefox          # CLI
    nixpick --refresh        # TUI, index reconstruit au démarrage
    nixpick --dry-run obsidian
"""

from __future__ import annotations

import argparse
import sys

from cli import run_cli, run_cli_remove
from config import __version__, get_settings
from engine import build_index
from rofi_mode import run_rofi
from tui import run_tui


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="nixpick",
        description="Cherche un paquet nixpkgs et modifie environment.systemPackages.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="affiche le fichier cible et la commande rebuild puis quitte",
    )
    parser.add_argument(
        "term",
        nargs="?",
        help="recherche en mode CLI (sinon ouvre la TUI)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="reconstruit l'index nixpkgs au démarrage",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="simulation : n'écrit pas dans packages.nix",
    )
    parser.add_argument(
        "--transparent",
        action="store_true",
        help="TUI : fond transparent (comme superfile)",
    )
    parser.add_argument(
        "--opaque",
        action="store_true",
        help="TUI : fond opaque (ignore la config)",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="force la TUI même si un terme est passé",
    )
    parser.add_argument(
        "--rofi",
        action="store_true",
        help="lance la recherche via Rofi (barre glass)",
    )
    parser.add_argument(
        "--build-index-only",
        action="store_true",
        help="reconstruit l'index puis quitte (sans TUI)",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="retire un paquet de environment.systemPackages (avec le terme CLI)",
    )
    args = parser.parse_args()

    if args.print_config:
        s = get_settings()
        print(f"packages_file={s.packages_file}")
        print(f"packages_anchor={s.packages_anchor}")
        print(f"rebuild_command={s.rebuild_command}")
        return 0

    if args.build_index_only:
        build_index(on_status=lambda m: print(m, file=sys.stderr))
        return 0

    if args.rofi:
        return run_rofi(refresh=args.refresh, dry_run=args.dry_run)

    if args.term and not args.tui:
        if args.remove:
            return run_cli_remove(args.term, dry_run=args.dry_run)
        return run_cli(args.term, refresh=args.refresh, dry_run=args.dry_run)

    transparent: bool | None = None
    if args.transparent:
        transparent = True
    elif args.opaque:
        transparent = False

    return run_tui(
        refresh=args.refresh,
        dry_run=args.dry_run,
        transparent=transparent,
    )


if __name__ == "__main__":
    sys.exit(main())
