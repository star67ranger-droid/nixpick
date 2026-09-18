"""Moteur nixpick : index, recherche, écriture dans packages.nix."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

PACKAGES_FILE = Path("/etc/nixos/modules/packages.nix")
ANCHOR = "environment.systemPackages"

CACHE_DIR = Path.home() / ".cache" / "nixpick"
INDEX_FILE = CACHE_DIR / "index.json"
INDEX_MAX_AGE_DAYS = 7

DEFAULT_RESULT_LIMIT = 12
TUI_RESULT_LIMIT = 80

StatusCallback = Callable[[str], None]


class NixCommandError(RuntimeError):
    """Échec d'une commande nix/nix-env."""


def run(cmd: list[str], timeout: int) -> str:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=True
        ).stdout
    except FileNotFoundError:
        raise NixCommandError(f"{cmd[0]} est introuvable. Ce script attend NixOS.")
    except subprocess.TimeoutExpired:
        raise NixCommandError(f"{cmd[0]} a dépassé {timeout} s.")
    except subprocess.CalledProcessError as err:
        raise NixCommandError((err.stderr or err.stdout or "").strip()[:400])


def index_age_days() -> float | None:
    if not INDEX_FILE.exists():
        return None
    return (time.time() - INDEX_FILE.stat().st_mtime) / 86400


def build_index(on_status: StatusCallback | None = None) -> dict:
    if on_status:
        on_status("Construction de l'index nixpkgs (~20 s)…")
    raw = run(["nix-env", "-qaP", "--json"], timeout=600)
    data = json.loads(raw)
    slim = {
        key: {"pname": pkg.get("pname", ""), "version": pkg.get("version", "")}
        for key, pkg in data.items()
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(slim))
    if on_status:
        on_status(f"{len(slim)} paquets indexés.")
    return slim


def load_index(refresh: bool = False, on_status: StatusCallback | None = None) -> dict:
    age = index_age_days()
    if refresh or age is None:
        return build_index(on_status)
    if age > INDEX_MAX_AGE_DAYS:
        if on_status:
            on_status(f"Index vieux de {age:.0f} jours, reconstruction…")
        return build_index(on_status)
    return json.loads(INDEX_FILE.read_text())


def attr_name(key: str) -> str:
    return key.split(".", 1)[1] if "." in key else key


def search(
    index: dict, term: str, limit: int = DEFAULT_RESULT_LIMIT
) -> list[tuple[str, str]]:
    if not term.strip():
        return []

    needle = term.lower().strip()
    results: list[tuple[int, int, str, str]] = []

    for key, pkg in index.items():
        attr = attr_name(key)
        low = attr.lower()
        pname = (pkg.get("pname") or "").lower()

        if low == needle or pname == needle:
            score = 100
        elif low.startswith(needle) or pname.startswith(needle):
            score = 70
        elif needle in low or needle in pname:
            score = 40
        else:
            continue

        results.append((-score, len(attr), attr, pkg.get("version", "")))

    results.sort()
    return [(attr, version) for _, _, attr, version in results[:limit]]


def fetch_descriptions(attrs: list[str]) -> dict[str, str]:
    if not attrs:
        return {}

    names = " ".join(json.dumps(a) for a in attrs)
    expr = f"""
      let
        pkgs = import <nixpkgs> {{ config.allowUnfree = true; }};
        lib = pkgs.lib;
        describe = name:
          let attempt = builtins.tryEval
            (lib.attrByPath (lib.splitString "." name) null pkgs);
          in if attempt.success && attempt.value != null
             then (attempt.value.meta.description or "")
             else "";
      in builtins.listToAttrs
           (map (n: {{ name = n; value = describe n; }}) [ {names} ])
    """
    try:
        raw = subprocess.run(
            ["nix", "eval", "--json", "--impure", "--expr", expr],
            capture_output=True,
            text=True,
            timeout=90,
            check=True,
        ).stdout
        return json.loads(raw)
    except Exception:
        return {}


