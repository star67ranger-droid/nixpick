#!/usr/bin/env python3
"""nixpick — chercher un paquet nixpkgs et l'ajouter à sa configuration NixOS.

Idée de départ : taper le nom d'une app dans une barre de recherche, et qu'elle
arrive dans la config sans avoir à ouvrir un fichier ni deviner le bon nom
d'attribut. Cette version est en ligne de commande ; l'interface graphique
viendra par-dessus, ce fichier restant le moteur.

Trois façons d'interroger nixpkgs ont été mesurées sur cette machine :

    nix search nixpkgs <terme>      > 25 s, à chaque appel      → inutilisable
    nix-env -qaP --json --meta      > 10 min                    → inutilisable
    nix-env -qaP --json              ~21 s, mis en cache        → retenu
    nix eval (descriptions en lot)   ~0,3 s pour 12 paquets     → retenu

D'où l'architecture : un index complet sans description, construit une fois et
gardé en cache, pour que la recherche soit instantanée et fonctionne hors
ligne ; puis les descriptions des seuls résultats affichés, récupérées à la
demande en un unique appel.

Usage :
    nixpick.py <terme>          cherche, propose, ajoute après confirmation
    nixpick.py --refresh        reconstruit l'index puis cherche
    nixpick.py --dry-run <t>    montre la modification sans l'écrire
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ─── Réglages propres à ma machine ──────────────────────────────────────────
# Les paquets système vivent dans un module thématique, pas dans
# configuration.nix (voir /etc/nixos/AGENTS.md).
PACKAGES_FILE = Path("/etc/nixos/modules/packages.nix")
ANCHOR = "environment.systemPackages"

CACHE_DIR = Path.home() / ".cache" / "nixpick"
INDEX_FILE = CACHE_DIR / "index.json"
INDEX_MAX_AGE_DAYS = 7

RESULT_LIMIT = 12

# ─── Affichage ──────────────────────────────────────────────────────────────
BOLD, DIM, GREEN, YELLOW, RED, RESET = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"
)


def say(msg: str = "") -> None:
    """Tout l'affichage part sur stderr, pour laisser stdout libre."""
    print(msg, file=sys.stderr)


