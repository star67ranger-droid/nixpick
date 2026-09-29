#!/usr/bin/env bash
# Installation locale (clone GitHub → venv → ~/.local/bin)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"
BIN_DIR="${HOME}/.local/bin"
CONFIG_DIR="${HOME}/.config/nixpick"
ROFI_DIR="${HOME}/.config/rofi"

echo "→ nixpick dans $ROOT"

if ! command -v python3 >/dev/null; then
  echo "python3 requis." >&2
  exit 1
fi

if [[ ! -d "$VENV" ]]; then
  echo "→ venv"
  python3 -m venv "$VENV"
fi

echo "→ dépendances"
"$VENV/bin/pip" install -q -U pip
"$VENV/bin/pip" install -q -e "$ROOT"

mkdir -p "$BIN_DIR"
ln -sf "$ROOT/bin/nixpick" "$BIN_DIR/nixpick"
ln -sf "$ROOT/scripts/nixpick-rofi.sh" "$BIN_DIR/nixpick-rofi"
chmod +x "$ROOT/bin/nixpick" "$ROOT/scripts/nixpick-rofi.sh"

mkdir -p "$CONFIG_DIR" "$ROFI_DIR"
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
  cp "$ROOT/config.example.toml" "$CONFIG_DIR/config.toml"
  echo "→ config créée : $CONFIG_DIR/config.toml (à adapter)"
fi

for theme in nixpick.rasi nixpick-query.rasi; do
  if [[ -f "$ROOT/assets/rofi/$theme" ]]; then
    # -n : ne jamais écraser une personnalisation manuelle.
    cp -n "$ROOT/assets/rofi/$theme" "$ROFI_DIR/$theme"
  fi
done

# Complétions : artefacts générés, on écrase à chaque install (une
# complétion périmée mentirait sur les sous-commandes).
mkdir -p "${HOME}/.local/share/bash-completion/completions" \
  "${HOME}/.local/share/zsh/site-functions" \
  "${HOME}/.config/fish/completions"
cp -f "$ROOT/assets/completions/nixpick.bash" \
  "${HOME}/.local/share/bash-completion/completions/nixpick"
cp -f "$ROOT/assets/completions/_nixpick" \
  "${HOME}/.local/share/zsh/site-functions/_nixpick"
cp -f "$ROOT/assets/completions/nixpick.fish" \
  "${HOME}/.config/fish/completions/nixpick.fish"

echo ""
echo "OK. Ajoute ~/.local/bin au PATH si besoin, puis :"
echo "  nixpick --print-config"
echo "  nixpick"
echo "  nixpick --rofi   # ou nixpick-rofi"