def list_installed_attrs() -> set[str]:
    """Paquets déjà listés dans environment.systemPackages."""
    if not PACKAGES_FILE.exists():
        return set()
    lines = PACKAGES_FILE.read_text().splitlines()
    found: set[str] = set()
    in_block = False
    for line in lines:
        if ANCHOR in line:
            in_block = True
            continue
        if in_block:
            if line.strip() == "];":
                break
            m = re.match(r"^\s*([a-zA-Z0-9_.-]+)\s*(#.*)?$", line)
            if m:
                found.add(m.group(1))
    return found


def already_listed(lines: list[str], attr: str) -> bool:
    pattern = re.compile(rf"^\s*{re.escape(attr)}\s*(#.*)?$")
    return any(pattern.match(line) for line in lines)


def _short_description(description: str, max_len: int = 55) -> str:
    short = description[:max_len].rstrip()
    if len(description) > max_len:
        short += "…"
    return short


@dataclass
class AddPlan:
    attr: str
    description: str
    new_line: str
    context_lines: list[str]
    packages_file: Path
    backup_path: Path


class AddOutcome(Enum):
    ALREADY_LISTED = "already_listed"
    FILE_MISSING = "file_missing"
    BLOCK_MISSING = "block_missing"


@dataclass
class AddFailure:
    outcome: AddOutcome
    message: str


def plan_add(attr: str, description: str) -> AddPlan | AddFailure:
    if not PACKAGES_FILE.exists():
        return AddFailure(AddOutcome.FILE_MISSING, f"{PACKAGES_FILE} introuvable.")

    lines = PACKAGES_FILE.read_text().splitlines(keepends=True)

    if already_listed(lines, attr):
        return AddFailure(
            AddOutcome.ALREADY_LISTED,
            f"{attr} est déjà dans environment.systemPackages.",
        )

    try:
        insert_at, indent = _find_insertion_point(lines)
    except LookupError as err:
        return AddFailure(AddOutcome.BLOCK_MISSING, str(err))

    comment = f"  # {_short_description(description)}" if description else ""
    new_line = f"{indent}{attr}{comment}\n"

    context = [lines[i].rstrip("\n") for i in range(max(0, insert_at - 2), insert_at)]
    context.append(f"+ {new_line.rstrip()}")

    return AddPlan(
        attr=attr,
        description=description,
        new_line=new_line,
        context_lines=context,
        packages_file=PACKAGES_FILE,
        backup_path=PACKAGES_FILE.with_suffix(".nix.bak"),
    )


def commit_add(plan: AddPlan, dry_run: bool = False) -> None:
    if dry_run:
        return

    lines = PACKAGES_FILE.read_text().splitlines(keepends=True)
    insert_at, _ = _find_insertion_point(lines)
    shutil.copy2(PACKAGES_FILE, plan.backup_path)
    lines.insert(insert_at, plan.new_line)
    PACKAGES_FILE.write_text("".join(lines))


def _find_insertion_point(lines: list[str]) -> tuple[int, str]:
    start = next((i for i, l in enumerate(lines) if ANCHOR in l), None)
    if start is None:
        raise LookupError(f"« {ANCHOR} » introuvable dans {PACKAGES_FILE}")

    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip() == "];"),
        None,
    )
    if end is None:
        raise LookupError(f"Fin du bloc « {ANCHOR} » introuvable.")

    indent = "  "
    for line in lines[start + 1 : end]:
        if line.strip() and not line.strip().startswith("#"):
            indent = line[: len(line) - len(line.lstrip())]
            break

    insert_at = end
    while insert_at - 1 > start and not lines[insert_at - 1].strip():
        insert_at -= 1
    return insert_at, indent


REBUILD_CMD = "sudo nixos-rebuild switch --flake /etc/nixos#nixos"
