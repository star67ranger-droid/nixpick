# nixpick

Recherche dans **nixpkgs** et ajout / retrait de paquets dans ton fichier NixOS `environment.systemPackages` — sans ouvrir l’éditeur à la main.

Conçu pour une config **modulaire** (`modules/packages.nix`), pas pour tout mettre dans `configuration.nix`.

**Projet vibecodé** : idée et usage réel (ma config NixOS / Hyprland) par Pikeo ; le code a été itéré avec des assistants IA (Cursor), puis durci (écritures atomiques, validation des attrs, audits). Les PR et retours sont les bienvenus — l’objectif est un petit outil utile et lisible, pas une usine à gaz.

## Démarrage rapide

```bash
nixpick              # TUI : taper un nom, Entrée pour ajouter
nixpick rebuild      # NixOS : applique via nixos-rebuild (confirmation)
nixpick sync         # hors NixOS : installe les listés dans le profil Nix
```

## Prérequis

- **NixOS**, ou toute machine avec **Nix + flakes** (`nix-command`, `flakes`)
- Python **3.12+**
- Pour l’index : `nix-env` + un **channel nixpkgs** (`nix-channel --add https://nixos.org/channels/nixos-unstable nixpkgs && nix-channel --update`) — sans channel, l’index est vide
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
.venv/bin/pip install -e '.[dev]'
chmod +x bin/nixpick
ln -sf "$(pwd)/bin/nixpick" ~/.local/bin/nixpick
mkdir -p ~/.config/nixpick
cp config.example.toml ~/.config/nixpick/config.toml
```

### pip (éditable)

```bash
pip install -e .
```

### Flake NixOS (input Git)

```nix
inputs.nixpick.url = "github:star67ranger-droid/nixpick";
# …
environment.systemPackages = [ pkgs.nixpick ];
```

Après mise à jour du dépôt : `nix flake lock --update-input nixpick` puis rebuild.

### Direct via Nix (sans cloner, toute distro avec Nix + flakes)

```bash
nix run github:star67ranger-droid/nixpick -- --help
nix profile install github:star67ranger-droid/nixpick  # commande `nixpick` en direct
```

Testé depuis zéro sur Ubuntu + Nix Determinate (VM) : construction,
TUI, index, sync.

## Configuration

Fichier : `~/.config/nixpick/config.toml`

```toml
packages_file = "/etc/nixos/modules/packages.nix"
packages_anchor = "environment.systemPackages"
rebuild_command = ["sudo", "nixos-rebuild", "switch", "--flake", "/etc/nixos#nixos"]
transparent_background = false
```

**Couleurs (TUI + Rofi)** : section `[colors]` et `[colors.rofi]` dans le même fichier. Guide complet : [docs/THEMES.md](docs/THEMES.md). Modèle : [`config.example.toml`](config.example.toml).

Variables d’environnement (prioritaires) :

| Variable | Rôle |
|----------|------|
| `NIXPICK_PACKAGES_FILE` | Fichier `.nix` à modifier |
| `NIXPICK_PACKAGES_ANCHOR` | Ligne d’ancrage (défaut `environment.systemPackages`) |
| `NIXPICK_REBUILD_COMMAND` | Tableau TOML ou chaîne shell (`shlex`), p. ex. `["sudo", "nixos-rebuild", "switch"]` — jamais de JSON, aucun shell |
| `NIXPICK_REBUILD_TERMINAL` | Émulateur pour `rebuild --terminal` (vérifié dans le PATH, sinon repli auto : kitty, foot, alacritty, wezterm) |
| `NIXPICK_LANGUAGE` | `fr` (défaut) ou `en` — prioritaire sur `language` du config ; changeable en direct via Ctrl+L |

Vérifier :

```bash
nixpick --print-config
```

## Commandes

| Commande | Description |
|----------|-------------|
| `nixpick` | **TUI** OpenTUI (recherche live, détail, ajout / retrait) |
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
| `nixpick fix-git` | `git add` des fichiers non suivis (??) du dépôt flake (confirmation) |
| `nixpick fix-git -y` | Idem sans redemander |
| `nixpick rebuild` | Lance `rebuild_command` (confirmation interactive) |
| `nixpick rebuild -y` | Rebuild sans redemander (scripts) |
| `nixpick rebuild -y --terminal` | Ouvre **kitty** / **foot** pour `sudo` et la sortie |
| `nixpick sync` | Hors NixOS : installe dans le profil les paquets listés mais absents (jamais de retrait) |
| `nixpick sync -y` | Idem sans redemander · `--dry-run` affiche la commande · `--upgrade` met aussi à jour les listés déjà installés |
| `nixpick doctor` | Fichier packages, cache index, verrou, **Git flake (fichiers suivis)**, flake.lock nixpick, outils, rebuild |
| `nixpick doctor --json` | Même diagnostic en JSON |
| `nixpick --why <attr>` | Indique si l’attribut est dans le fichier configuré (ligne approximative) |
| `nixpick --print-config` | Affiche fichier cible, ancre et rebuild puis quitte |
| `nixpick --tui` | Force la TUI même avec un terme de recherche |
| `nixpick --transparent` / `--opaque` | Fond TUI (ANSI / Kitty) |

### Complétion shell

Fichiers dans `assets/completions/` (bash, zsh, fish) — synchro avec le CLI
testée (`tests/test_completions.py`).

```bash
# bash (~/.bashrc)
source /chemin/nixpick/assets/completions/nixpick.bash
# zsh (dossier dans $fpath, fichier nommé _nixpick)
cp assets/completions/_nixpick ~/.local/share/zsh/site-functions/
# fish
cp assets/completions/nixpick.fish ~/.config/fish/completions/
```

Via le flake Nix, les complétions sont installées automatiquement
(`installShellCompletion`).

### TUI — raccourcis

Style **fuzzy-finder** : recherche centrée en haut, liste à gauche (`▸` sélection,
`●` déjà installé, version alignée à droite), panneau **détail** à droite,
suggestions au repos, footer en bas.

- **Taper** : recherche live (min. 2 caractères)
- **↑ ↓** (ou **Ctrl+N** / **Ctrl+P**) : naviguer sans quitter la recherche
- **PageUp** / **PageDown** : d’un écran de résultats
- **↵** : ajouter · **Ctrl+X** : retirer (si déjà dans la config)
- **Espace** : panier multi-sélection (`+`) · **↵** avec panier non vide : tout ajouter d'un coup
- **y** (focus liste) : copie l'attribut dans le presse-papiers (wl-copy/xclip/xsel)
- **Ctrl+I** : masquer les paquets installés · **Ctrl+D** : simulation
- **Tab** : basculer recherche / liste (puis `x l i d t q` au focus liste) · **Esc** : vider la recherche, puis quitter
- **Ctrl+R** : reconstruire l’index · **?** / **F1** : aide
- **Ctrl+L** : paramètres (langue FR/EN en direct, fond transparent, fichier packages — sauvegardés dans `config.toml`)

Les entrées déjà présentes dans `systemPackages` sont marquées **●**.

### Rofi

1. Saisir un terme (ex. `cursor`) → **Entrée**
2. Choisir dans la liste · **✓** = déjà dans `systemPackages` (retrait proposé) · sans ✓ = ajout
3. Aperçu **read-only** du diff (`+` / `-` autour de la ligne concernée), puis **Confirmer l'ajout** / **Confirmer le retrait** ou **Annuler** (sans notification)

Après validation : notification, puis menu **« Corriger Git (fix-git) »** (si des `??` bloquent le flake), **« Lancer le rebuild »** / **« Plus tard »**. Le rebuild s’ouvre dans un terminal (kitty, foot, …) si tu acceptes. Sinon : `nixpick rebuild`.

Thèmes : `assets/rofi/` dans le dépôt ; nixpick régénère `~/.config/nixpick/rofi/*.rasi` à chaque lancement (les copies de `~/.config/rofi/` ne servent qu'en secours — voir [docs/THEMES.md](docs/THEMES.md)).

## Hors NixOS (Ubuntu, etc. — Nix + flakes requis)

Pas de `/etc/nixos` ? nixpick bascule tout seul :

1. **Cible locale** : `~/.config/nixpick/packages.nix`, créée (squelette) au premier ajout — jamais d’erreur « introuvable ». `NIXPICK_PACKAGES_FILE` reste prioritaire.
2. **Recherche** : identique (index `nix-env`, descriptions `nix eval`). Prérequis : un channel nixpkgs (voir Prérequis).
3. **Appliquer** : `nixpick sync` installe dans ton profil les listés absents (`nix profile install nixpkgs#…`, jamais de retrait). Proposé après chaque ajout CLI, suggéré en TUI/Rofi.
4. **Limites** : pas de `rebuild` (pas de `nixos-rebuild`), install **par utilisateur**, `doctor` signale `/etc/nixos` absent — c’est attendu.

```bash
nixpick                    # ajouter btop → ~/.config/nixpick/packages.nix
nixpick sync               # nix profile install nixpkgs#btop (confirmation)
nixpick sync --dry-run     # voir la commande sans l’exécuter
```

## Comportement

- Index : `nix-env -qaP --json` → cache `~/.cache/nixpick/` (rebuild auto ~7 jours). Prérequis : `nix-env` dans le PATH + channel nixpkgs (`nixpick doctor`).
- Descriptions : `nix eval` à la demande pour les résultats affichés
- Rebuild **uniquement** si tu confirmes (`nixpick rebuild`, ou « Lancer le rebuild » en Rofi, ou `o` après un ajout CLI)
- **Fichiers non suivis par Git** dans `/etc/nixos` : le flake ne voit pas les nouveaux chemins (`dotfiles/…`) tant qu’ils ne sont pas `git add`. `nixpick doctor` liste les `??` et propose la commande ; `nixpick rebuild` refuse de lancer `sudo` tant que c’est le cas (Rofi affiche un rappel).
- Si nixpick est un **input path** dans ton flake NixOS : après chaque changement du dépôt nixpick, mets à jour le lock avant rebuild : `cd /etc/nixos && nix flake lock --update-input nixpick` (`nixpick doctor` signale un hash périmé)
- Sauvegarde horodatée `packages.nix.bak.YYYYMMDD-HHMMSS` avant écriture ; métadonnées dans `~/.cache/nixpick/last-op.json` pour `nixpick --undo`

## Dépannage

- **Recherche vide (« aucun résultat »)** : index vide = souvent pas de channel nixpkgs. Vérifier : `python3 -c "import json; print(len(json.load(open('$HOME/.cache/nixpick/index.json'))))"` → si `0`, `nix-channel --add https://nixos.org/channels/nixos-unstable nixpkgs && nix-channel --update`, puis **Ctrl+R** dans la TUI.
- **« index indisponible » après reconstruction** : lancer `nixpick --build-index-only` pour voir l’erreur. Cause fréquente : machine trop petite — évaluer nixpkgs-unstable demande plusieurs Go de RAM (2 Go → OOM-kill, `died with SIGKILL`).
- **Rebuild refusé (« not tracked by Git »)** : `nixpick fix-git` (ou `fix-git -y`), puis rebuild.
- **`flake.lock` périmé** (nixpick en input path) : `cd /etc/nixos && nix flake lock --update-input nixpick` — `nixpick doctor` le signale.
- **TUI minuscule / overlay « 40×12 requis »** : agrandir le terminal, pas de contournement.
- **Crash avec traceback** : copier la sortie dans une issue — https://github.com/star67ranger-droid/nixpick/issues.

## Hyprland / Waybar (exemple)

```json
"custom/nixpick": {
  "format": "󰏗",
  "on-click": "nixpick --rofi"
}
```

## Limites

- Ne détecte pas les paquets activés via des **options** (`programs.firefox.enable`, etc.)
- Un seul bloc `environment.systemPackages` par fichier, forme **`anchor = with pkgs; [ … ];`** (configurable via `packages_anchor`). Pas de `++`, listes imbriquées hors paquets simples, ni plusieurs blocs.
- Après chaque écriture, validation optionnelle via `nix-instantiate --parse` (restaure la sauvegarde si le fichier est invalide).
- `rebuild_command` est une **liste d’arguments** (TOML tableau ou chaîne parsée par `shlex`) — pas d’évaluation shell sauf le terminal interactif du rebuild.
- Pas de prise en charge Home Manager pour l’instant

## Projets proches

- [nixmate](https://github.com/daskladas/nixmate) (Rust) : couteau suisse TUI NixOS-only — générations, services, rebuild, doctor… Complémentaire : nixpick se concentre sur recherche + édition d’un fichier, et fonctionne avec Nix seul (voir `nixpick sync`).
- [ns-tui](https://github.com/briheet/ns-tui) : recherche floue de paquets en TUI.
- À ne pas confondre avec `duskoide/nixpick` (Rust, homonyme sans rapport).

## Licence

MIT — voir [LICENSE](LICENSE).

## Contribuer

Issues et PR bienvenues : https://github.com/star67ranger-droid/nixpick/issues. Garde le scope : recherche rapide + édition sûre d’un fichier Nix déclaratif.
