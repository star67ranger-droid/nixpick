# Handoff Cursor ↔ Antigravity

**Dernière mise à jour :** Cursor, 2026-09-23 — **journée clôturée** (v0.3.5.1).

## Livré aujourd’hui

- **v0.3.4** : `fix-git`, preflight flake Git, Rofi « Corriger Git ».
- **v0.3.5** : audit (CI git, `nix flake check`, Dependabot, packaging `share/nixpick`, fix-git ciblé flake).
- **v0.3.5.1** : `asset_path` sous paquet Nix.
- **CI** : verte (pytest 56 + flake). **Releases** : v0.3.5 sur GitHub ; tag **v0.3.5.1** à pousser avec ce commit.
- **Dependabot** : 3 PR Actions ouvertes (non mergées — à valider toi si tu veux).

## Prochaine session (Pikeo, machine réelle)

1. `pip install -e .` ou lock flake : `cd /etc/nixos && nix flake lock --update-input nixpick`
2. `nixpick doctor` · `SUPER+N` (fix-git + rebuild si besoin)
3. `git commit` dans `/etc/nixos` si des fichiers étaient en `??`

## Pas de travail agent ouvert

- Pas de feature v0.4 engagée (options `programs.*` = idée plus tard).
- Arbitrage scope / `sudo` rebuild : Pikeo seulement.
