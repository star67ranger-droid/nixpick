"""Moteur nixpick : index, recherche, écriture dans packages.nix."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterator

from config import get_settings


def packages_file() -> Path:
    return get_settings().packages_file


def packages_anchor() -> str:
    return get_settings().packages_anchor


def rebuild_command() -> str:
    return get_settings().rebuild_command

CACHE_DIR = Path.home() / ".cache" / "nixpick"
INDEX_FILE = CACHE_DIR / "index.json"
INDEX_META_FILE = CACHE_DIR / "index-meta.json"
INDEX_MAX_AGE_DAYS = 7
INDEX_STALE_NOTIFY_DAYS = 14

DEFAULT_RESULT_LIMIT = 12
TUI_RESULT_LIMIT = 40
ATTR_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")

DESC_CACHE_FILE = CACHE_DIR / "descriptions.json"
LAST_OP_FILE = CACHE_DIR / "last-op.json"

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


def _write_index_meta(built_at: float | None = None) -> None:
    ts = built_at if built_at is not None else time.time()
    built_at_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    INDEX_META_FILE.write_text(json.dumps({"built_at": built_at_iso}))


def index_age_days() -> float | None:
    if INDEX_META_FILE.exists():
        try:
            meta = json.loads(INDEX_META_FILE.read_text())
            raw = meta.get("built_at")
            if isinstance(raw, str) and raw:
                built = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if built.tzinfo is None:
                    built = built.replace(tzinfo=timezone.utc)
                return (time.time() - built.timestamp()) / 86400
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
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
    _write_index_meta()
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
    try:
        return json.loads(INDEX_FILE.read_text())
    except (json.JSONDecodeError, OSError) as err:
        if on_status:
            on_status(f"Index illisible ({err}), reconstruction…")
        return build_index(on_status)


def attr_name(key: str) -> str:
    return key.split(".", 1)[1] if "." in key else key


@dataclass(frozen=True, slots=True)
class PackageRow:
    attr: str
    version: str
    attr_lc: str
    pname_lc: str


@dataclass
class PackageIndex:
    """Liste compacte pour parcourir l'index sans dict ni .lower() à chaque frappe."""

    rows: list[PackageRow]
    by_leading: dict[str, list[PackageRow]]

    def __len__(self) -> int:
        return len(self.rows)

    @classmethod
    def from_dict(cls, index: dict) -> PackageIndex:
        rows: list[PackageRow] = []
        by_leading: dict[str, list[PackageRow]] = {}
        for key, pkg in index.items():
            attr = attr_name(key)
            row = PackageRow(
                attr=attr,
                version=pkg.get("version", ""),
                attr_lc=attr.lower(),
                pname_lc=(pkg.get("pname") or "").lower(),
            )
            rows.append(row)
            for ch in {row.attr_lc[:1], row.pname_lc[:1]} - {""}:
                by_leading.setdefault(ch, []).append(row)
        return cls(rows=rows, by_leading=by_leading)

    def candidates_for(self, needle: str) -> tuple[list[PackageRow], set[str]]:
        """Réduit le scan pour les requêtes ≥ 2 caractères (première lettre attr/pname)."""
        ch = needle[0]
        pool = self.by_leading.get(ch, [])
        seen: set[str] = set()
        out: list[PackageRow] = []
        for row in pool:
            if row.attr in seen:
                continue
            seen.add(row.attr)
            out.append(row)
        return out, seen


def search(
    index: dict | PackageIndex,
    term: str,
    limit: int = DEFAULT_RESULT_LIMIT,
) -> list[tuple[str, str]]:
    if not term.strip():
        return []

    pkg_index = index if isinstance(index, PackageIndex) else PackageIndex.from_dict(index)
    return search_index(pkg_index, term, limit)


