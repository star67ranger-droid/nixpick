"""Messages utilisateur (CLI, Rofi, notifications)."""

from __future__ import annotations

from pathlib import Path

from config import format_rebuild_command, is_nixos
from engine import AddFailure, RemoveFailure
from i18n import t


def rofi_confirm_add() -> str:
    return t("rofi.confirm_add")


def rofi_confirm_remove() -> str:
    return t("rofi.confirm_remove")


def rofi_cancel() -> str:
    return t("rofi.cancel")


def rofi_rebuild_now() -> str:
    return t("rofi.rebuild_now")


def rofi_rebuild_later() -> str:
    return t("rofi.rebuild_later")


def rofi_fix_git() -> str:
    return t("rofi.fix_git")


def rofi_sync_now() -> str:
    return t("rofi.sync_now")


ISSUES_URL = "https://github.com/star67ranger-droid/nixpick/issues"


def is_affirmative(answer: str) -> bool:
    """Un seul prédicat de confirmation partout (o/oui/y/yes)."""
    return answer.strip().lower() in ("o", "oui", "y", "yes")


def cli_cancelled() -> str:
    return t("cli.cancelled")


def apply_hint() -> str:
    """Consigne d'application selon la plateforme (source unique)."""
    return "nixpick sync" if not is_nixos() else "nixpick rebuild"


def cli_success_lines(backup_path: Path) -> list[str]:
    lines = [t("cli.saved", path=backup_path), ""]
    if is_nixos():
        lines += [
            t("cli.apply_rebuild"),
            f"  ({format_rebuild_command()})",
        ]
    else:
        lines += [
            t("cli.apply_sync"),
            t("cli.apply_sync_detail"),
        ]
    return lines


def diff_preview_text(context_lines: list[str], packages_file: Path) -> str:
    header = str(packages_file)
    sep = "─" * min(48, max(len(header), 16))
    body = "\n".join(context_lines)
    return f"{header}\n{sep}\n{body}"


def rofi_confirm_choices(*, remove: bool) -> list[str]:
    if remove:
        return [rofi_confirm_remove(), rofi_cancel()]
    return [rofi_confirm_add(), rofi_cancel()]


def notify_search_too_short() -> tuple[str, str]:
    return (
        "nixpick",
        t("rofi.search_too_short"),
    )


def notify_index_error(detail: str) -> tuple[str, str]:
    return (
        t("rofi.index_title"),
        t("rofi.index_error", detail=detail),
    )


def notify_not_found(term: str) -> tuple[str, str]:
    return (
        "nixpick",
        t("rofi.not_found", term=term),
    )


def notify_remove_failure(plan: RemoveFailure) -> tuple[str, str]:
    return ("nixpick", plan.message)


def notify_add_failure(plan: AddFailure) -> tuple[str, str]:
    return ("nixpick", plan.message)


def notify_permission_denied(packages_file: Path) -> tuple[str, str]:
    return (
        "nixpick",
        t("rofi.permission_denied", path=packages_file),
    )


def notify_dry_run_remove(attr: str) -> tuple[str, str]:
    return (
        t("rofi.dry_run_title"),
        t("rofi.dry_run_remove", attr=attr),
    )


def notify_dry_run_add(attr: str) -> tuple[str, str]:
    return (
        t("rofi.dry_run_title"),
        t("rofi.dry_run_add", attr=attr),
    )


def rofi_rebuild_choices(*, git_ok: bool = True) -> list[str]:
    if not git_ok:
        return [rofi_fix_git(), rofi_rebuild_now(), rofi_rebuild_later()]
    return [rofi_rebuild_now(), rofi_rebuild_later()]


def _success_body(backup_path: Path) -> str:
    if is_nixos():
        how = t("cli.success_rebuild", cmd=format_rebuild_command())
    else:
        how = t("cli.success_sync")
    return t("cli.saved_body", path=backup_path, how=how)


def notify_success_remove(attr: str, backup_path: Path) -> tuple[str, str]:
    return (t("rofi.removed_title", attr=attr), _success_body(backup_path))


def notify_success_add(attr: str, backup_path: Path) -> tuple[str, str]:
    return (t("rofi.added_title", attr=attr), _success_body(backup_path))
