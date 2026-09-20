# Thèmes et couleurs

nixpick lit les couleurs dans **`~/.config/nixpick/config.toml`**. Tu peux copier les sections depuis [`config.example.toml`](../config.example.toml) à la racine du dépôt.

Les valeurs sont des couleurs **hex** : `#RRGGBB` ou `#RGB` (raccourci).

## Fichier de config

```toml
[colors]
# TUI Textual (nixpick sans argument)
background = "#2c2d31"
surface = "#232326"
surface_elevated = "#35363b"
text = "#a7aab0"
text_muted = "#737994"
primary = "#57a5e5"
accent = "#51a8b3"
accent_alt = "#bb70d2"
warning = "#e5c07b"
success = "#8fb573"
danger = "#e06c75"
detail_title = "#dbb671"
list_highlight_bg = "#2c2d31"

[colors.rofi]
# Mode nixpick --rofi / nixpick-rofi
background = "#271d1b"
text = "#e8e4df"
border = "#53433f"
prompt = "#ffb59e"
entry_text = "#f1dfda"
selected_background = "#723521"
selected_text = "#ffdbd0"
comment = "#8b8478"
```

Tu n’es pas obligé de tout définir : les clés absentes gardent le **thème par défaut** (gris/bleu TUI, tons chauds Rofi).

## TUI (Textual)

| Clé | Rôle |
|-----|------|
| `background` | Fond principal de l’écran |
| `surface` | Barre du haut, recherche, panneaux |
| `surface_elevated` | Modales de confirmation, aide |
| `text` | Texte courant |
| `text_muted` | Chemins, bordures, pied de page |
| `primary` | Titre « nixpick », nom du paquet, focus recherche |
| `accent` | Raccourcis, ligne surlignée dans la liste |
| `accent_alt` | Bordure de l’aide (`?`) |
| `warning` | Badges simulation / alertes |
| `success` | Indices « ajouter », touches de confirmation |
| `danger` | Retrait, bordure modale de suppression |
| `detail_title` | Titre du panneau « détail » |
| `list_highlight_bg` | Fond de la ligne sélectionnée |

Relance `nixpick` après modification du TOML (le thème est chargé au démarrage).

### Transparence

`transparent_background = true` dans le même fichier (hors section `[colors]`) active le mode **ANSI** pour voir le fond du terminal (Kitty : `background_opacity`). Les couleurs de `[colors]` restent utilisées pour le texte et les bordures.

## Rofi

Les couleurs `[colors.rofi]` servent à **générer** automatiquement :

- `~/.config/nixpick/rofi/nixpick.rasi`
- `~/.config/nixpick/rofi/nixpick-query.rasi`

Ces fichiers sont recréés à chaque lancement de `nixpick --rofi` (ou quand nixpick résout le thème). **Ne les édite pas à la main** : change le TOML à la place.

Ordre de recherche du thème Rofi :

1. Fichiers générés dans `~/.config/nixpick/rofi/`
2. `~/.config/rofi/nixpick*.rasi` (si tu préfères un thème 100 % manuel, place-les ici et évite de dupliquer dans `nixpick/rofi/`)
3. Fichiers embarqués dans le dépôt (`assets/rofi/`)

### Police Rofi

Les `.rasi` générés utilisent `JetBrainsMono Nerd Font 13`. Adapte la ligne `font:` dans un thème manuel si besoin.

## Exemple : aligner sur matugen / Waybar

Si ta barre utilise déjà une palette (ex. tons chauds `#271d1b`), recopie les hex dans `[colors.rofi]`. Pour la TUI, tu peux reprendre les mêmes `surface` / `primary` que ta config Kitty ou un thème Catppuccin — garde un contraste lisible entre `text` et `background`.

## Dépannage

- **Couleur refusée au démarrage** : vérifie le format `#` + 3 ou 6 chiffres hex.
- **Rofi inchangé** : supprime `~/.config/nixpick/rofi/*.rasi` et relance `nixpick --rofi` pour forcer la régénération.
- **Thème Rofi custom** : installe uniquement sous `~/.config/rofi/` et retire les fichiers générés dans `nixpick/rofi/` si tu veux qu’ils ne soient plus prioritaires.