def search_index(
    index: PackageIndex, term: str, limit: int = DEFAULT_RESULT_LIMIT
) -> list[tuple[str, str]]:
    if not term.strip():
        return []

    needle = term.lower().strip()
    # Une lettre = des milliers de correspondances : on évite le scan complet.
    if len(needle) < 2:
        return []

    results: list[tuple[int, int, str, str]] = []

    def score_row(row: PackageRow) -> int | None:
        if row.attr_lc == needle or row.pname_lc == needle:
            return 100
        if row.attr_lc.startswith(needle) or row.pname_lc.startswith(needle):
            return 70
        if needle in row.attr_lc or needle in row.pname_lc:
            return 40
        return None

    primary, seen = index.candidates_for(needle)
    for row in primary:
        score = score_row(row)
        if score is not None:
            results.append((-score, len(row.attr), row.attr, row.version))

    if len(results) < limit:
        for row in index.rows:
            if row.attr in seen:
                continue
            score = score_row(row)
            if score is not None:
                results.append((-score, len(row.attr), row.attr, row.version))

    results.sort()
    return [(attr, version) for _, _, attr, version in results[:limit]]


class DescriptionCache:
    """Évite de relancer nix eval pour les mêmes attributs."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        if DESC_CACHE_FILE.exists():
            try:
                self._data = json.loads(DESC_CACHE_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, attr: str) -> str | None:
        text = self._data.get(attr)
        return text if text else None

    def remember(self, attr: str, description: str) -> None:
        if not description or self._data.get(attr) == description:
            return
        self._data[attr] = description
        self._persist()

    def _persist(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            DESC_CACHE_FILE.write_text(json.dumps(self._data))
        except OSError:
            pass

    def fetch_one(self, attr: str) -> str:
        cached = self.get(attr)
        if cached is not None:
            return cached
        desc = fetch_descriptions([attr]).get(attr, "")
        if desc:
            self.remember(attr, desc)
        return desc

    def remember_many(self, data: dict[str, str]) -> None:
        changed = False
        for attr, description in data.items():
            if not description or self._data.get(attr) == description:
                continue
            self._data[attr] = description
            changed = True
        if changed:
            self._persist()

    def fetch_many(self, attrs: list[str]) -> dict[str, str]:
        missing = [a for a in attrs if self.get(a) is None]
        if not missing:
            return {a: self.get(a) or "" for a in attrs}
        fetched = fetch_descriptions(missing)
        self.remember_many(fetched)
        return {a: self.get(a) or fetched.get(a, "") or "" for a in attrs}


def fetch_descriptions(attrs: list[str]) -> dict[str, str]:
    if not attrs:
        return {}

    safe: list[str] = []
    for a in attrs:
        if _validate_attr_name(a) is None:
            safe.append(a)
    if not safe:
        return {}

    names = " ".join(json.dumps(a) for a in safe)
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
    path = packages_file()
    if not path.exists():
        return set()
    lines = path.read_text().splitlines()
    anchor_re = re.compile(rf"^\s*{re.escape(packages_anchor())}\b")
    found: set[str] = set()
    in_block = False
    for line in lines:
        if anchor_re.match(line):
            in_block = True
            continue
        if in_block:
            if line.strip() == "];":
                break
            m = re.match(r"^\s*([a-zA-Z0-9_.-]+)\s*(#.*)?$", line)
            if m:
                found.add(m.group(1))
    return found


def _attr_line_pattern(attr: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*{re.escape(attr)}\s*(#.*)?$")


def already_listed(lines: list[str], attr: str) -> bool:
    pattern = _attr_line_pattern(attr)
    return any(pattern.match(line) for line in lines)


def _read_packages_lines() -> list[str] | AddFailure:
    path = packages_file()
    if not path.exists():
        return AddFailure(AddOutcome.FILE_MISSING, f"{path} introuvable.")
    return path.read_text().splitlines(keepends=True)


def find_package_line_index(lines: list[str], attr: str) -> int | None:
    """Index de la ligne du paquet dans environment.systemPackages."""
    pattern = _attr_line_pattern(attr)
    anchor_re = re.compile(rf"^\s*{re.escape(packages_anchor())}\b")
    in_block = False
    for i, line in enumerate(lines):
        if anchor_re.match(line):
            in_block = True
            continue
        if in_block:
            if line.strip() == "];":
                break
            if pattern.match(line):
                return i
    return None


def _sanitize_description(description: str) -> str:
    """Une ligne sûre pour un commentaire Nix (# …)."""
    one_line = " ".join(description.split())
    return one_line.replace("#", " ").strip()


def _short_description(description: str, max_len: int = 55) -> str:
    clean = _sanitize_description(description)
    short = clean[:max_len].rstrip()
    if len(clean) > max_len:
        short += "…"
    return short


def _validate_attr_name(attr: str) -> str | None:
    if not attr or not ATTR_NAME_RE.fullmatch(attr):
        return f"Nom d'attribut invalide : {attr!r}"
    return None


def _backup_path() -> Path:
    from datetime import datetime

    base = packages_file()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return base.with_name(f"{base.name}.bak.{ts}")


@contextmanager
def _packages_edit_lock() -> Iterator[None]:
    path = packages_file()
    lock_path = path.parent / f".{path.name}.nixpick.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def _record_last_op(op: str, attr: str, backup_path: Path, pkg_file: Path) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.time(),
        "op": op,
        "attr": attr,
        "backup_path": str(backup_path),
        "packages_file": str(pkg_file),
    }
    _atomic_write_text(LAST_OP_FILE, json.dumps(payload, indent=2) + "\n")


