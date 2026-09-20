"""Palette de couleurs (config.toml [colors] / [colors.rofi])."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from config import CONFIG_FILE, _load_toml

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
    background: str = "#2c2d31"
    surface: str = "#232326"
    surface_elevated: str = "#35363b"
    text: str = "#a7aab0"
    text_muted: str = "#737994"
    primary: str = "#57a5e5"
    accent: str = "#51a8b3"
    accent_alt: str = "#bb70d2"
    warning: str = "#e5c07b"
    success: str = "#8fb573"
    danger: str = "#e06c75"
    detail_title: str = "#dbb671"
    list_highlight_bg: str = "#2c2d31"

    def rich(self, key: str) -> str:
        """Couleur sans # pour le markup Rich/Textual ([b #hex])."""
        return getattr(self, key).lstrip("#")


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
    root = data.get("colors") if isinstance(data.get("colors"), dict) else {}
    rofi_table = root.get("rofi") if isinstance(root.get("rofi"), dict) else {}

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


def palette_config_path_hint() -> str:
    return str(CONFIG_FILE)
