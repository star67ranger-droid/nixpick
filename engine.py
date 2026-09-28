"""Moteur nixpick : index, recherche, écriture dans packages.nix."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path

from config import get_settings


def packages_file() -> Path:
    return get_settings().packages_file


def packages_anchor() -> str:
    return get_settings().packages_anchor


def rebuild_command() -> tuple[str, ...]:
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
    except OSError as err:
        raise NixCommandError(f"{cmd[0]} : {err}") from err


def _atomic_write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _write_index_meta(built_at: float | None = None) -> None:
    ts = built_at if built_at is not None else time.time()
    built_at_iso = datetime.fromtimestamp(ts, tz=UTC).isoformat()
    _atomic_write_json(INDEX_META_FILE, {"built_at": built_at_iso})


def index_age_days() -> float | None:
    if INDEX_META_FILE.exists():
        try:
            meta = json.loads(INDEX_META_FILE.read_text(encoding="utf-8"))
            raw = meta.get("built_at")
            if isinstance(raw, str) and raw:
                built = datetime.fromisoformat(raw)
                if built.tzinfo is None:
                    built = built.replace(tzinfo=UTC)
                return (time.time() - built.timestamp()) / 86400
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    if not INDEX_FILE.exists():
        return None
    return (time.time() - INDEX_FILE.stat().st_mtime) / 86400


@contextmanager
def _index_build_lock() -> Iterator[None]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = CACHE_DIR / "index.build.lock"
    with open(lock_path, "w", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def build_index(on_status: StatusCallback | None = None) -> dict:
    with _index_build_lock():
        if on_status:
            on_status("Construction de l'index nixpkgs (~20 s)…")
        raw = run(["nix-env", "-qaP", "--json"], timeout=600)
        data = json.loads(raw)
        slim = {
            key: {"pname": pkg.get("pname", ""), "version": pkg.get("version", "")}
        for key, pkg in data.items()
        }
        _atomic_write_json(INDEX_FILE, slim)
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
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
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


@lru_cache(maxsize=64)
def _subsequence_pattern(needle: str) -> re.Pattern[str]:
    """Motif « fzf » compilé une fois par requête : le moteur C ne monopolise
    pas le GIL, contrairement au générateur Python (le scan de repli gelait
    la TUI ~90 ms par frappe sur un index de 100 000 lignes)."""
    return re.compile(".*".join(re.escape(ch) for ch in needle))


def _is_subsequence(needle: str, hay: str) -> bool:
    """True si ``needle`` apparaît dans ``hay`` dans l'ordre (fzf, sans exiger
    la contiguïté) : ``"frx"`` matche ``firefox``."""
    if not needle:
        return True
    # Préfiltre en C : toute sous-séquence contient la première lettre.
    return needle[0] in hay and _subsequence_pattern(needle).search(hay) is not None


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
        if _is_subsequence(needle, row.attr_lc) or _is_subsequence(needle, row.pname_lc):
            # Dernier rang : ne repousse jamais une correspondance contiguë.
            return 20
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
    """Évite de relancer nix eval pour les mêmes attributs.

    Les descriptions arrivent d'un worker TUI concurrent : le verrou protège
    le dict (``json.dumps`` pendant qu'un autre thread l'insère) et l'écriture
    du cache.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, str] = {}
        if DESC_CACHE_FILE.exists():
            try:
                self._data = json.loads(DESC_CACHE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, attr: str) -> str | None:
        with self._lock:
            text = self._data.get(attr)
        return text if text else None

    def remember(self, attr: str, description: str) -> None:
        if not description:
            return
        with self._lock:
            if self._data.get(attr) == description:
                return
            self._data[attr] = description
            self._persist()

    def _persist(self) -> None:
        # Appelé sous verrou.
        try:
            _atomic_write_json(DESC_CACHE_FILE, self._data)
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
        with self._lock:
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
    except json.JSONDecodeError:
        return {}
    except subprocess.TimeoutExpired:
        return {}
    except subprocess.CalledProcessError:
        return {}
    except OSError:
        return {}