def _load_last_op() -> dict | None:
    if not LAST_OP_FILE.exists():
        return None
    try:
        data = json.loads(LAST_OP_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _backup_matches_target(backup_path: Path, target: Path) -> bool:
    prefix = f"{target.name}.bak."
    return backup_path.name.startswith(prefix) and backup_path.parent == target.parent


@dataclass(frozen=True, slots=True)
class UndoResult:
    code: int
    stdout: str = ""
    stderr: str = ""


def undo_last_write() -> UndoResult:
    """Restaure packages_file depuis la dernière sauvegarde (sans rebuild)."""
    record = _load_last_op()
    if not record:
        return UndoResult(1, stderr="Aucune dernière opération enregistrée.")

    op = record.get("op")
    attr = record.get("attr", "")
    if op not in ("add", "remove"):
        return UndoResult(1, stderr="Dernière opération invalide ou illisible.")

    target = packages_file()
    recorded_target = record.get("packages_file")
    if not recorded_target:
        return UndoResult(1, stderr="Dernière opération invalide ou illisible.")
    try:
        if Path(recorded_target).resolve() != target.resolve():
            return UndoResult(
                1,
                stderr=(
                    f"La dernière opération concerne un autre fichier "
                    f"({recorded_target}), pas {target}."
                ),
            )
    except OSError:
        return UndoResult(1, stderr="Chemin de la dernière opération invalide.")

    backup_raw = record.get("backup_path")
    if not backup_raw:
        return UndoResult(1, stderr="Dernière opération sans sauvegarde associée.")
    backup_path = Path(backup_raw)
    if not backup_path.is_file():
        return UndoResult(1, stderr=f"Sauvegarde introuvable : {backup_path}")
    if not _backup_matches_target(backup_path, target):
        return UndoResult(
            1,
            stderr=f"La sauvegarde ne correspond pas au fichier cible {target}.",
        )

    try:
        with _packages_edit_lock():
            _atomic_write_text(target, backup_path.read_text(encoding="utf-8"))
    except PermissionError:
        return UndoResult(
            1, stderr=f"Pas les droits d'écriture sur {target}."
        )
    except OSError as err:
        return UndoResult(1, stderr=f"Restauration impossible : {err}")

    try:
        LAST_OP_FILE.unlink(missing_ok=True)
    except OSError:
        pass

    verb = "ajout" if op == "add" else "retrait"
    return UndoResult(
        0,
        stdout=(
            f"Fichier restauré : {target} "
            f"(annulation du {verb} de {attr})."
        ),
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


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
    invalid = _validate_attr_name(attr)
    if invalid:
        return AddFailure(AddOutcome.BLOCK_MISSING, invalid)

    lines_or_err = _read_packages_lines()
    if isinstance(lines_or_err, AddFailure):
        return lines_or_err
    lines = lines_or_err

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
        packages_file=packages_file(),
        backup_path=_backup_path(),
    )


def commit_add(plan: AddPlan, dry_run: bool = False) -> None:
    if dry_run:
        return

    with _packages_edit_lock():
        path = packages_file()
        lines = path.read_text().splitlines(keepends=True)
        if already_listed(lines, plan.attr):
            raise LookupError(f"{plan.attr} est déjà listé.")
        insert_at, _ = _find_insertion_point(lines)
        shutil.copy2(path, plan.backup_path)
        lines.insert(insert_at, plan.new_line)
        _atomic_write_text(path, "".join(lines))
        _record_last_op("add", plan.attr, plan.backup_path, path)


def _find_insertion_point(lines: list[str]) -> tuple[int, str]:
    anchor = packages_anchor()
    path = packages_file()
    anchor_re = re.compile(rf"^\s*{re.escape(anchor)}\b")
    start = next((i for i, l in enumerate(lines) if anchor_re.match(l)), None)
    if start is None:
        raise LookupError(f"« {anchor} » introuvable dans {path}")

    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip() == "];"),
        None,
    )
    if end is None:
        raise LookupError(f"Fin du bloc « {anchor} » introuvable.")

    indent = "  "
    for line in lines[start + 1 : end]:
        if line.strip() and not line.strip().startswith("#"):
            indent = line[: len(line) - len(line.lstrip())]
            break

    insert_at = end
    while insert_at - 1 > start and not lines[insert_at - 1].strip():
        insert_at -= 1
    return insert_at, indent