def run(cmd: list[str], timeout: int) -> str:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=True
        ).stdout
    except FileNotFoundError:
        say(f"{RED}{cmd[0]} est introuvable. Ce script attend un système NixOS.{RESET}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        say(f"{RED}{cmd[0]} a dépassé {timeout} s, abandon.{RESET}")
        sys.exit(1)
    except subprocess.CalledProcessError as err:
        say(f"{RED}{cmd[0]} a échoué :{RESET} {(err.stderr or '').strip()[:300]}")
        sys.exit(1)


# ─── Index ──────────────────────────────────────────────────────────────────
def index_age_days() -> float | None:
    """Âge de l'index en jours, ou None s'il n'existe pas encore."""
    if not INDEX_FILE.exists():
        return None
    return (time.time() - INDEX_FILE.stat().st_mtime) / 86400


def build_index() -> dict:
    """Construit l'index de nixpkgs et le met en cache.

    Volontairement sans `--meta` : l'ajouter fait passer l'indexation de vingt
    secondes à plus de dix minutes. Les descriptions sont récupérées plus tard,
    seulement pour les résultats affichés.
    """
    say(f"{DIM}Construction de l'index nixpkgs (une vingtaine de secondes)…{RESET}")
    raw = run(["nix-env", "-qaP", "--json"], timeout=600)
    data = json.loads(raw)

    # On ne garde que ce qui sert : l'index complet avec tous les champs pèse
    # 25 Mo, ce qui ralentit chaque lancement au chargement.
    slim = {
        key: {"pname": pkg.get("pname", ""), "version": pkg.get("version", "")}
        for key, pkg in data.items()
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(slim))
    say(f"{GREEN}{len(slim)} paquets indexés.{RESET}")
    return slim


def load_index(refresh: bool = False) -> dict:
    age = index_age_days()
    if refresh or age is None:
        return build_index()
    if age > INDEX_MAX_AGE_DAYS:
        say(f"{DIM}Index vieux de {age:.0f} jours, reconstruction.{RESET}")
        return build_index()
    return json.loads(INDEX_FILE.read_text())


# ─── Recherche ──────────────────────────────────────────────────────────────
def attr_name(key: str) -> str:
    """`nixos.ripgrep` → `ripgrep`.

    nix-env préfixe chaque clé par le nom du channel ; `with pkgs; [ ... ]`
    attend l'attribut sans ce préfixe.
    """
    return key.split(".", 1)[1] if "." in key else key


def search(index: dict, term: str, limit: int = RESULT_LIMIT) -> list[tuple[str, str]]:
    """Cherche `term` et trie par pertinence. Renvoie [(attribut, version)].

    Le score privilégie une correspondance exacte, puis un début de nom, puis
    une correspondance partielle : chercher « git » doit remonter git avant
    les dizaines de paquets dont le nom contient git.
    """
    needle = term.lower()
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

        # À score égal, le nom le plus court est presque toujours le bon :
        # « firefox » avant « firefox-unwrapped ».
        results.append((-score, len(attr), attr, pkg.get("version", "")))

    results.sort()
    return [(attr, version) for _, _, attr, version in results[:limit]]


def fetch_descriptions(attrs: list[str]) -> dict[str, str]:
    """Récupère les descriptions des paquets donnés, en un seul appel.

    `tryEval` et les valeurs par défaut sont indispensables : une partie de
    nixpkgs échoue à l'évaluation (paquets cassés, non libres, ou dépendant
    d'un système différent) et ferait tomber tout le lot.
    """
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
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout
        return json.loads(raw)
    except Exception:
        # Une description manquante n'est pas une raison d'échouer : on affiche
        # les résultats sans elles.
        return {}


# ─── Lecture / écriture de la configuration ─────────────────────────────────
def already_listed(lines: list[str], attr: str) -> bool:
    """Le paquet figure-t-il déjà dans le fichier ?"""
    pattern = re.compile(rf"^\s*{re.escape(attr)}\s*(#.*)?$")
    return any(pattern.match(line) for line in lines)


def find_insertion_point(lines: list[str]) -> tuple[int, str]:
    """Renvoie (index de ligne où insérer, indentation à utiliser).

    On repère le bloc `environment.systemPackages` puis le `];` qui le ferme,
    et on insère juste avant. L'indentation est reprise sur la première entrée
    existante, pour ne pas dénaturer la mise en forme du fichier.
    """
    start = next((i for i, l in enumerate(lines) if ANCHOR in l), None)
    if start is None:
        raise LookupError(f"« {ANCHOR} » est introuvable dans {PACKAGES_FILE}")

    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() == "];"), None)
    if end is None:
        raise LookupError(f"La fin du bloc « {ANCHOR} » est introuvable")

    indent = "  "
    for line in lines[start + 1:end]:
        if line.strip() and not line.strip().startswith("#"):
            indent = line[:len(line) - len(line.lstrip())]
            break

    # Reculer avant les lignes vides qui précèdent le `];`.
    insert_at = end
    while insert_at - 1 > start and not lines[insert_at - 1].strip():
        insert_at -= 1
    return insert_at, indent