def list_installed_attrs() -> set[str]:
    """Paquets détectés dans le bloc simple environment.systemPackages."""
    path = packages_file()
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _find_package_block(lines)
    if start is None or end is None:
        return set()
    found: set[str] = set()
    for line in lines[start + 1 : end]:
        match = re.match(r"^\s*([a-zA-Z0-9_.-]+)\s*(?:#.*)?$", line)
        if match:
            found.add(match.group(1))
    return found


def _attr_line_pattern(attr: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*{re.escape(attr)}\s*(#.*)?$")


def already_listed(lines: list[str], attr: str) -> bool:
    return find_package_line_index(lines, attr) is not None


def _read_packages_lines() -> list[str] | AddFailure:
    path = packages_file()
    if not path.exists():
        return AddFailure(AddOutcome.FILE_MISSING, f"{path} introuvable.")
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _strip_nix_line_comment(line: str) -> str:
    """Retire les commentaires `#` hors chaînes, sans parser les chaînes Nix."""
    in_string = False
    escaped = False
    for i, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
        elif char == '"':
            in_string = not in_string
        elif char == "#" and not in_string:
            return line[:i]
    return line


def _nix_code_only(line: str) -> str:
    """Commentaires retirés puis contenu des chaînes « … » vidé.

    Compter ``[`` / ``]`` sur la ligne brute comptait aussi les crochets d'une
    chaîne (``"modules[1]"``) : le bloc était alors déclaré non équilibré et
    l'ajout refusé à tort.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for char in _strip_nix_line_comment(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            out.append(char)
    return "".join(out)


def _find_package_block(lines: list[str]) -> tuple[int | None, int | None]:
    """Trouve un bloc simple `anchor = with pkgs; [`; refuse les formes ambiguës."""
    anchor_re = re.compile(rf"^\s*{re.escape(packages_anchor())}\s*=\s*with\s+pkgs\s*;\s*\[\s*(?:#.*)?$")
    starts = [i for i, line in enumerate(lines) if anchor_re.match(line)]
    if len(starts) != 1:
        return None, None
    start = starts[0]
    depth = 1
    end: int | None = None
    for i in range(start + 1, len(lines)):
        stripped = _nix_code_only(lines[i])
        depth += stripped.count("[") - stripped.count("]")
        if depth == 0:
            if stripped.strip() != "];":
                return None, None
            end = i
            break
        if depth < 0:
            return None, None
    return start, end


def find_package_line_index(lines: list[str], attr: str) -> int | None:
    """Index de la ligne du paquet dans un bloc pris en charge."""
    pattern = _attr_line_pattern(attr)
    start, end = _find_package_block(lines)
    if start is None or end is None:
        return None
    for i in range(start + 1, end):
        if pattern.match(lines[i]):
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
    base = packages_file()
    # Horodatage local, simple étiquette de fichier (jamais comparé entre fuseaux).
    ts = time.strftime("%Y%m%d-%H%M%S")
    return base.with_name(f"{base.name}.bak.{ts}")


def _edit_lock_dir() -> Path:
    """Répertoire des verrous d'édition : cache utilisateur, sinon ``/tmp``.

    ``~/.cache`` peut être indisponible (HOME en lecture seule, bac à sable) :
    on retombe sur un répertoire temporaire plutôt que de rendre toute édition
    impossible.
    """
    candidates = [CACHE_DIR]
    try:
        candidates.append(Path(tempfile.gettempdir()) / f"nixpick-{os.getuid()}")
    except (AttributeError, OSError):  # pragma: no cover — plateforme sans uid
        candidates.append(Path(tempfile.gettempdir()) / "nixpick")
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        return base
    return candidates[-1]


def packages_lock_path() -> Path:
    """Verrou d'édition de ``packages_file`` — source unique de vérité.

    Il vit hors du dépôt flake : posé à côté de ``packages.nix``, il laissait
    un fichier orphelin au cœur du dépôt, jamais supprimé et visible dans
    ``git status``.
    """
    digest = hashlib.sha1(str(packages_file()).encode("utf-8")).hexdigest()[:16]
    return _edit_lock_dir() / f"edit-{digest}.lock"


@contextmanager
def _packages_edit_lock() -> Iterator[None]:
    lock_path = packages_lock_path()
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


BACKUP_KEEP = 5


def prune_backups(keep: int = BACKUP_KEEP) -> list[Path]:
    """Garde les ``keep`` sauvegardes les plus récentes, supprime les autres.

    Chaque écriture crée un ``packages.nix.bak.<horodatage>`` : sans purge ils
    s'accumulent à jamais dans le dépôt flake. L'horodatage ``%Y%m%d-%H%M%S``
    est triable lexicalement, donc le tri par nom est aussi un tri chronologique.
    """
    target = packages_file()
    prefix = f"{target.name}.bak."
    try:
        candidates = sorted(
            (
                p
                for p in target.parent.iterdir()
                if p.is_file() and p.name.startswith(prefix)
            ),
            key=lambda p: p.name,
            reverse=True,
        )
    except OSError:
        return []
    removed: list[Path] = []
    for path in candidates[max(0, keep) :]:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            pass
    return removed


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


class NixSyntaxError(ValueError):
    """packages.nix illisible pour nix-instantiate après édition."""


def validate_nix_syntax(path: Path) -> str | None:
    """Retourne un message d'erreur ou None si OK / outil absent."""
    if not shutil.which("nix-instantiate"):
        return None
    try:
        subprocess.run(
            ["nix-instantiate", "--parse", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        msg = (err.stderr or err.stdout or "").strip()
        return msg[:500] if msg else "nix-instantiate --parse a échoué."
    except (OSError, subprocess.TimeoutExpired) as err:
        return str(err)
    return None


def _ensure_valid_packages_file(path: Path, backup: Path) -> None:
    err = validate_nix_syntax(path)
    if err is None:
        return
    restored = True
    detail = ""
    try:
        _atomic_write_text(path, backup.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as restore_err:
        restored = False
        detail = f" Restauration impossible : {restore_err}."
    state = "restauré depuis la sauvegarde" if restored else "NON restauré"
    raise NixSyntaxError(
        f"{path} invalide après modification ({state}).{detail} Détail : {err}"
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        mode = None
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            # mkstemp crée en 0600 : on réapplique le mode du fichier source.
            os.chmod(tmp_name, mode)
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
    INVALID_ATTR = "invalid_attr"


@dataclass
class AddFailure:
    outcome: AddOutcome
    message: str


def plan_add(attr: str, description: str) -> AddPlan | AddFailure:
    invalid = _validate_attr_name(attr)
    if invalid:
        return AddFailure(AddOutcome.INVALID_ATTR, invalid)

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
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        if already_listed(lines, plan.attr):
            raise LookupError(f"{plan.attr} est déjà listé.")
        insert_at, _ = _find_insertion_point(lines)
        shutil.copy2(path, plan.backup_path)
        lines.insert(insert_at, plan.new_line)
        _atomic_write_text(path, "".join(lines))
        _ensure_valid_packages_file(path, plan.backup_path)
        _record_last_op("add", plan.attr, plan.backup_path, path)
        prune_backups()


def _find_insertion_point(lines: list[str]) -> tuple[int, str]:
    anchor = packages_anchor()
    start, end = _find_package_block(lines)
    if start is None:
        raise LookupError(
            f"Bloc « {anchor} » absent, multiple ou dans une forme non prise en charge. "
            "Format attendu : anchor = with pkgs; [ … ];"
        )
    if end is None:
        raise LookupError(f"Fin du bloc « {anchor} » introuvable ou bloc Nix non équilibré.")

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
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        line_idx = find_package_line_index(lines, plan.attr)
        if line_idx is None:
            raise LookupError(f"Ligne introuvable pour {plan.attr}")

        shutil.copy2(path, plan.backup_path)
        del lines[line_idx]
        _atomic_write_text(path, "".join(lines))
        _ensure_valid_packages_file(path, plan.backup_path)
        _record_last_op("remove", plan.attr, plan.backup_path, path)
        prune_backups()
