"""Messages utilisateur (CLI, Rofi, notifications)."""

from __future__ import annotations

from pathlib import Path

from config import format_rebuild_command, is_nixos
from engine import AddFailure, RemoveFailure

ROFI_CONFIRM_ADD = "Confirmer l'ajout"
ROFI_CONFIRM_REMOVE = "Confirmer le retrait"
ROFI_CANCEL = "Annuler"
ROFI_REBUILD_NOW = "󰐊 Lancer le rebuild"
ROFI_REBUILD_LATER = "Plus tard"
ROFI_FIX_GIT = "󰊢 Corriger Git (fix-git)"


ISSUES_URL = "https://github.com/star67ranger-droid/nixpick/issues"
ROFI_SYNC_NOW = "Installer via sync"


def is_affirmative(answer: str) -> bool:
    """Un seul prédicat de confirmation partout (o/oui/y/yes)."""
    return answer.strip().lower() in ("o", "oui", "y", "yes")


def cli_cancelled() -> str:
    return "Abandonné."


def apply_hint() -> str:
    """Consigne d'application selon la plateforme (source unique)."""
    return "nixpick sync" if not is_nixos() else "nixpick rebuild"


def cli_success_lines(backup_path: Path) -> list[str]:
    lines = [f"Sauvegarde : {backup_path}", ""]
    if is_nixos():
        lines += [
            "Pour appliquer : nixpick rebuild",
            f"  ({format_rebuild_command()})",
        ]
    else:
        lines += [
            "Pour installer : nixpick sync",
            "  (nix profile install nixpkgs#… des listés)",
        ]
    return lines


def diff_preview_text(context_lines: list[str], packages_file: Path) -> str:
    header = str(packages_file)
    sep = "─" * min(48, max(len(header), 16))
    body = "\n".join(context_lines)
    return f"{header}\n{sep}\n{body}"


def rofi_confirm_choices(*, remove: bool) -> list[str]:
    if remove:
        return [ROFI_CONFIRM_REMOVE, ROFI_CANCEL]
    return [ROFI_CONFIRM_ADD, ROFI_CANCEL]


def notify_search_too_short() -> tuple[str, str]:
    return (
        "nixpick",
        "Tape au moins 2 caractères.\nEssaie un nom de paquet ou d'attribut nixpkgs.",
    )


def notify_index_error(detail: str) -> tuple[str, str]:
    return (
        "nixpick — index",
        f"{detail}\nReconstruis l'index : nixpick --build-index-only",
    )


def notify_not_found(term: str) -> tuple[str, str]:
    return (
        "nixpick",
        f"Rien trouvé pour « {term} ».\nEssaie un autre terme ou vérifie l'orthographe.",
    )


def notify_remove_failure(plan: RemoveFailure) -> tuple[str, str]:
    return ("nixpick", plan.message)


def notify_add_failure(plan: AddFailure) -> tuple[str, str]:
    return ("nixpick", plan.message)


def notify_permission_denied(packages_file: Path) -> tuple[str, str]:
    return (
        "nixpick",
        (
            f"Pas les droits d'écriture sur {packages_file}.\n"
            "Vérifie les permissions ou adapte NIXPICK_PACKAGES_FILE."
        ),
    )


def notify_dry_run_remove(attr: str) -> tuple[str, str]:
    return (
        "nixpick (dry-run)",
        f"{attr} aurait été retiré — aucune modification sur le disque.",
    )


def notify_dry_run_add(attr: str) -> tuple[str, str]:
    return (
        "nixpick (dry-run)",
        f"{attr} aurait été ajouté — aucune modification sur le disque.",
    )


def rofi_rebuild_choices(*, git_ok: bool = True) -> list[str]:
    if not git_ok:
        return [ROFI_FIX_GIT, ROFI_REBUILD_NOW, ROFI_REBUILD_LATER]
    return [ROFI_REBUILD_NOW, ROFI_REBUILD_LATER]


def _success_body(backup_path: Path) -> str:
    if is_nixos():
        how = f"Applique avec : nixpick rebuild\n({format_rebuild_command()})"
    else:
        how = "Installe avec : nixpick sync"
    return f"Sauvegarde : {backup_path}\n{how}"


def notify_success_remove(attr: str, backup_path: Path) -> tuple[str, str]:
    return (f"nixpick · {attr} retiré", _success_body(backup_path))


def notify_success_add(attr: str, backup_path: Path) -> tuple[str, str]:
    return (f"nixpick · {attr} ajouté", _success_body(backup_path))