def add_package(attr: str, description: str, dry_run: bool) -> bool:
    """Ajoute `attr` au bloc systemPackages. Renvoie True si le fichier a changé."""
    if not PACKAGES_FILE.exists():
        say(f"{RED}{PACKAGES_FILE} est introuvable.{RESET}")
        return False

    lines = PACKAGES_FILE.read_text().splitlines(keepends=True)

    if already_listed(lines, attr):
        say(f"{YELLOW}{attr} est déjà dans ta configuration. Rien à faire.{RESET}")
        return False

    insert_at, indent = find_insertion_point(lines)
    # La description sert de pense-bête dans la config : tronquée, pour ne pas
    # faire déborder la ligne et rester lisible six mois plus tard.
    short = description[:55].rstrip()
    if len(description) > 55:
        short += "…"
    comment = f"  # {short}" if short else ""
    new_line = f"{indent}{attr}{comment}\n"

    say()
    say(f"{BOLD}Modification prévue dans {PACKAGES_FILE} :{RESET}")
    for i in range(max(0, insert_at - 2), insert_at):
        say(f"  {DIM}{lines[i].rstrip()}{RESET}")
    say(f"  {GREEN}+ {new_line.rstrip()}{RESET}")

    if dry_run:
        say(f"\n{DIM}Mode --dry-run : rien n'a été écrit.{RESET}")
        return False

    try:
        answer = input("\nJ'écris ? [o/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        say()
        return False
    if answer not in ("o", "oui", "y"):
        say("Abandonné.")
        return False

    backup = PACKAGES_FILE.with_suffix(".nix.bak")
    try:
        shutil.copy2(PACKAGES_FILE, backup)
        lines.insert(insert_at, new_line)
        PACKAGES_FILE.write_text("".join(lines))
    except PermissionError:
        say(f"{RED}Pas les droits d'écriture sur {PACKAGES_FILE}.{RESET}")
        say(f"{DIM}Relance avec sudo, ou donne-toi les droits sur /etc/nixos.{RESET}")
        return False

    say(f"{GREEN}Ajouté.{RESET} Sauvegarde : {backup}")
    return True


def print_next_steps() -> None:
    """Rappelle quoi faire ensuite, sans rien lancer.

    Volontairement non automatisé : d'après /etc/nixos/AGENTS.md, un `switch`
    commit ET pousse tout /etc/nixos sur origin/main. Déclencher ça tout seul
    serait une mauvaise surprise.
    """
    say()
    say(f"{BOLD}Pour appliquer :{RESET}")
    say("  sudo nixos-rebuild switch --flake /etc/nixos#nixos")
    say()
    say(f"{DIM}Rappel : un switch commit et pousse /etc/nixos automatiquement.")
    say("Pour annuler avant d'appliquer :")
    say(f"  cp {PACKAGES_FILE}.bak {PACKAGES_FILE}{RESET}")


# ─── Point d'entrée ─────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cherche un paquet nixpkgs et l'ajoute à la config NixOS."
    )
    parser.add_argument("term", nargs="?", help="ce que tu cherches")
    parser.add_argument("--refresh", action="store_true",
                        help="reconstruit l'index avant de chercher")
    parser.add_argument("--dry-run", action="store_true",
                        help="montre la modification sans l'écrire")
    args = parser.parse_args()

    if not args.term:
        if args.refresh:
            build_index()
            return 0
        parser.print_help()
        return 1

    index = load_index(refresh=args.refresh)
    results = search(index, args.term)

    if not results:
        say(f"{YELLOW}Rien trouvé pour « {args.term} ».{RESET}")
        say(f"{DIM}Essaie un mot plus court, ou --refresh si l'index est vieux.{RESET}")
        return 1

    descriptions = fetch_descriptions([attr for attr, _ in results])

    say()
    for n, (attr, version) in enumerate(results, 1):
        desc = (descriptions.get(attr) or "")[:70]
        say(f"  {BOLD}{n:>2}{RESET}. {GREEN}{attr}{RESET} {DIM}{version}{RESET}")
        if desc:
            say(f"      {DIM}{desc}{RESET}")

    try:
        choice = input(f"\nLequel ? [1-{len(results)}, Entrée pour annuler] ").strip()
    except (EOFError, KeyboardInterrupt):
        say()
        return 1

    if not choice:
        return 0
    if not choice.isdigit() or not 1 <= int(choice) <= len(results):
        say(f"{RED}Choix invalide.{RESET}")
        return 1

    attr, _ = results[int(choice) - 1]
    if add_package(attr, descriptions.get(attr, ""), args.dry_run):
        print_next_steps()
    return 0


if __name__ == "__main__":
    sys.exit(main())
