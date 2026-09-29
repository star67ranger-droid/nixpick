"""Mode ligne de commande (un terme en argument)."""

from __future__ import annotations

import sys

from config import is_nixos
from engine import (
    DEFAULT_RESULT_LIMIT,
    AddFailure,
    NixCommandError,
    NixSyntaxError,
    RemoveFailure,
    commit_add,
    commit_remove,
    fetch_descriptions,
    load_index,
    plan_add,
    plan_remove,
    search,
)
from flake_git import rebuild_preflight_message
from messages import cli_cancelled, cli_success_lines, is_affirmative
from rebuild_runner import run_rebuild
from sync_runner import install_profile_refs

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
    if not is_affirmative(answer):
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
    except NixSyntaxError as err:
        say(f"{RED}{err}{RESET}")
        return 1

    say(f"{GREEN}Retiré.{RESET}")
    for line in cli_success_lines(plan.backup_path):
        say(line if line else "")
    if not is_nixos():
        # Pas de prune auto (décision assumée) : le retrait de la liste ne
        # désinstalle pas le profil — on donne la commande manuelle au lieu
        # de proposer un rebuild qui échouerait (FileNotFoundError).
        say(f"Retiré de la liste. Pour désinstaller du profil : nix profile remove {plan.attr}")
        return 0
    return _maybe_rebuild_after_cli()


def _maybe_rebuild_after_cli() -> int:
    try:
        answer = input("\nLancer nixpick rebuild maintenant ? [o/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        say()
        return 0
    if not is_affirmative(answer):
        return 0

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
        # ALREADY_LISTED est idempotent (comme NOT_LISTED côté retrait).
        return 0 if plan.outcome.name == "ALREADY_LISTED" else 1

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
    if not is_affirmative(answer):
        say(cli_cancelled())
        return 0

    try:
        commit_add(plan, dry_run=False)
    except PermissionError:
        say(f"{RED}Pas les droits d'écriture sur {plan.packages_file}.{RESET}")
        return 1
    except LookupError as err:
        say(f"{YELLOW}{err}{RESET}")
        return 1
    except NixSyntaxError as err:
        say(f"{RED}{err}{RESET}")
        return 1

    say(f"{GREEN}Ajouté.{RESET}")
    if plan.created_file:
        say(f"Fichier créé : {plan.packages_file}")
    for line in cli_success_lines(plan.backup_path):
        say(line if line else "")
    if not is_nixos():
        return _maybe_install_after_cli(plan.attr)
    return _maybe_rebuild_after_cli()


def _maybe_install_after_cli(attr: str) -> int:
    """Hors NixOS : propose d'installer l'attribut dans le profil.

    Retourne le code d'install (l'ajout reste acquis même en cas d'échec,
    le message le dit explicitement pour les scripts).
    """
    try:
        answer = input(f"\nInstaller nixpkgs#{attr} dans ton profil ? [o/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        say()
        return 0
    if not is_affirmative(answer):
        return 0
    code = install_profile_refs([f"nixpkgs#{attr}"])
    if code != 0:
        say(f"{RED}L'ajout a réussi, mais l'installation a échoué (code {code}).{RESET}")
    return code
