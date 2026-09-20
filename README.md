# nixpick

Recherche dans **nixpkgs** et ajout / retrait de paquets dans ton fichier NixOS `environment.systemPackages` — sans ouvrir l’éditeur à la main.

Conçu pour une config **modulaire** (`modules/packages.nix`), pas pour tout mettre dans `configuration.nix`.

**Projet vibecodé** : idée et usage réel (ma config NixOS / Hyprland) par Pikeo ; le code a été itéré avec des assistants IA (Cursor), puis durci (écritures atomiques, validation des attrs, audits). Les PR et retours sont les bienvenus — l’objectif est un petit outil utile et lisible, pas une usine à gaz.

## Prérequis

- **NixOS** (ou machine avec `nix-env` / `nix eval` sur `<nixpkgs>`)
- Python **3.11+**
- Optionnel : **Rofi** pour `nixpick --rofi`

## Installation

### Rapide (clone + script)

```bash
git clone https://github.com/star67ranger-droid/nixpick.git
cd nixpick
./scripts/install.sh
```

Le script crée un venv, installe les deps, lie `nixpick` et `nixpick-rofi` dans `~/.local/bin`, copie `config.example.toml` → `~/.config/nixpick/config.toml` et les thèmes Rofi.

### Manuel

```bash
cd nixpick
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
chmod +x bin/nixpick
ln -sf "$(pwd)/bin/nixpick" ~/.local/bin/nixpick
mkdir -p ~/.config/nixpick
cp config.example.toml ~/.config/nixpick/config.toml
```

### pip (éditable)

```bash
pip install -e .
```

## Configuration

Fichier : `~/.config/nixpick/config.toml`

```toml
packages_file = "/etc/nixos/modules/packages.nix"
packages_anchor = "environment.systemPackages"
rebuild_command = "sudo nixos-rebuild switch --flake /etc/nixos#nixos"
transparent_background = false
```

**Couleurs (TUI + Rofi)** : section `[colors]` et `[colors.rofi]` dans le même fichier. Guide complet : [docs/THEMES.md](docs/THEMES.md). Modèle : [`config.example.toml`](config.example.toml).

Variables d’environnement (prioritaires) :

| Variable | Rôle |
|----------|------|
| `NIXPICK_PACKAGES_FILE` | Fichier `.nix` à modifier |
| `NIXPICK_PACKAGES_ANCHOR` | Ligne d’ancrage (défaut `environment.systemPackages`) |
| `NIXPICK_REBUILD_COMMAND` | Affichée après ajout / retrait |

Vérifier :

```bash
nixpick --print-config
```

## Commandes

| Commande | Description |
|----------|-------------|
| `nixpick` | **TUI** Textual (recherche live, détail, ajout / retrait) |
| `nixpick firefox` | Mode **CLI** interactif |
| `nixpick --remove spotify` | Retire un attribut du fichier configuré |
| `nixpick --rofi` | Lanceur **Rofi** (2 étapes : terme → liste) |
| `nixpick-rofi` | Alias shell vers `--rofi` |
| `nixpick --dry-run` | Simulation (aucune écriture) |
| `nixpick --refresh` | Reconstruit l’index nixpkgs au démarrage |
| `nixpick --build-index-only` | Index seulement, puis quitte |
| `nixpick --list-installed` | Attributs déjà dans `systemPackages` (une ligne par attr) |
| `nixpick --list-installed --json` | Même liste en une ligne JSON (`attrs`, `count`, `packages_file`, `index_age_days`) |
| `nixpick --undo` | Restaure le fichier configuré depuis la sauvegarde de la dernière écriture (pas de rebuild) |
| `nixpick rebuild` | Lance `rebuild_command` (confirmation interactive) |
| `nixpick rebuild -y` | Rebuild sans redemander (scripts) |
| `nixpick rebuild -y --terminal` | Ouvre **kitty** / **foot** pour `sudo` et la sortie |
| `nixpick doctor` | Vérifie fichier packages, cache index, verrou, outils (`nix-env`, Rofi), commande rebuild |
| `nixpick doctor --json` | Même diagnostic en JSON |
| `nixpick --why <attr>` | Indique si l’attribut est dans le fichier configuré (ligne approximative) |
| `nixpick --transparent` / `--opaque` | Fond TUI (ANSI / Kitty) |

### TUI — raccourcis

- **Taper** : recherche (min. 2 caractères)
- **↵** : ajouter · **x** : retirer (si déjà dans la config)
- **l** : catalogue des paquets déjà listés
- **i** : masquer les paquets installés · **d** : simulation
- **Ctrl+R** : reconstruire l’index · **?** / **F1** : aide

Les entrées déjà présentes dans `systemPackages` sont marquées **●**.

### Rofi

1. Saisir un terme (ex. `cursor`) → **Entrée**
2. Choisir dans la liste · **✓** = déjà dans `systemPackages` (retrait proposé) · sans ✓ = ajout
3. Aperçu **read-only** du diff (`+` / `-` autour de la ligne concernée), puis **Confirmer l'ajout** / **Confirmer le retrait** ou **Annuler** (sans notification)

Après validation : notification, puis menu **« Lancer le rebuild »** / **« Plus tard »** (rebuild dans un terminal kitty si tu acceptes). Sinon : `nixpick rebuild`.

Thèmes : `assets/rofi/` dans le dépôt, ou `~/.config/rofi/nixpick*.rasi` (installés par `install.sh`).

## Comportement

- Index : `nix-env -qaP --json` → cache `~/.cache/nixpick/` (rebuild auto ~7 jours)
- Descriptions : `nix eval` à la demande pour les résultats affichés
- Rebuild **uniquement** si tu confirmes (`nixpick rebuild`, ou « Lancer le rebuild » en Rofi, ou `o` après un ajout CLI)
- Si nixpick est un **input path** dans ton flake NixOS : après chaque changement du dépôt nixpick, mets à jour le lock avant rebuild : `cd /etc/nixos && nix flake lock --update-input nixpick` (`nixpick doctor` signale un hash périmé)
- Variable optionnelle `NIXPICK_REBUILD_TERMINAL` (défaut : premier parmi kitty, foot, alacritty, wezterm)
- Sauvegarde horodatée `packages.nix.bak.YYYYMMDD-HHMMSS` avant écriture ; métadonnées dans `~/.cache/nixpick/last-op.json` pour `nixpick --undo`

## Hyprland / Waybar (exemple)

```json
"custom/nixpick": {
  "format": "󰏗",
  "on-click": "nixpick --rofi"
}
```

## Limites

- Ne détecte pas les paquets activés via des **options** (`programs.firefox.enable`, etc.)
- Un seul bloc `environment.systemPackages` par fichier (configurable via `packages_anchor`)
- Pas de prise en charge Home Manager pour l’instant

## Licence

MIT — voir [LICENSE](LICENSE).

## Contribuer

Issues et PR bienvenues. Garde le scope : recherche rapide + édition sûre d’un fichier Nix déclaratif.
