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
import traceback

from cli import run_cli, run_cli_remove
from config import __version__, get_settings, resolve_language
from doctor import run_doctor, run_why
from engine import (
    NixCommandError,
    build_index,
    index_age_days,
    list_installed_attrs,
    load_index,
    packages_file,
    search,
    undo_last_write,
)
from errors import explain_error
from fix_git_runner import run_fix_git
from i18n import set_language, t
from messages import ISSUES_URL
from rebuild_runner import run_rebuild
from rofi_mode import run_rofi
from sync_runner import run_sync
from tui import run_tui


def main() -> int:
    """Point d'entrée : les erreurs inattendues affichent un traceback ET
    l'URL de signalement (sinon l'utilisateur ne sait pas quoi en faire)."""
    try:
        return _run()
    except KeyboardInterrupt:
        print(t("app.interrupted"), file=sys.stderr)
        return 130
    except Exception as err:  # noqa: BLE001 — garde-fou : toute erreur inattendue est signalée
        traceback.print_exc()
        advice = explain_error(err)
        if advice:
            print(advice, file=sys.stderr)
        print(t("app.report_bug", url=ISSUES_URL), file=sys.stderr)
        return 1


def _run() -> int:
    set_language(resolve_language())
    parser = argparse.ArgumentParser(
        prog="nixpick",
        description=t("app.desc"),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")
    doctor_parser = subparsers.add_parser(
        "doctor",
        help=t("app.help_doctor"),
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help=t("app.help_doctor_json"),
    )
    rebuild_parser = subparsers.add_parser(
        "rebuild",
        help=t("app.help_rebuild"),
    )
    rebuild_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=t("app.help_yes_script"),
    )
    rebuild_parser.add_argument(
        "--terminal",
        action="store_true",
        help=t("app.help_terminal"),
    )
    rebuild_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=t("app.help_dry_run"),
    )
    fix_git_parser = subparsers.add_parser(
        "fix-git",
        help=t("app.help_fix_git"),
    )
    fix_git_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=t("app.help_yes"),
    )
    fix_git_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=t("app.help_fix_git_dry"),
    )
    sync_parser = subparsers.add_parser(
        "sync",
        help=t("app.help_sync"),
    )
    sync_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=t("app.help_yes"),
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=t("app.help_sync_dry"),
    )
    sync_parser.add_argument(
        "--upgrade",
        action="store_true",
        help=t("app.help_sync_upgrade"),
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help=t("app.help_print_config"),
    )
    parser.add_argument(
        "term",
        nargs="?",
        help=t("app.help_term"),
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=t("app.help_refresh"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=t("app.help_dryrun"),
    )
    parser.add_argument(
        "--transparent",
        action="store_true",
        help=t("app.help_transparent"),
    )
    parser.add_argument(
        "--opaque",
        action="store_true",
        help=t("app.help_opaque"),
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help=t("app.help_tui"),
    )
    parser.add_argument(
        "--rofi",
        action="store_true",
        help=t("app.help_rofi"),
    )
    parser.add_argument(
        "--build-index-only",
        action="store_true",
        help=t("app.help_build_index"),
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help=t("app.help_remove"),
    )
    parser.add_argument(
        "--list-installed",
        action="store_true",
        help=t("app.help_list"),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=t("app.help_list_json"),
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help=t("app.help_undo"),
    )
    parser.add_argument(
        "--why",
        metavar="ATTR",
        help=t("app.help_why"),
    )
    parser.add_argument(
        "--print",
        dest="print_term",
        metavar="TERM",
        help=t("app.help_print"),
    )
    args = parser.parse_args()

    # SEC-01 : une config illisible/invalid ne doit pas être remplacée en
    # silence par les défauts (redirection d'écritures) : on refuse de démarrer.
    try:
        get_settings()
    except ValueError as err:
        print(t("app.error", err=err), file=sys.stderr)
        return 1

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

    if args.command == "sync":
        return run_sync(yes=args.yes, dry_run=args.dry_run, upgrade=args.upgrade)

    return _run_flags(args)


def _run_flags(args: argparse.Namespace) -> int:
    """Options globales (hors sous-commandes) : retours directs puis TUI/CLI."""
    if args.print_config:
        s = get_settings()
        print(f"packages_file={s.packages_file}")
        print(f"packages_file_resolved={s.packages_file.resolve()}")
        print(f"packages_anchor={s.packages_anchor}")
        print(f"rebuild_command={s.rebuild_command}")
        return 0

    if args.why is not None:
        return run_why(args.why)

    if args.print_term is not None:
        # Composable : seul l'attribut sur stdout (scripts, agents, shell).
        try:
            index = load_index(refresh=args.refresh)
        except NixCommandError as err:
            print(t("app.error", err=err), file=sys.stderr)
            return 1
        hits = search(index, args.print_term, limit=1)
        if not hits:
            print(t("cli.nothing_found", term=args.print_term), file=sys.stderr)
            return 1
        print(hits[0][0])
        return 0

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
        try:
            build_index(on_status=lambda m: print(m, file=sys.stderr))
        except NixCommandError as err:
            print(t("app.error", err=err), file=sys.stderr)
            advice = explain_error(err)
            if advice:
                print(advice, file=sys.stderr)
            return 1
        return 0

    if args.rofi:
        return run_rofi(refresh=args.refresh, dry_run=args.dry_run)

    if args.remove and not args.term:
        print(
            t("app.remove_needs_term"),
            file=sys.stderr,
        )
        return 2

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
