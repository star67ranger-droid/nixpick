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
    rebuild_command,
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


def run_rofi(refresh: bool = False, dry_run: bool = False) -> int:
    term = _rofi("󰏖 nixpick", query_only=True)
    if not term:
        return 0
    term = term.strip()
    if len(term) < 2:
        _notify("nixpick", "Tape au moins 2 caractères.")
        return 1

    try:
        index = load_index(refresh=refresh)
    except NixCommandError as err:
        _notify("nixpick — index", str(err))
        return 1

    results = search(index, term, limit=DEFAULT_RESULT_LIMIT)
    if not results:
        _notify("nixpick", f"Rien trouvé pour « {term} ».")
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
            _notify("nixpick", plan_rm.message)
            return 0
        preview = "\n".join(plan_rm.context_lines[-4:])
        _notify("nixpick — retrait", preview[:220] or attr)
        answer = _rofi(f"Retirer {attr} ?", ["Oui, retirer", "Non"], max_lines=2)
        if answer != "Oui, retirer":
            return 0
        if dry_run:
            _notify("nixpick (dry-run)", f"{attr} aurait été retiré.")
            return 0
        try:
            commit_remove(plan_rm, dry_run=False)
        except PermissionError:
            _notify("nixpick", f"Pas les droits d'écriture sur {plan_rm.packages_file}")
            return 1
        _notify(f"nixpick · {attr} retiré", f"Pour appliquer :\n{rebuild_command()}")
        return 0

    plan = plan_add(attr, descriptions.get(attr, ""))
    if isinstance(plan, AddFailure):
        _notify("nixpick", plan.message)
        return 0

    preview = "\n".join(plan.context_lines[-4:])
    _notify("nixpick — aperçu", preview[:220] or attr)

    answer = _rofi(f"Ajouter {attr} ?", ["Oui", "Non"], max_lines=2)
    if answer != "Oui":
        return 0

    if dry_run:
        _notify("nixpick (dry-run)", f"{attr} aurait été ajouté.")
        return 0

    try:
        commit_add(plan, dry_run=False)
    except PermissionError:
        _notify("nixpick", f"Pas les droits d'écriture sur {plan.packages_file}")
        return 1

    _notify(f"nixpick · {attr} ajouté", f"Pour appliquer :\n{rebuild_command()}")
    return 0
