# Rapport d'audit #3 — nixpick 0.4.0 + travail non committé

## 1. Résumé exécutif

Troisième audit (agent `nixpick-audit`, lecture seule), ciblé sur le code nouveau
depuis l'audit #2 (`sync_runner`, repli non-NixOS, garde-fou `main()`, complétions,
workflow release) et la dette restante (rofi 26 %, rebuild 45 %, config 52 %).

**Findings : 33 au total — 1 P1, 8 P2, 24 P3. Zéro P0.**

Point le plus grave : **QUA-01 (P1)** — `rebuild --terminal` et tout rebuild Rofi
sont cassés chez les utilisateurs kitty (`kitty` n'a pas d'option `-e`).

À noter : l'audit invalide deux de mes décisions récentes (UX-04 : message
« Pour appliquer : rebuild » resté en dur hors NixOS ; UX-06 : parcours retrait
sans branche sync) et révèle un invariant que j'avais manqué (UX-09 :
ensembles de confirmation incohérents).

## 2. Méthode

- Agent d'audit en lecture seule sur le working tree ; vérifications par
  exécution locale (`pytest`, `ruff`, `mypy`, `kitty --help`).
- Non vérifié : rendu Rofi/X11 réel, `kitty -e` en exécution, `-e` de
  foot/alacritty/wezterm, chemins OOM/canal absent, `nix hash path` chronométré,
  workflow release et install.sh exécutés.
- Les IDs `UX-nn`/`QUA-nn`/… sont ceux de l'audit #3 (collisions possibles
  avec les rapports #1/#2).

## 3. Synthèse

| Priorité | Nbre | IDs |
|----------|------|-----|
| P1 | 1 | QUA-01 (kitty `-e`) |
| P2 | 8 | UX-01 (README JSON), UX-02 (build-index-only), UX-03 (message NixOS), UX-04 (message rebuild hors NixOS), UX-05 (URL issues sur pannes routinières), UX-06 (retrait sans sync), UX-07 (doctor rouge/vert inversés hors NixOS), QUA-02 (release sans garde-fous) |
| P3 | 24 | UX-08…UX-18, UI-01, SEC-01, QUA-03…QUA-07, TST-01…TST-03, PERF-01…PERF-03 |

## 4. Décisions de triage

| Finding | Statut | Motif |
|---------|--------|-------|
| QUA-01, UX-01…UX-07, QUA-02 | ✅ accepté | — |
| UX-08…UX-18, UI-01, SEC-01, QUA-03…QUA-07 | ✅ accepté | — |
| TST-01 | ✅ accepté | plancher remonté après mesure |
| TST-02 | ✅ accepté partiel | `config.py`/`theme.py` explicites (gratuits) ; CLI/Rofi selon le nombre d'erreurs mesuré |
| TST-03 | ✅ accepté partiel | `S` + `C901` avec triage ; **`EM` décliné** : `EM101/EM102` interdisent les f-strings dans les `raise`, style utilisé partout (`raise NixCommandError(f"…")`) — documenté, pas appliqué |
| PERF-01 | ✅ accepté | génération/annulation comme la recherche |
| PERF-02 | ⚠️ mesurer d'abord | `nix hash path` non chronométré par l'audit ; si < quelques secondes, aucun changement |
| PERF-03 | ❌ décliné (mesuré) | walk complet = **21 ms** avec .git à 2,7 Mo/360 objets : pas un problème. Le prune proposé raterait les écritures profondes (mtime du top-dir inchangé par les writes nested) → fausses alertes « lock périmé ». |
| PERF-03 | ✅ accepté | ne pas descendre dans `_VOLATILE_TOP` |
| UX-14 | ✅ accepté (doc) | toast TUI passif par construction : uniformiser le libellé + documenter le choix, pas de modal |
| QUA-01 (périmètre) | ✅ accepté partiel | fix **vérifié** pour kitty uniquement ; foot/alacritty/wezterm inchangés (non vérifiables ici) + commentaire |

## 5. To-do d'exécution (ordre)

1. **P1** : QUA-01 (argv par terminal, kitty sans `-e`).
2. **P2** : UX-01 (README env), UX-02 (try autour de build-index-only),
   UX-03 (message install Nix), UX-04+QUA-07 (messages `is_nixos()` + dédup),
   UX-05 (URL seulement si inattendu), UX-06 (hint `nix profile remove`
   après retrait hors NixOS — pas de sync, qui serait no-op sans prune),
   UX-07 (doctor honnête hors NixOS — voir §6),
   QUA-02 (`needs`, glob `v[0-9]*`, « notes seules » documenté).
3. **P3 par fichier** : cli (UX-08 code install, UX-09 prédicat partagé),
   config (UX-10 TOML, QUA-03 validation), rofi (UX-11 labels, UX-15 notif
   sync), tui (UX-12 garde touches, UX-13 aide focus, UI-01 sanitize),
   sync (UX-16 stderr), rebuild (UX-18 which), README (UX-17 env table),
   install.sh (QUA-04 `cp -n` + complétions), example (QUA-05 table
   `[nixpick]`), imports (QUA-06 après vérif cycles), SEC-01 (atomique),
   TST-01/02/03, PERF-01/03 (+02 si mesuré lent).
4. Vérifications : `pytest` (inexistant → 0 fail), `ruff`, `mypy`,
   `nix flake check`, revue du diff. Pas de commit/push sans demande.

## 6. Point d'arbitrage ouvert

**UX-07 — sémantique exit code de `doctor` hors NixOS.** Aujourd'hui :
fichier absent → `ok=False` (exit 1 sur install fraîche saine) pendant que
le check rebuild reste OK (alors que le rebuild est impossible). Proposition :
fichier absent hors NixOS → `ok=True` + détail « sera créé au premier ajout »,
et check rebuild → mention « sans objet hors NixOS ». À confirmer : ça change
le code de sortie de `doctor` (consommé par le préflight rebuild ? — vérifié
pendant l'exécution).

## 7. Suivi d'exécution

Arbitrage UX-07 tranché : **doctor honnête** (vérifié : son exit code n'est
consommé par rien d'autre). Tous les findings acceptés sont corrigés et
vérifiés (`pytest`, `ruff`, `mypy`, `nix flake check` verts) :

- QUA-06 (imports top-level) a cassé 12 tests qui patchaient les modules
  sources : corrigés en patchant là où c'est résolu (règle appliquée partout).
- PERF-02 mesuré : `nix hash path` = 0,47 s → aucun changement.
- TST-01 : plancher remonté 70 → 72 (mesuré 73).
- TST-02 : périmètre étendu à 14 modules (`--follow-imports=skip`, tui exclu :
  13 erreurs stubs opentui hors sujet) ; au passage, 2 vrais bugs corrigés
  (`err` réassigné hors `except` dans flake_git, `out: object` dans doctor).
- TST-03 : `S` (+ignores documentés S603/S607, S101/S108 en tests) et `C901`
  ratchet à 25 ; `EM` décliné (conflit avec les `raise f"…"` partout).
- PERF-01 : garde anti-pile-up + génération (tuer le `nix-env` orphelin
  demanderait du plumbing Popen — limitation documentée).
