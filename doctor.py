"""Diagnostics (`nixpick doctor`) et traçabilité (`nixpick --why`)."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import engine
from engine import (
    ATTR_NAME_RE,
    find_package_line_index,
    index_age_days,
    list_installed_attrs,
    packages_anchor,
    packages_file,
    rebuild_command,
)
from flake_git import check_flake_untracked
from flake_lock import check_nixpick_flake_lock


@dataclass(frozen=True)
class Check:
    label: str
    ok: bool
    detail: str


def packages_lock_path() -> Path:
    path = packages_file()
    return path.parent / f".{path.name}.nixpick.lock"


def _check_packages_file() -> Check:
    path = packages_file()
    if not path.exists():
        parent = path.parent
        if parent.exists() and os.access(parent, os.W_OK):
            return Check(
                "Fichier packages",
                False,
                f"{path} n'existe pas encore (le dossier parent est inscriptible).",
            )
        return Check(
            "Fichier packages",
            False,
            f"{path} introuvable et le dossier parent n'est pas inscriptible.",
        )
    if not os.access(path, os.R_OK):
        return Check("Fichier packages", False, f"{path} illisible.")
    if not os.access(path, os.W_OK):
        return Check(
            "Fichier packages",
            False,
            f"{path} existe mais n'est pas modifiable.",
        )
    return Check("Fichier packages", True, f"{path} présent et modifiable.")


def _check_index() -> Check:
    index_file = engine.INDEX_FILE
    if not index_file.exists():
        return Check(
            "Cache index",
            False,
            f"Pas d'index dans {index_file.parent} "
            "(lance nixpick --build-index-only ou ouvre la TUI).",
        )
    age = index_age_days()
    age_str = f"{age:.1f}" if age is not None else "?"
    detail = f"Index présent ({index_file.name}), âge {age_str} j."
    if age is not None and age > engine.INDEX_MAX_AGE_DAYS:
        detail += (
            f" Plus de {engine.INDEX_MAX_AGE_DAYS} j — "
            "un refresh est conseillé (nixpick --refresh)."
        )
    return Check("Cache index", True, detail)


def _check_lock() -> Check:
    lock = packages_lock_path()
    if not lock.exists():
        return Check("Verrou d'édition", True, "Aucun fichier verrou (.nixpick.lock).")
    try:
        with open(lock, "a+", encoding="utf-8") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                return Check(
                    "Verrou d'édition",
                    True,
                    f"{lock.name} présent mais inactif (pas d'édition en cours).",
                )
            except BlockingIOError:
                return Check(
                    "Verrou d'édition",
                    False,
                    f"Verrou actif sur {lock.name} — "
                    "une session nixpick modifie peut-être le fichier.",
                )
    except OSError as err:
        return Check("Verrou d'édition", False, f"Impossible de tester le verrou : {err}")


def _check_nix_env() -> Check:
    if shutil.which("nix-env"):
        return Check("nix-env", True, "nix-env trouvé dans le PATH.")
    return Check(
        "nix-env",
        False,
        "nix-env absent du PATH — requis pour construire l'index.",
    )


def _check_rofi() -> Check:
    if shutil.which("rofi"):
        return Check("rofi (optionnel)", True, "rofi trouvé (pour nixpick --rofi).")
    return Check(
        "rofi (optionnel)",
        True,
        "rofi absent — seulement utile avec nixpick --rofi.",
    )


def _check_rebuild() -> Check:
    cmd = rebuild_command().strip()
    if not cmd:
        return Check(
            "Commande rebuild",
            False,
            "rebuild_command vide — configure config.toml ou NIXPICK_REBUILD_COMMAND.",
        )
    return Check(
        "Commande rebuild",
        True,
        f"Après ajout ou retrait : {cmd}",
    )


def _check_flake_lock() -> Check:
    ok, detail = check_nixpick_flake_lock()
    return Check("flake.lock (input nixpick)", ok, detail.replace("\n", "\n      "))


def _check_flake_git() -> Check:
    ok, detail = check_flake_untracked()
    return Check("Git flake (fichiers suivis)", ok, detail.replace("\n", "\n      "))


def collect_checks() -> list[Check]:
    return [
        _check_packages_file(),
        _check_index(),
        _check_lock(),
        _check_nix_env(),
        _check_rofi(),
        _check_flake_git(),
        _check_flake_lock(),
        _check_rebuild(),
    ]


def format_doctor_report(checks: list[Check]) -> str:
    lines = ["Diagnostic nixpick", ""]
    for check in checks:
        mark = "OK" if check.ok else "!!"
        lines.append(f"  [{mark}] {check.label} — {check.detail}")
    lines.append("")
    failed = [c for c in checks if not c.ok]
    if failed:
        lines.append(f"{len(failed)} point(s) à corriger.")
    else:
        lines.append("Tout semble en ordre.")
    return "\n".join(lines)


def run_doctor(*, as_json: bool = False, out: object | None = None) -> int:
    stream = out or sys.stdout
    checks = collect_checks()
    if as_json:
        payload = {
            "ok": all(c.ok for c in checks),
            "checks": [
                {"label": c.label, "ok": c.ok, "detail": c.detail} for c in checks
            ],
        }
        print(json.dumps(payload, ensure_ascii=False), file=stream)
    else:
        print(format_doctor_report(checks), file=stream)
    return 1 if any(not c.ok for c in checks) else 0


def _find_git_root(start: Path) -> Path | None:
    path = start.resolve()
    if path.is_file():
        path = path.parent
    for candidate in (path, *path.parents):
        if (candidate / ".git").is_dir():
            return candidate
    return None


def _git_log_line(packages_path: Path, line_no: int) -> str | None:
    root = _find_git_root(packages_path)
    if root is None:
        return None
    try:
        rel = packages_path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    spec = f"{line_no},{line_no}:{rel}"
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "-L", spec],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.strip()


def run_why(attr: str, *, out: object | None = None) -> int:
    stream = out or sys.stdout
    attr = attr.strip()
    if not attr or not ATTR_NAME_RE.match(attr):
        print(f"Attribut invalide : {attr!r}", file=sys.stderr)
        return 2

    path = packages_file()
    if not path.exists():
        print(f"Fichier configuré introuvable : {path}", file=sys.stderr)
        return 1

    lines = path.read_text().splitlines()
    anchor = packages_anchor()
    line_idx = find_package_line_index(lines, attr)

    print(f"Fichier : {path}", file=stream)
    print(f"Attribut : {attr}", file=stream)

    if line_idx is not None:
        line_no = line_idx + 1
        print(f"Dans {anchor} : oui, ligne {line_no}", file=stream)
        print(f"  {lines[line_idx].rstrip()}", file=stream)
        history = _git_log_line(path, line_no)
        if history:
            print(file=stream)
            print(history, file=stream)
        return 0

    if attr in list_installed_attrs():
        print(f"Dans {anchor} : oui (détecté, ligne non résolue).", file=stream)
        return 0

    approx = [(i, line) for i, line in enumerate(lines) if attr in line]
    print(f"L'attribut {attr} n'apparaît pas dans {anchor}.", file=stream)
    if approx:
        print("Occurrences approximatives dans le fichier :", file=stream)
        for i, line in approx[:10]:
            print(f"  L{i + 1}: {line.rstrip()}", file=stream)
    else:
        print("Aucune occurrence de cet attribut dans le fichier.", file=stream)
    return 0


def explain_why(attr: str) -> int:
    """Alias CLI pour ``run_why`` (sortie sur stdout/stderr)."""
    return run_why(attr)
