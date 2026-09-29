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
from typing import TextIO

import engine
from config import is_nixos
from engine import (
    ATTR_NAME_RE,
    find_package_line_index,
    index_age_days,
    list_installed_attrs,
    packages_anchor,
    packages_file,
    packages_lock_path,
    rebuild_command,
)
from flake_git import check_flake_untracked
from flake_lock import check_nixpick_flake_lock
from i18n import t


@dataclass(frozen=True)
class Check:
    label: str
    ok: bool
    detail: str


def _check_packages_file() -> Check:
    path = packages_file()
    if not path.exists():
        if not is_nixos():
            return Check(
                t("doc.label_packages"),
                True,
                t("doc.pkg_will_create", path=path),
            )
        parent = path.parent
        if parent.exists() and os.access(parent, os.W_OK):
            return Check(
                t("doc.label_packages"),
                False,
                t("doc.pkg_writable_parent", path=path),
            )
        return Check(
            t("doc.label_packages"),
            False,
            t("doc.pkg_unwritable", path=path),
        )
    if not os.access(path, os.R_OK):
        return Check(t("doc.label_packages"), False, f"{path} illisible.")
    if not os.access(path, os.W_OK):
        return Check(
            t("doc.label_packages"),
            False,
            t("doc.pkg_readonly", path=path),
        )
    return Check(t("doc.label_packages"), True, t("doc.pkg_ok", path=path))


def _check_index() -> Check:
    index_file = engine.INDEX_FILE
    if not index_file.exists():
        return Check(
            t("doc.label_index"),
            False,
            t("doc.index_missing", parent=index_file.parent),
        )
    age = index_age_days()
    age_str = f"{age:.1f}" if age is not None else "?"
    detail = t("doc.index_present", name=index_file.name, age=age_str)
    if age is not None and age > engine.INDEX_MAX_AGE_DAYS:
        detail += t("doc.index_stale", days=engine.INDEX_MAX_AGE_DAYS)
    return Check(t("doc.label_index"), True, detail)


def _check_lock() -> Check:
    lock = packages_lock_path()
    if not lock.exists():
        return Check(t("doc.label_lock"), True, t("doc.lock_none"))
    try:
        with open(lock, "a+", encoding="utf-8") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                return Check(
                    t("doc.label_lock"),
                    True,
                    t("doc.lock_idle", name=lock.name),
                )
            except BlockingIOError:
                return Check(
                    t("doc.label_lock"),
                    False,
                    t("doc.lock_active", name=lock.name),
                )
    except OSError as err:
        return Check(t("doc.label_lock"), False, t("doc.lock_untestable", err=err))


def _check_nix_env() -> Check:
    if shutil.which("nix-env"):
        return Check(t("doc.label_nixenv"), True, t("doc.nixenv_ok"))
    if shutil.which("nix"):
        return Check(
            "nix-env",
            False,
            t("doc.nixenv_noenv"),
        )
    return Check(
        "nix-env",
        False,
        t("doc.nixenv_nonix"),
    )


def _check_rofi() -> Check:
    if shutil.which("rofi"):
        return Check(t("doc.label_rofi"), True, t("doc.rofi_ok"))
    return Check(
        t("doc.label_rofi"),
        True,
        t("doc.rofi_missing"),
    )


def _check_rebuild() -> Check:
    from config import format_rebuild_command

    argv = rebuild_command()
    cmd = format_rebuild_command()
    if not argv:
        return Check(
            t("doc.label_rebuild"),
            False,
            t("doc.rebuild_empty"),
        )
    detail = t("doc.rebuild_ok", cmd=cmd)
    if not is_nixos():
        detail += t("doc.rebuild_no_nixos")
    return Check(
        t("doc.label_rebuild"),
        True,
        detail,
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
    lines = [t("doc.title"), ""]
    for check in checks:
        mark = "OK" if check.ok else "!!"
        lines.append(f"  [{mark}] {check.label} — {check.detail}")
    lines.append("")
    failed = [c for c in checks if not c.ok]
    if failed:
        lines.append(t("doc.report_failures", n=len(failed)))
    else:
        lines.append(t("doc.report_ok"))
    return "\n".join(lines)


def run_doctor(*, as_json: bool = False, out: TextIO | None = None) -> int:
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
            check=False,  # le returncode est inspecté juste après
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.strip()


def run_why(attr: str, *, out: TextIO | None = None) -> int:
    stream = out or sys.stdout
    attr = attr.strip()
    if not attr or not ATTR_NAME_RE.match(attr):
        print(t("doc.why_invalid", attr=attr), file=sys.stderr)
        return 2

    path = packages_file()
    if not path.exists():
        print(t("doc.why_missing", path=path), file=sys.stderr)
        return 1

    lines = path.read_text(encoding="utf-8").splitlines()
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
