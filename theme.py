"""Palette de couleurs (config.toml [colors] / [colors.rofi])."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from config import _load_toml

_HEX_RE = re.compile(r"^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})$")


def _norm_hex(value: str, field: str) -> str:
    raw = str(value).strip()
    if not _HEX_RE.match(raw):
        raise ValueError(f"{field} : couleur invalide {raw!r} (attendu #RGB ou #RRGGBB)")
    if len(raw) == 4:
        r, g, b = raw[1], raw[2], raw[3]
        return f"#{r}{r}{g}{g}{b}{b}".lower()
    return raw.lower()


@dataclass(frozen=True)
class TuiColors:
    # Neutres zinc froids + UN seul accent (bleu désaturé) ; le vert / rouge /
    # ambre restent réservés aux états (installé, erreur, simulation).
    background: str = "#17181c"
    surface: str = "#101114"
    surface_elevated: str = "#212328"
    text: str = "#c8ccd2"
    text_muted: str = "#838a94"
    primary: str = "#7ba4e0"
    accent: str = "#8ab7ea"
    accent_alt: str = "#6f9ad6"
    warning: str = "#d6b072"
    success: str = "#8cb37f"
    danger: str = "#d9757e"
    detail_title: str = "#838a94"
    list_highlight_bg: str = "#21242a"


@dataclass(frozen=True)
class RofiColors:
    background: str = "#271d1b"
    text: str = "#e8e4df"
    border: str = "#53433f"
    prompt: str = "#ffb59e"
    entry_text: str = "#f1dfda"
    selected_background: str = "#723521"
    selected_text: str = "#ffdbd0"
    comment: str = "#8b8478"


@dataclass(frozen=True)
class ColorPalette:
    tui: TuiColors
    rofi: RofiColors


_TUI_FIELDS = {f.name for f in TuiColors.__dataclass_fields__.values()}
_ROFI_FIELDS = {f.name for f in RofiColors.__dataclass_fields__.values()}


def _merge_table(defaults: dict[str, str], table: dict | None, fields: set[str]) -> dict[str, str]:
    out = dict(defaults)
    if not table:
        return out
    for key, value in table.items():
        if key not in fields:
            continue
        out[key] = _norm_hex(str(value), f"colors.{key}")
    return out


def load_color_palette() -> ColorPalette:
    data = _load_toml()
    raw_colors = data.get("colors")
    root: dict[str, Any] = raw_colors if isinstance(raw_colors, dict) else {}
    raw_rofi = root.get("rofi")
    rofi_table: dict[str, Any] = raw_rofi if isinstance(raw_rofi, dict) else {}

    tui_defaults = {k: getattr(TuiColors(), k) for k in _TUI_FIELDS}
    rofi_defaults = {k: getattr(RofiColors(), k) for k in _ROFI_FIELDS}

    tui_merged = _merge_table(tui_defaults, root, _TUI_FIELDS)
    rofi_merged = _merge_table(rofi_defaults, rofi_table, _ROFI_FIELDS)

    return ColorPalette(
        tui=TuiColors(**tui_merged),
        rofi=RofiColors(**rofi_merged),
    )


@lru_cache(maxsize=1)
def get_color_palette() -> ColorPalette:
    return load_color_palette()


def reset_color_palette_cache() -> None:
    get_color_palette.cache_clear()
