"""Traducteur d'erreurs : chaque panne connue gagne un conseil actionnable.

Utilisé sur les chemins d'erreur CLI (garde-fou `main()`, `--build-index-only`).
La TUI a déjà ses messages par type (`_index_error_message`) : on n'y touche pas.
"""

from __future__ import annotations

import json
import subprocess

from i18n import t


def explain_error(err: BaseException) -> str | None:
    """Conseil pour `err`, ou None si rien de connu (pas de bruit)."""
    if isinstance(err, subprocess.TimeoutExpired):
        return t("err.timeout")
    if isinstance(err, json.JSONDecodeError):
        return t("err.corrupt_index")
    if isinstance(err, FileNotFoundError):
        name = err.filename if isinstance(err.filename, str) else None
        return t("err.missing_binary", name=name or "?")
    if isinstance(err, OSError):
        return t("err.cache_io")
    if isinstance(err, subprocess.CalledProcessError):
        if err.returncode == -9:
            return t("err.sigkill")
        return _explain_text(str(err))
    return _explain_text(str(err))


def _explain_text(text: str) -> str | None:
    lowered = text.lower()
    if "sigkill" in lowered or "signal 9" in lowered:
        return t("err.sigkill")
    if "nixpkgs" in lowered and "not found" in lowered:
        return t("err.no_channel")
    if "not tracked by git" in lowered:
        return t("err.untracked_git")
    return None
