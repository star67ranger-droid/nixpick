# Changelog

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
