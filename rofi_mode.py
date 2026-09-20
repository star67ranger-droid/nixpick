"""Mode Rofi : recherche + confirmation glass, sans TUI."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from config import rofi_theme_paths
from engine import (
    DEFAULT_RESULT_LIMIT,
    AddFailure,
    NixCommandError,
    RemoveFailure,
    commit_add,
    commit_remove,
    fetch_descriptions,
    list_installed_attrs,
    load_index,
    plan_add,
    plan_remove,
    search,
)
from messages import (
    ROFI_CONFIRM_ADD,
    ROFI_CONFIRM_REMOVE,
    diff_preview_text,
    notify_add_failure,
    notify_dry_run_add,
    notify_dry_run_remove,
    notify_index_error,
    notify_not_found,
    notify_permission_denied,
    notify_remove_failure,
    notify_search_too_short,
    notify_success_add,
    notify_success_remove,
    rofi_confirm_choices,
)


def _rofi_theme(*, query_only: bool = False) -> str:
    for path in rofi_theme_paths(query_only):
        if path.is_file():
            return str(path)
    return str(Path.home() / ".config/rofi/config.rasi")


def _rofi(
    prompt: str,
    lines: list[str] | None = None,
    *,
    max_lines: int = 12,
    query_only: bool = False,
) -> str | None:
    if not shutil.which("rofi"):
        print("rofi introuvable", file=sys.stderr)
        return None

    cmd = [
        "rofi",
        "-dmenu",
        "-i",
        "-p",
        prompt,
        "-theme",
        _rofi_theme(query_only=query_only),
        "-show",
        "dmenu",
    ]
    if lines is None:
        cmd.extend(["-lines", "0"])
        stdin = ""
    else:
        n = len(lines)
        cmd.extend(
            [
                "-no-custom",
                "-lines",
                str(min(max_lines, max(3, n))),
            ]
        )
        stdin = "\n".join(lines) + "\n"

    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as err:
        print(f"rofi : {err}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def _rofi_preview(message: str) -> None:
    """Affiche l’aperçu diff (read-only) avant confirmation."""
    if not shutil.which("rofi"):
        return
    cmd = [
        "rofi",
        "-e",
        message,
        "-theme",
        _rofi_theme(),
    ]
    try:
        subprocess.run(cmd, check=False, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return


def _notify(title: str, body: str) -> None:
    if not shutil.which("notify-send"):
        return
    try:
        subprocess.run(
            ["notify-send", "-a", "nixpick", "-u", "normal", title, body],
            check=False,
            timeout=5,
        )
    except Exception:
        return


def _confirm_plan(
    attr: str,
    context_lines: list[str],
    packages_file: Path,
    *,
    remove: bool,
) -> bool:
    _rofi_preview(diff_preview_text(context_lines, packages_file))
    verb = "retrait" if remove else "ajout"
    answer = _rofi(
        f"{attr} — confirmer l'{verb} ?",
        rofi_confirm_choices(remove=remove),
        max_lines=2,
    )
    if remove:
        return answer == ROFI_CONFIRM_REMOVE
    return answer == ROFI_CONFIRM_ADD


def run_rofi(refresh: bool = False, dry_run: bool = False) -> int:
    term = _rofi("󰏖 nixpick", query_only=True)
    if not term:
        return 0
    term = term.strip()
    if len(term) < 2:
        t, b = notify_search_too_short()
        _notify(t, b)
        return 1

    try:
        index = load_index(refresh=refresh)
    except NixCommandError as err:
        t, b = notify_index_error(str(err))
        _notify(t, b)
        return 1

    results = search(index, term, limit=DEFAULT_RESULT_LIMIT)
    if not results:
        t, b = notify_not_found(term)
        _notify(t, b)
        return 1

    installed = list_installed_attrs()
    descriptions = fetch_descriptions([a for a, _ in results])

    labels: list[str] = []
    by_label: dict[str, str] = {}
    for attr, version in results:
        mark = " ✓" if attr in installed else ""
        label = f"{attr}  ·  {version}{mark}"
        labels.append(label)
        by_label[label] = attr

    chosen = _rofi(f"Choisir · {term}", labels)
    if not chosen or chosen not in by_label:
        return 0

    attr = by_label[chosen]
    already = attr in installed

    if already:
        plan_rm = plan_remove(attr)
        if isinstance(plan_rm, RemoveFailure):
            t, b = notify_remove_failure(plan_rm)
            _notify(t, b)
            return 0
        if not _confirm_plan(
            attr,
            plan_rm.context_lines,
            plan_rm.packages_file,
            remove=True,
        ):
            return 0
        if dry_run:
            t, b = notify_dry_run_remove(attr)
            _notify(t, b)
            return 0
        try:
            commit_remove(plan_rm, dry_run=False)
        except PermissionError:
            t, b = notify_permission_denied(plan_rm.packages_file)
            _notify(t, b)
            return 1
        t, b = notify_success_remove(attr, plan_rm.backup_path)
        _notify(t, b)
        return 0

    plan = plan_add(attr, descriptions.get(attr, ""))
    if isinstance(plan, AddFailure):
        t, b = notify_add_failure(plan)
        _notify(t, b)
        return 0

    if not _confirm_plan(
        attr,
        plan.context_lines,
        plan.packages_file,
        remove=False,
    ):
        return 0

    if dry_run:
        t, b = notify_dry_run_add(attr)
        _notify(t, b)
        return 0

    try:
        commit_add(plan, dry_run=False)
    except PermissionError:
        t, b = notify_permission_denied(plan.packages_file)
        _notify(t, b)
        return 1

    t, b = notify_success_add(attr, plan.backup_path)
    _notify(t, b)
    return 0
