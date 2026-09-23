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
import json
import sys

from cli import run_cli, run_cli_remove
from config import __version__, get_settings
from doctor import run_doctor, run_why
from engine import (
    build_index,
    index_age_days,
    list_installed_attrs,
    packages_file,
    undo_last_write,
)
from fix_git_runner import run_fix_git
from rebuild_runner import run_rebuild
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
    subparsers = parser.add_subparsers(dest="command")
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="vérifie config, cache, outils (sans lancer Nix)",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help="sortie JSON (checks structurés)",
    )
    rebuild_parser = subparsers.add_parser(
        "rebuild",
        help="lance la commande rebuild configurée (confirmée)",
    )
    rebuild_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="sans demander confirmation (utile en script)",
    )
    rebuild_parser.add_argument(
        "--terminal",
        action="store_true",
        help="ouvre un émulateur (kitty, foot…) pour sudo / la sortie",
    )
    rebuild_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="affiche la commande rebuild sans l'exécuter",
    )
    fix_git_parser = subparsers.add_parser(
        "fix-git",
        help="git add les fichiers non suivis (??) du dépôt flake NixOS",
    )
    fix_git_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="sans demander confirmation",
    )
    fix_git_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="affiche la commande git sans l'exécuter",
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
    parser.add_argument(
        "--list-installed",
        action="store_true",
        help="liste les attributs déjà présents dans environment.systemPackages",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="avec --list-installed : une ligne JSON (attrs, count, packages_file, index_age_days)",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="restaure packages.nix depuis la dernière sauvegarde (sans rebuild)",
    )
    parser.add_argument(
        "--why",
        metavar="ATTR",
        help="indique si un attribut est dans le fichier packages configuré",
    )
    args = parser.parse_args()

    if args.command == "doctor":
        return run_doctor(as_json=args.json)

    if args.command == "rebuild":
        return run_rebuild(
            yes=args.yes,
            in_terminal=args.terminal,
            dry_run=args.dry_run,
        )

    if args.command == "fix-git":
        return run_fix_git(yes=args.yes, dry_run=args.dry_run)

    if args.print_config:
        s = get_settings()
        print(f"packages_file={s.packages_file}")
        print(f"packages_file_resolved={s.packages_file.resolve()}")
        print(f"packages_anchor={s.packages_anchor}")
        print(f"rebuild_command={s.rebuild_command}")
        return 0

    if args.why is not None:
        return run_why(args.why)

    if args.list_installed:
        if args.json:
            attrs = sorted(list_installed_attrs())
            print(
                json.dumps(
                    {
                        "attrs": attrs,
                        "count": len(attrs),
                        "packages_file": str(packages_file()),
                        "index_age_days": index_age_days(),
                    },
                    ensure_ascii=False,
                )
            )
        else:
            for attr in sorted(list_installed_attrs()):
                print(attr)
        return 0

    if args.undo:
        result = undo_last_write()
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.code

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
