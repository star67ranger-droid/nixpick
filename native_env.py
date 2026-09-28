"""Prérequis natifs pour OpenTUI (yoga / libstdc++).

opentui embarque yoga, une librairie C++ qui charge ``libstdc++.so.6`` au
``import``. Sur NixOS aucune libstdc++ n'est sur le chemin du chargeur par
défaut : l'import échoue avec ``libstdc++.so.6: cannot open shared object
file``. Ce module précharge la bibliothèque en mémoire (même *soname* → le
``dlopen`` suivant la retrouve), sans toucher aux variables d'environnement
du processus.

Sans effet sur les plateformes où la bibliothèque est déjà résoluble
(la plupart des distributions, macOS via Homebrew, Windows).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
from functools import lru_cache

_SONAME = "libstdc++.so.6"

_PATTERNS = (
    "/nix/store/*-gcc-*-lib/lib/libstdc++.so.6",
    "/usr/lib/libstdc++.so.6",
    "/usr/lib64/libstdc++.so.6",
    "/usr/lib/x86_64-linux-gnu/libstdc++.so.6",
    "/opt/homebrew/opt/gcc/lib/gcc-current/libstdc++.so.6",
)


def _is_elf64(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            header = handle.read(5)
    except OSError:
        return False
    return header[:4] == b"\x7fELF" and header[4] == 2


def _try_load(path: str) -> str | None:
    if not path or not _is_elf64(path):
        return None
    try:
        ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
    except OSError:
        return None
    return path


@lru_cache(maxsize=1)
def ensure_opentui_libs() -> str | None:
    """Charge ``libstdc++`` si le chargeur ne la trouve pas.

    Retourne le chemin chargé, le nom résolu, ou ``None`` si rien n'était
    nécessaire (ou introuvable).
    """
    try:
        ctypes.CDLL(_SONAME, mode=ctypes.RTLD_GLOBAL)
        return _SONAME
    except OSError:
        pass

    for directory in os.environ.get("LD_LIBRARY_PATH", "").split(":"):
        loaded = _try_load(os.path.join(directory, _SONAME))
        if loaded:
            return loaded

    for pattern in _PATTERNS:
        for candidate in sorted(glob.glob(pattern)):
            loaded = _try_load(candidate)
            if loaded:
                return loaded

    discovered = ctypes.util.find_library("stdc++")
    if discovered:
        loaded = _try_load(discovered)
        if loaded:
            return loaded

    return None
