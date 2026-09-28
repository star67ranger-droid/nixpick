# Changelog

## 0.4.0 — non publié

- **TUI** : migration de Textual vers **OpenTUI** (rendu direct, `tui_css.py` supprimé, `native_env` pour libstdc++ sur NixOS)
- **TUI** : interface refondue en **fuzzy-finder centré** (style telescope / fzf) :
  recherche centrée à bordure active, hint d'état centré, liste sans bordure avec
  colonnes `▸` sélection / `●` installé / nom / version alignée à droite,
  panneau ` détail ` à droite, suggestions dim au repos, footer centré ;
  nouvelles touches **ctrl+n / ctrl+p** (depuis la recherche) et **pageup / pagedown**
- **Palette par défaut sobre** : neutres zinc + **un seul accent bleu**
  (`primary` / `accent` / `accent_alt`) ; vert, rouge et ambre réservés aux états
  (`●` installé, erreur, simulation) ; titres de panneau en gris, ligne
  sélectionnée sur un fond surélevé discret
- **Correctifs rendu** : la racine remplit la hauteur du terminal (`height="100%"`),
  `Input` centré verticalement, largeurs liste/détail calculées par une source unique,
  lignes sans repli (`wrap_mode="none"`) pour que l'aide et le corps du détail ne
  débordent plus sur les bordures
- **CI** : pytest 3.12 + 3.13 (wheels OpenTUI cp312/cp313 uniquement) ; `flake.nix` embarque `opentui` + `yoga-python` (wheels PyPI) ; `nix flake check` vert (100 tests) ; job **lint** `ruff check .` (baseline `[tool.ruff]` explicite, 17 règles)
- **Audit** : 11 correctifs UX / sécurité / qualité (rapport : `docs/AUDIT-REPORT.md`)
- **Audit n°2** : 30 constats — P0/P1 corrigés :
  - **TUI** : échec d'index ne fige plus l'interface (catch large + message `Ctrl+R`), hint honnête « index indisponible »
  - **TUI** : footer/README n'annoncent plus `x` / `l` / `q` inaccessibles au focus recherche (`^X` `^L` `esc`)
  - **TUI** : plan liste/détail toujours contenu dans la largeur ; aide tronquée avec indicateur sur terminal court ; message explicite sous 40×12 ; collage du presse-papiers (`ctrl+shift+V`) ; indice du panneau détail elliptique ; branche `ctrl+c` morte retirée
  - **CLI** : `--remove` sans terme → code 2 (plus de TUI silencieuse) ; `--rofi` sans rofi → code 1
  - **engine** : verrou d'édition déplacé hors du dépôt flake (`~/.cache`, repli `/tmp`) ; crochets dans les chaînes ne cassent plus la localisation du bloc ; `AddOutcome.INVALID_ATTR` ; restauration annoncée honnête et atomique ; descriptions Rofi chargées après le choix (plus de `nix eval` bloquant) ; cache descriptions sous verrou ; encodage UTF-8 explicite ; purge des sauvegardes `.bak.*` (5 conservées) ; recherche par **sous-séquence** (vrai match fzf) ; imports morts retirés
  - **fix-git -y** : inventaire des fichiers toujours affiché ; thème Rofi manuel documenté comme injoignable ; `comment` = couleur du placeholder rofi
- **Perf** : sous-séquence fzf en regex compilée par requête (`lru_cache`, `re.escape`) + préfiltre première lettre — repli scan complet sur 100k lignes : ~90 → ~33 ms, moteur C hors GIL ; test anti-interprétation regex (« a.c » ≠ « abc »)
- **Tests** : smoke tests TUI (`tests/test_tui.py`, rendu + navigation + modales + fuzzy-finder)

## 0.3.6 — 2026-09-25

- **Nix** : `git` dans le sandbox de `doCheck` (tests flake_git / fix_git)
- **Sécurité / robustesse** : `rebuild_command` en argv (shlex) ; validation `nix-instantiate --parse` après écriture ; caches JSON atomiques ; verrou construction index
- **Parseur** : bloc unique `anchor = with pkgs; [ … ];` ; erreurs explicites si forme non supportée
- **Git flake** : ignore les sauvegardes `packages.nix.bak.*` ; TUI gère `LookupError` / `NixSyntaxError`
- **CI** : pytest 3.11 + 3.12 ; `flake check` avec tests package + smoke `nixpick --help`
- **Nettoyage** : code mort retiré ; `requirements.txt` déjà absent — install via `pip install -e .`

## 0.3.5 — 2026-09-23

- **CI** : identité git pour les tests ; job `nix flake check` ; Dependabot actions + pip
- **fix-git** : `git add --`, lots ; chemins limités au répertoire flake ; erreurs git explicites
- **Packaging** : assets Rofi et `config.example.toml` dans `share/nixpick/`
- **UX** : repli stderr si pas de `notify-send` ; CLI rebuild + preflight fix-git ; doctor rebuild vide
- **Défaut** : `rebuild_command` avec `--flake /etc/nixos#nixos`

## 0.3.5.1 — 2026-09-23

- **Packaging Nix** : `asset_path()` trouve `share/nixpick` dans le store (pas seulement `sys.prefix`)
- **CI** : PR Dependabot ouvertes (checkout / setup-python / nix-installer) — à merger quand tu veux

## 0.3.4 — 2026-09-23

- **`nixpick fix-git`** : exécute `git add` sur les fichiers `??` du dépôt flake (après confirmation)
- Packaging : module `fix_git_runner` ; tests Antigravity sur `rebuild_preflight_notify_body`

## 0.3.3 — 2026-09-23

- **flake_git** : détecte les fichiers non suivis (`??`) dans le dépôt du flake NixOS
- **doctor** : check « Git flake (fichiers suivis) » + commande `git add` suggérée
- **rebuild** : préflight avant confirmation ; aide rebuild enrichie
- **Rofi** : notification + aperçu si le rebuild est bloqué par Git

## 0.1.0 — 2026-09-20

Première release publique (projet vibecodé, durci avant publication).

- TUI Textual : recherche live, ajout / retrait, catalogue des paquets listés
- CLI interactif et `--remove`
- Mode Rofi (2 étapes) + thèmes `assets/rofi/`
- Config `~/.config/nixpick/config.toml` et variables `NIXPICK_*`
- Index nixpkgs en cache, descriptions à la demande
- Écriture atomique, verrou fichier, validation des noms d’attribut
- `flake.nix`, tests pytest, CI GitHub Actions
