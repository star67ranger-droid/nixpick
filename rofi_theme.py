"""Génère les thèmes Rofi depuis config.toml."""

from __future__ import annotations

from pathlib import Path

from config import CONFIG_DIR, asset_path
from theme import ColorPalette, RofiColors, get_color_palette

_ROFI_TEMPLATE = """/* Généré par nixpick — ne pas éditer (voir docs/THEMES.md) */
/* comment (palette) : {comment} */
configuration {{
  modi: "dmenu";
}}

* {{
  font: "JetBrainsMono Nerd Font 13";
  background-color: transparent;
  text-color: {text};
}}

window {{
  transparency: "real";
  location: center;
  anchor: center;
  width: 44em;
  border: 2px;
  border-color: {border};
  border-radius: 18px;
  background-color: {background};
}}

mainbox {{
  children: [ inputbar, listview ];
  spacing: 8px;
  padding: 12px 14px 14px 14px;
}}

inputbar {{
  padding: 8px 12px;
  spacing: 8px;
  children: [ prompt, entry ];
}}

prompt {{
  text-color: {prompt};
}}

entry {{
  placeholder: "Filtrer…";
  text-color: {entry_text};
}}

listview {{
  lines: 12;
  columns: 1;
  fixed-height: true;
  spacing: 4px;
}}

element {{
  padding: 8px 12px;
  border-radius: 10px;
}}

element selected {{
  background-color: {selected_background};
  text-color: {selected_text};
}}
"""

_ROFI_QUERY_TEMPLATE = _ROFI_TEMPLATE.replace(
    'placeholder: "Filtrer…";',
    'placeholder: "Rechercher un paquet…";',
)


def _format_rofi(template: str, c: RofiColors) -> str:
    return template.format(
        background=c.background,
        text=c.text,
        border=c.border,
        prompt=c.prompt,
        entry_text=c.entry_text,
        selected_background=c.selected_background,
        selected_text=c.selected_text,
        comment=c.comment,
    )


def rofi_generated_dir() -> Path:
    return CONFIG_DIR / "rofi"


def sync_rofi_themes(palette: ColorPalette | None = None) -> list[Path]:
    """Écrit nixpick.rasi et nixpick-query.rasi dans ~/.config/nixpick/rofi/."""
    pal = palette or get_color_palette()
    out_dir = rofi_generated_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        out_dir / "nixpick.rasi",
        out_dir / "nixpick-query.rasi",
    ]
    paths[0].write_text(_format_rofi(_ROFI_TEMPLATE, pal.rofi), encoding="utf-8")
    paths[1].write_text(
        _format_rofi(_ROFI_QUERY_TEMPLATE, pal.rofi), encoding="utf-8"
    )
    return paths


def bundled_rofi_paths() -> list[Path]:
    return [
        asset_path("rofi", "nixpick.rasi"),
        asset_path("rofi", "nixpick-query.rasi"),
    ]
