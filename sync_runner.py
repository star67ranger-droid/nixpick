"""Installe dans le profil Nix les paquets listés mais absents (hors NixOS).

Équivalent de `rebuild` sans NixOS : `nix profile install nixpkgs#attr`
pour chaque attribut listé et absent du profil. Ne désinstalle jamais rien.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys

from engine import list_installed_attrs
from i18n import t
from messages import is_affirmative

INSTALL_TIMEOUT = 600

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def parse_profile_list(output: str) -> list[dict[str, str]]:
    """Parse `nix profile list` (blocs `Name:` / `Flake attribute:`)."""
    entries: list[dict[str, str]] = []
    for block in _ANSI_RE.sub("", output).split("\n\n"):
        entry: dict[str, str] = {}
        for line in block.splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() in ("Name", "Flake attribute"):
                entry[key.strip().lower().replace(" ", "_")] = value.strip()
        if entry:
            entries.append(entry)
    return entries


def is_installed(attr: str, entries: list[dict[str, str]]) -> bool:
    """Attr couvert si le profil contient `….<attr>` ou un nom exact."""
    for entry in entries:
        if entry.get("name") == attr:
            return True
        if entry.get("flake_attribute", "").endswith(f".{attr}"):
            return True
    return False


def missing_refs(
    listed: list[str], entries: list[dict[str, str]]
) -> list[str]:
    """Références `nixpkgs#attr` à installer (déjà présents exclus)."""
    return [f"nixpkgs#{attr}" for attr in listed if not is_installed(attr, entries)]


def upgradeable_refs(
    listed: list[str], entries: list[dict[str, str]]
) -> list[str]:
    """Flake attributes installés correspondant à la liste (pour upgrade).

    Chemin complet (`legacyPackages.x.htop`) : `nix profile upgrade`
    l'accepte et met à jour sur place, quelle que soit l'origine.
    """
    refs: list[str] = []
    for attr in listed:
        for entry in entries:
            flake_attr = entry.get("flake_attribute", "")
            if flake_attr.endswith(f".{attr}") or entry.get("name") == attr:
                if flake_attr and flake_attr not in refs:
                    refs.append(flake_attr)
                break
    return refs


def upgrade_profile_refs(refs: list[str]) -> int:
    """`nix profile upgrade` sur les refs. Retourne le code de sortie."""
    argv = ["nix", "profile", "upgrade", *refs]
    try:
        proc = subprocess.run(argv, check=False, timeout=INSTALL_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as err:
        print(t("sync.upgrade_failed_os", err=err), file=sys.stderr)
        return 1
    code = int(proc.returncode or 0)
    if code != 0:
        print(t("sync.upgrade_failed", code=code), file=sys.stderr)
    return code


def install_profile_refs(refs: list[str]) -> int:
    """`nix profile install` sur les refs. Retourne le code de sortie."""
    argv = ["nix", "profile", "install", *refs]
    try:
        proc = subprocess.run(argv, check=False, timeout=INSTALL_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as err:
        print(t("sync.install_failed", err=err), file=sys.stderr)
        return 1
    code = int(proc.returncode or 0)
    if code != 0:
        print(
            t("sync.install_exit", code=code),
            file=sys.stderr,
        )
    return code


def run_sync(*, yes: bool = False, dry_run: bool = False, upgrade: bool = False) -> int:
    """Installe les paquets listés absents du profil (+ upgrade ciblé).

    Jamais de retrait. L'upgrade ne touche que les listés déjà installés,
    par leur flake attribute complet (mise à jour sur place).
    """
    if shutil.which("nix") is None:
        print(t("sync.no_nix"), file=sys.stderr)
        return 1

    listed = sorted(list_installed_attrs())
    if not listed:
        print(t("sync.empty_list"), file=sys.stderr)
        return 0

    try:
        proc = subprocess.run(
            ["nix", "profile", "list"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as err:
        print(t("sync.list_failed", err=err), file=sys.stderr)
        return 1
    if proc.returncode != 0:
        print(t("sync.unreadable"), file=sys.stderr)
        tail = "\n".join(proc.stderr.strip().splitlines()[-3:])
        if tail:
            print(tail, file=sys.stderr)
        return 1

    entries = parse_profile_list(proc.stdout)
    refs = missing_refs(listed, entries)
    up_refs = upgradeable_refs(listed, entries) if upgrade else []
    if not refs and not up_refs:
        print(t("sync.uptodate"))
        return 0

    install_cmd = shlex.join(["nix", "profile", "install", *refs]) if refs else ""
    upgrade_cmd = shlex.join(["nix", "profile", "upgrade", *up_refs]) if up_refs else ""
    if dry_run:
        if install_cmd:
            print(f"[dry-run] {install_cmd}")
        if upgrade_cmd:
            print(f"[dry-run] {upgrade_cmd}")
        return 0

    if not yes:
        if not sys.stdin.isatty():
            print(
                t("sync.no_tty", cmd=install_cmd or upgrade_cmd),
                file=sys.stderr,
            )
            return 1
        if install_cmd and upgrade_cmd:
            prompt = t("sync.confirm_both", install=install_cmd, upgrade=upgrade_cmd)
        elif upgrade_cmd:
            prompt = t("sync.confirm_upgrade", cmd=upgrade_cmd)
        else:
            prompt = t("sync.confirm", cmd=install_cmd)
        try:
            answer = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return 1
        if not is_affirmative(answer):
            return 0

    if refs:
        code = install_profile_refs(refs)
        if code == 0:
            print(t("sync.installed", refs=", ".join(refs)))
        if code != 0:
            return code
    if up_refs:
        ucode = upgrade_profile_refs(up_refs)
        if ucode == 0:
            print(t("sync.upgraded", refs=", ".join(up_refs)))
        return ucode
    return 0
