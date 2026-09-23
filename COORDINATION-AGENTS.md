# Coordination Cursor ↔ Antigravity (nixpick)

Dernière mise à jour : 2026-09-23 (Cursor).

## Rôle du dépôt

**nixpick** : recherche nixpkgs + ajout/retrait dans `environment.systemPackages` (fichier modulaire, ex. `/etc/nixos/modules/packages.nix`), rebuild guidé, Rofi (`SUPER+N`), `doctor`, thèmes TOML.

- Repo : `~/Projets/nixpick` — GitHub `star67ranger-droid/nixpick`
- Install système : flake input dans `/etc/nixos`, binaire `nixpick` / `nixpick-rofi`
- Tests : `pytest` dans le venv du projet

## État récent (contexte Pikeo)

- **v0.3.x** : `nixpick rebuild` (confirmation `o`, aide flake « not tracked by Git »), `flake_lock` doctor, thèmes.
- Friction récurrente : fichiers **non suivis par Git** dans `/etc/nixos` → `git -C /etc/nixos add …` avant rebuild.
- Pikeo préfère **français**, pas de commits/push sans demande explicite côté assistants.

## Découpage de travail suggéré

| Zone | Qui | Notes |
|------|-----|--------|
| Python (engine, TUI, rofi, doctor, tests) | Antigravity ou Cursor | Une branche / une PR à la fois |
| Nix (flake, module NixOS, packaging) | Vérifier les deux | Rebuild local obligatoire |
| UX / copy FR (`messages.py`) | Pikeo valide le ton | |
| Docs README / THEMES | soit l’un soit l’autre | Éviter doublons |

## Quand Pikeo doit être là

1. **`sudo nixos-rebuild switch`** et mot de passe.
2. **Choix produit** : nouvelle feature vs polish, scope v0.4.
3. **Conflits Git** sur `/etc/nixos` ou décision de commit/push.
4. **OAuth / API** Antigravity ou clés (jamais dans le repo).
5. **Validation Rofi/Hyprland** sur sa machine (bind `SUPER+N`).

Sinon : enchaîner issues/PR, pytest vert, proposer le diff.

## CLI Antigravity sur cette machine

Le paquet Nix s’appelle `antigravity-cli` ; la commande est **`agy`** (pas `antigravity-cli`).

```bash
cd ~/Projets/nixpick
agy -i --add-dir .    # session interactive
agy -p "…" --add-dir .   # une réponse non interactive
```

## Fait (2026-09-23, Cursor)

- `flake_git.py` : détection `git status ??` sur le dépôt du flake, commande `git add` prête à copier.
- `nixpick doctor` : check « Git flake (fichiers suivis) ».
- `nixpick rebuild` : préflight avant confirmation / sudo (v0.3.3).

## Pistes suivantes

- Module NixOS optionnel dans le flake nixpick.
- `nix flake update` nixpick input depuis le doctor si lock périmé (déjà partiel).

---

*Fichier pour aligner les agents ; Pikeo peut ignorer ou supprimer.*
