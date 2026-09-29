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


def install_profile_refs(refs: list[str]) -> int:
    """`nix profile install` sur les refs. Retourne le code de sortie."""
    argv = ["nix", "profile", "install", *refs]
    try:
        proc = subprocess.run(argv, check=False, timeout=INSTALL_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as err:
        print(f"nix profile install : {err}", file=sys.stderr)
        return 1
    code = int(proc.returncode or 0)
    if code != 0:
        print(
            f"nix profile install a quitté avec le code {code} "
            "(relis la sortie Nix ci-dessus).",
            file=sys.stderr,
        )
    return code


def run_sync(*, yes: bool = False, dry_run: bool = False) -> int:
    """Installe les paquets listés absents du profil. Jamais de retrait."""
    if shutil.which("nix") is None:
        print("nix introuvable — installe Nix puis relance.", file=sys.stderr)
        return 1

    listed = sorted(list_installed_attrs())
    if not listed:
        print("Rien à installer : aucun paquet listé.", file=sys.stderr)
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
        print(f"nix profile list : {err}", file=sys.stderr)
        return 1
    if proc.returncode != 0:
        print("Impossible de lire le profil Nix.", file=sys.stderr)
        return 1

    refs = missing_refs(listed, parse_profile_list(proc.stdout))
    if not refs:
        print("Profil à jour : tout ce qui est listé est installé.")
        return 0

    display_cmd = shlex.join(["nix", "profile", "install", *refs])
    if dry_run:
        print(f"[dry-run] {display_cmd}")
        return 0

    if not yes:
        if not sys.stdin.isatty():
            print(
                "Sync non lancé : pas de terminal interactif.\n"
                f"  {display_cmd}\n"
                "Utilise : nixpick sync --yes",
                file=sys.stderr,
            )
            return 1
        try:
            answer = input(
                f"Installer dans le profil ?\n  {display_cmd}\n[o/N] "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return 1
        if answer not in ("o", "oui", "y", "yes"):
            return 0

    code = install_profile_refs(refs)
    if code == 0:
        print(f"Installé : {', '.join(refs)}")
    return code
