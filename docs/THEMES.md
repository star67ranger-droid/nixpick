# Thèmes et couleurs

nixpick lit les couleurs dans **`~/.config/nixpick/config.toml`**. Tu peux copier les sections depuis [`config.example.toml`](../config.example.toml) à la racine du dépôt.

Les valeurs sont des couleurs **hex** : `#RRGGBB` ou `#RGB` (raccourci).

## Fichier de config

```toml
[colors]
# TUI OpenTUI (nixpick sans argument) — neutres zinc + un seul accent bleu
background = "#17181c"
surface = "#101114"
surface_elevated = "#212328"
text = "#c8ccd2"
text_muted = "#838a94"
primary = "#7ba4e0"
accent = "#8ab7ea"
accent_alt = "#6f9ad6"
warning = "#d6b072"
success = "#8cb37f"
danger = "#d9757e"
detail_title = "#838a94"
list_highlight_bg = "#21242a"

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

Tu n’es pas obligé de tout définir : les clés absentes gardent le **thème par défaut** (neutres zinc + un seul accent bleu pour la TUI, tons chauds Rofi).

## TUI (OpenTUI)

Le défaut ne compte qu’**une seule teinte** (le bleu de `primary` / `accent` / `accent_alt`) :
le vert, le rouge et l’ambre ne servent qu’aux **états** (installé, erreur, simulation).

| Clé | Rôle |
|-----|------|
| `background` | Fond principal de l’écran |
| `surface` | Barre du haut, champ de recherche, pied de page |
| `surface_elevated` | Modales de confirmation, aide, toasts |
| `text` | Texte courant |
| `text_muted` | Titres de panneau, compteurs, versions, labels du pied de page |
| `primary` | Accent unique : marque « nixpick », prompt, champ focalisé, ligne sélectionnée, nom du paquet |
| `accent` | Raccourcis (pied de page, colonne de l’aide) |
| `accent_alt` | Flags de la barre (ex. `transp.`), bordure de l’aide |
| `warning` | Simulation, chargement de l’index |
| `success` | Point `●` installé, indice « ajouter », confirmation |
| `danger` | Retrait, erreur, bordure modale de suppression |
| `detail_title` | Bordure et titre du panneau « détail » (gris, comme le titre de liste) |
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

1. Fichiers générés dans `~/.config/nixpick/rofi/` — **recréés à chaque lancement**, ils gagnent donc toujours
2. `~/.config/rofi/nixpick*.rasi` — secours, utilisé seulement si la génération échoue
3. Fichiers embarqués dans le dépôt (`assets/rofi/`)

> Un `.rasi` posé à la main dans `~/.config/rofi/` est donc **ignoré** tant que
> nixpick génère les siens. Pour un thème vraiment personnalisé, lance rofi
> toi-même : `rofi -dmenu -theme ~/mon-theme.rasi -p "…"`.
> Pour changer uniquement les couleurs, `[colors.rofi]` suffit.

### Police Rofi

Les `.rasi` générés utilisent `JetBrainsMono Nerd Font 13`. Adapte la ligne `font:` dans un thème manuel si besoin.

## Exemple : aligner sur matugen / Waybar

Si ta barre utilise déjà une palette (ex. tons chauds `#271d1b`), recopie les hex dans `[colors.rofi]`. Pour la TUI, tu peux reprendre les mêmes `surface` / `primary` que ta config Kitty ou un thème Catppuccin — garde un contraste lisible entre `text` et `background`.

## Dépannage

- **Couleur refusée au démarrage** : vérifie le format `#` + 3 ou 6 chiffres hex.
- **Rofi inchangé** : supprime `~/.config/nixpick/rofi/*.rasi` et relance `nixpick --rofi` pour forcer la régénération.
- **Thème Rofi custom** : les fichiers de `~/.config/nixpick/rofi/` sont réécrits à chaque lancement ; un fichier copié dans `~/.config/rofi/` ne servira que si la génération échoue. Pour un rasi entièrement différent, appelle `rofi -theme` directement.