class RemoveOutcome(Enum):
    NOT_LISTED = "not_listed"
    FILE_MISSING = "file_missing"
    BLOCK_MISSING = "block_missing"
    INVALID_ATTR = "invalid_attr"


@dataclass
class RemoveFailure:
    outcome: RemoveOutcome
    message: str


@dataclass
class RemovePlan:
    attr: str
    removed_line: str
    context_lines: list[str]
    packages_file: Path
    backup_path: Path


def plan_remove(attr: str) -> RemovePlan | RemoveFailure:
    invalid = _validate_attr_name(attr)
    if invalid:
        return RemoveFailure(RemoveOutcome.INVALID_ATTR, invalid)

    lines_or_err = _read_packages_lines()
    if isinstance(lines_or_err, AddFailure):
        return RemoveFailure(
            RemoveOutcome.FILE_MISSING,
            lines_or_err.message,
        )

    lines = lines_or_err
    line_idx = find_package_line_index(lines, attr)
    if line_idx is None:
        return RemoveFailure(
            RemoveOutcome.NOT_LISTED,
            f"{attr} n'est pas dans environment.systemPackages.",
        )

    raw = lines[line_idx].rstrip("\n")
    removed = raw.strip()
    context: list[str] = []
    for i in range(max(0, line_idx - 2), line_idx):
        context.append(lines[i].rstrip("\n"))
    context.append(f"- {removed}")

    return RemovePlan(
        attr=attr,
        removed_line=lines[line_idx],
        context_lines=context,
        packages_file=packages_file(),
        backup_path=_backup_path(),
    )


def commit_remove(plan: RemovePlan, dry_run: bool = False) -> None:
    if dry_run:
        return

    with _packages_edit_lock():
        path = packages_file()
        lines = path.read_text().splitlines(keepends=True)
        line_idx = find_package_line_index(lines, plan.attr)
        if line_idx is None:
            raise LookupError(f"Ligne introuvable pour {plan.attr}")

        shutil.copy2(path, plan.backup_path)
        del lines[line_idx]
        _atomic_write_text(path, "".join(lines))
        _record_last_op("remove", plan.attr, plan.backup_path, path)
