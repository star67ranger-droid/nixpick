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

from cli import run_cli
from engine import build_index
from tui import run_tui


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cherche un paquet nixpkgs et l'ajoute à environment.systemPackages."
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
        "--tui",
        action="store_true",
        help="force la TUI même si un terme est passé",
    )
    parser.add_argument(
        "--build-index-only",
        action="store_true",
        help="reconstruit l'index puis quitte (sans TUI)",
    )
    args = parser.parse_args()

    if args.build_index_only:
        build_index(on_status=lambda m: print(m, file=sys.stderr))
        return 0

    if args.term and not args.tui:
        return run_cli(args.term, refresh=args.refresh, dry_run=args.dry_run)

    return run_tui(refresh=args.refresh, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
