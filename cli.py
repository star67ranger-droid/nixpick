"""Mode ligne de commande (un terme en argument)."""

from __future__ import annotations

import sys

from engine import (
    DEFAULT_RESULT_LIMIT,
    AddFailure,
    NixCommandError,
    RemoveFailure,
    commit_add,
    commit_remove,
    fetch_descriptions,
    load_index,
    plan_add,
    plan_remove,
    search,
)
from messages import cli_cancelled, cli_success_lines
from rebuild_runner import run_rebuild

BOLD, DIM, GREEN, YELLOW, RED, RESET = (
    "\033[1m",
    "\033[2m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[0m",
)


def say(msg: str = "") -> None:
    print(msg, file=sys.stderr)


def run_cli_remove(term: str, dry_run: bool) -> int:
    plan = plan_remove(term.strip())
    if isinstance(plan, RemoveFailure):
        say(f"{YELLOW}{plan.message}{RESET}")
        return 0 if plan.outcome.name == "NOT_LISTED" else 1

    say()
    say(f"{BOLD}Suppression prévue dans {plan.packages_file} :{RESET}")
    for line in plan.context_lines:
        prefix = RED if line.startswith("-") else DIM
        say(f"  {prefix}{line}{RESET}")

    if dry_run:
        say(f"\n{DIM}Mode --dry-run : rien n'écrit.{RESET}")
        return 0

    try:
        answer = input("\nJe retire ? [o/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        say()
        return 1
    if answer not in ("o", "oui", "y"):
        say(cli_cancelled())
        return 0

    try:
        commit_remove(plan, dry_run=False)
    except PermissionError:
        say(f"{RED}Pas les droits d'écriture sur {plan.packages_file}.{RESET}")
        return 1
    except LookupError as err:
        say(f"{RED}{err}{RESET}")
        return 1

    say(f"{GREEN}Retiré.{RESET}")
    for line in cli_success_lines(plan.backup_path):
        say(line if line else "")
    return _maybe_rebuild_after_cli()


def _maybe_rebuild_after_cli() -> int:
    try:
        answer = input("\nLancer nixpick rebuild maintenant ? [o/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        say()
        return 0
    if answer not in ("o", "oui", "y"):
        return 0
    from flake_git import rebuild_preflight_message

    preflight = rebuild_preflight_message()
    if preflight:
        say(preflight)
        say("\nLance : nixpick fix-git --yes   puis   nixpick rebuild")
        return 1
    return run_rebuild(yes=True, in_terminal=False)


def run_cli(term: str, refresh: bool, dry_run: bool) -> int:
    try:
        index = load_index(refresh=refresh, on_status=say)
    except NixCommandError as err:
        say(f"{RED}{err}{RESET}")
        return 1

    results = search(index, term, limit=DEFAULT_RESULT_LIMIT)
    if not results:
        say(f"{YELLOW}Rien trouvé pour « {term} ».{RESET}")
        return 1

    descriptions = fetch_descriptions([a for a, _ in results])
    say()
    for n, (attr, version) in enumerate(results, 1):
        desc = (descriptions.get(attr) or "")[:70]
        say(f"  {BOLD}{n:>2}{RESET}. {GREEN}{attr}{RESET} {DIM}{version}{RESET}")
        if desc:
            say(f"      {DIM}{desc}{RESET}")

    try:
        choice = input(f"\nLequel ? [1-{len(results)}, Entrée pour annuler] ").strip()
    except (EOFError, KeyboardInterrupt):
        say()
        return 1

    if not choice:
        return 0
    if not choice.isdigit() or not 1 <= int(choice) <= len(results):
        say(f"{RED}Choix invalide.{RESET}")
        return 1

    attr, _ = results[int(choice) - 1]
    plan = plan_add(attr, descriptions.get(attr, ""))
    if isinstance(plan, AddFailure):
        say(f"{YELLOW}{plan.message}{RESET}")
        return 0

    say()
    say(f"{BOLD}Modification prévue dans {plan.packages_file} :{RESET}")
    for line in plan.context_lines:
        prefix = GREEN if line.startswith("+") else DIM
        say(f"  {prefix}{line}{RESET}")

    if dry_run:
        say(f"\n{DIM}Mode --dry-run : rien n'écrit.{RESET}")
        return 0

    try:
        answer = input("\nJ'écris ? [o/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        say()
        return 1
    if answer not in ("o", "oui", "y"):
        say(cli_cancelled())
        return 0

    try:
        commit_add(plan, dry_run=False)
    except PermissionError:
        say(f"{RED}Pas les droits d'écriture sur {plan.packages_file}.{RESET}")
        return 1

    say(f"{GREEN}Ajouté.{RESET}")
    for line in cli_success_lines(plan.backup_path):
        say(line if line else "")
    return _maybe_rebuild_after_cli()
