# Rapport d'audit #2 — nixpick 0.4.0 (en cours)

## 1. Résumé exécutif

Second audit du working tree **après** la migration Textual → OpenTUI et la refonte
fuzzy-finder (rapport n°1 : `docs/AUDIT-REPORT.md`). Le moteur reste sain, mais la
refonte a laissé des **contrats cassés entre le code et la documentation**, et plusieurs
défauts de robustesse préexistants n'avaient jamais été corrigés.

**Findings : 32 au total — 5 P0, 16 P1, 11 P2/P3.**

*(Note : l'agent d'audit annonçait « 30 constats » ; le détail en liste 32.
Le décompte des sections détaillées fait foi — même cas que le rapport n°1.)*

Trois risques principaux :

1. **UX-01/UX-02 (P0)** — un échec d'index autre qu'une `NixCommandError` tuait le worker
   en silence : `loading` restait bloqué à `True`, aucun message, TUI gelée sur l'écran de
   chargement. Même cas nominal, la lambda capturait `err` effacé en fin de bloc `except`
   (fin de vie de la variable en Python 3) → `NameError` différé.
2. **UX-03 (P1)** — le footer et le README annonçaient `x` / `l` / `q` alors qu'au focus
   recherche (l'état par défaut) ces touches sont avalées par le champ de saisie.
   Identique au constat UX-01 du rapport n°1 : la documentation décrit un produit qui ne
   se comporte pas comme prévu.
3. **QUA-05 (P1)** — le verrou `.packages.nix.nixpick.lock` était créé **dans le dépôt
   flake**, jamais supprimé, et visible dans `git status`.

**Verdict : 32 correctifs appliqués et vérifiés (100 tests, `nix flake check` vert,
`ruff check` propre, passe perf mesurée) ; plus aucun item ouvert.**

## 2. Périmètre et méthodologie

- **Date :** 28/09/2026. **Base :** working tree non committé, HEAD `a480b25`.
- **Agents :** `nixpick-audit` (lecture seule) → findings bruts, puis application manuelle.
- **Vérification :** `pytest` (100 tests, 7,4 s) ; `nix flake check` (98 tests dans le
  sandbox — les 2 fichiers ajoutés après n'avaient pas été `git add`és, corrigé) ;
  smoke TUI headless via `opentui.testing.test_render` (100×30, 90×14, 40×30, 30×8).
- **Convention d'identifiants :** `UX-nn` / `UI-nn` / `QUA-nn` / `TST-nn` / `PERF-nn`
  proviennent de l'audit n°2 et **peuvent entrer en collision** avec ceux du rapport n°1.
- **Non audité :** rendu Rofi/X11 réel, performances mesurées, couverture de tests.

## 3. Synthèse

| Priorité | UX  | UI  | Qualité | Tests | Perf | Total |
|----------|-----|-----|---------|-------|------|-------|
| P0       | 2   | 0   | 3       | 0     | 0    | 5     |
| P1       | 8   | 3   | 4       | 1     | 0    | 16    |
| P2/P3    | 2   | 1   | 4       | 1     | 3    | 11    |
| **Total**| **12** | **4** | **11** | **2** | **3** | **32** |

## 4. Findings P0

#### [UX-01] TUI gelée après un échec d'index — P0

- **Fichier :** `tui.py:408` (`load_index_worker`)
- **Problème :** seul `NixCommandError` était attrapé. Un `json.JSONDecodeError`
  (index corrompu), une `OSError` (cache illisible) ou toute autre exception sortait du
  thread sans état : `loading` reste `True`, `_on_index_error` jamais appelé, aucun toast.
- **Correction :** `except Exception as err` + `_index_error_message(err)`
  (`tui.py:144`) qui distingue `JSONDecodeError` / `OSError` / `NixCommandError`.
  Le message est figé **avant** le `post()` — `err` est effacé en fin de bloc `except`.
- **Statut :** ✅ corrigé — test `test_index_en_echec_ne_bloque_pas_la_tui`.

#### [UX-02] Lambda capturant une variable `except` effacée — P0

- **Fichier :** `tui.py:408` (même fonction)
- **Problème :** `self.post(lambda: self._on_index_error(str(err)))` — `err` n'existe
  plus quand la frame suivante exécute la lambda → `NameError` dans `tick()`, avalé par
  `_run_safely` qui ne fait que stocker `last_error` : échec totalement invisible.
- **Correction :** `message = _index_error_message(err)` puis `lambda: self._on_index_error(message)`.
- **Statut :** ✅ corrigé.

#### [QUA-05] Verrou d'édition jamais retiré, posé dans le dépôt flake — P0

- **Fichier :** `engine.py:537` (`packages_lock_path`), `engine.py:516` (`_edit_lock_dir`)
- **Problème :** le lock vivait à `path.parent / ".{name}.nixpick.lock"`, c'est-à-dire
  **au cœur du dépôt NixOS**, jamais supprimé, visible dans `git status ??`.
- **Correction :** le verrou va dans `~/.cache/nixpick/edit-<sha1 du chemin>.lock`,
  avec repli `$TMPDIR/nixpick-<uid>` si le cache est inaccessible (bac à sable Nix,
  HOME en lecture seule) — sinon toute édition devenait impossible.
  `doctor.packages_lock_path()` importe désormais la fonction d'`engine` (source unique).
- **Statut :** ✅ corrigé — `test_doctor_active_lock` vert dans les deux environnements.

#### [QUA-02] Restauration annoncée alors qu'elle avait échoué — P0

- **Fichier :** `engine.py:718` (`_ensure_valid_packages_file`)
- **Problème :** `shutil.copy2(backup, path)` dans un `except OSError: pass`, puis
  message « (restauré depuis la sauvegarde) » **systématique** → l'utilisateur croit
  son fichier rétabli alors qu'il est resté invalide.
- **Correction :** écriture atomique `_atomic_write_text` (plus de copie partielle),
  état honnête `restauré` / `NON restauré` + raison.
- **Statut :** ✅ corrigé — `test_commit_restores_backup_on_invalid_nix`.

#### [QUA-12] Lecture de fichiers sans encodage explicite — P0

- **Fichier :** `engine.py` (index, meta, cache descriptions, `packages.nix` ×3),
  `config.py`, `doctor.py`
- **Problème :** `Path.read_text()` sans `encoding=` dépend de la locale : sur un
  système à locale `C`, une description UTF-8 ou un nom de paquet accentué lève
  `UnicodeDecodeError` (non catché dans plusieurs chemins).
- **Correction :** `encoding="utf-8"` sur les 9 appels concernés.
- **Statut :** ✅ corrigé.

## 5. Findings P1

| ID | Fichier:ligne | Constat | Correction | Statut |
|----|---------------|---------|------------|--------|
| UX-05 | `tui.py:992` `hint_region` | Après échec d'index, la hint disait « aucun résultat pour « x » » : l'utilisateur croyait à une faute de frappe | Branche `index_failed()` avant le test de résultats → « index indisponible — Ctrl+R » | ✅ |
| UX-03 | `tui.py:94` `_FOOTER_KEYS`, `README.md` | Footer/README annonçaient `x`/`l`/`q`, inertes au focus recherche (défaut) | Notation `^X` `^L` `^I` `^D` `^T` `^R` + `esc quitter` ; README § TUI aligné ; `essential={"?","esc"}` | ✅ |
| UI-01 | `tui.py:194` `_split_widths` | `listing + detail` dépassait `width-2` (42 > 38 à 40 px) : le rendu débordait sous le bord droit | Bornes recalculées sur `available = width-2`, somme toujours exacte | ✅ |
| UI-02 | `tui.py:1247` `_help_box` | Sous 24 lignes visibles, la dernière ligne de l'aide se posait sur la bordure / disparaissait | Troncature propre + marqueur `… +N lignes (README § TUI — raccourcis)` | ✅ |
| UX-07 | `tui.py:1191` `too_small_region` | Terminal < 40×12 : plan fixe (8 lignes) compressé, liste invisible, aucune explication | Overlay `z_index=40` « terminal 30×8 : 40×12 requis — agrandir » | ✅ |
| UX-06 | `tui.py:463` `on_paste` | Le bracketed paste était ignoré : coller « firefox » ne remplissait pas la recherche | `use_paste(app.on_paste)` → `insert_text` + nouvelle requête ; retours ligne écrasés en espaces | ✅ |
| UI-03 | `tui.py` `_detail_for_row` | `attr`, `meta` et indice du panneau détail sans `_ellipsis` : débordement en colonne étroite | `_ellipsis(..., inner)` sur les 3 lignes ; indice aligné sur `ctrl+x` | ✅ |
| UX-04 | `nixpick.py:229` | `nixpick --remove` sans terme tombait dans la TUI au lieu de refuser | Code d'erreur **2** + message d'usage sur stderr | ✅ |
| QUA-03 | `rofi_mode.py:223` | `--rofi` sans rofi installé → « rofi introuvable » puis **exit 0** (faux succès) | Vérification `shutil.which` en tête de `run_rofi` → **exit 1** | ✅ |
| QUA-04 | `engine.py` `AddOutcome` | Attribut invalide classé `BLOCK_MISSING` (« bloc absent ») au lieu de `INVALID_ATTR` | `AddOutcome.INVALID_ATTR` ajouté et utilisé | ✅ |
| QUA-01 | `engine.py:429` `_nix_code_only` | Les `[` `]` **à l'intérieur des chaînes** déséquilibraient le bloc → « bloc non pris en charge » à tort | Commentaires retirés puis chaînes vidées avant comptage | ✅ |
| QUA-06 | `engine.py` `DescriptionCache` | Dict muté depuis le worker TUI pendant `json.dumps` → `RuntimeError` possible | `threading.Lock` sur `get` / `remember` / `remember_many` | ✅ |
| UX-09 | `fix_git_runner.py:49` | `fix-git -y` ajoutait les fichiers **sans jamais les lister** | Inventaire toujours imprimé avant toute action | ✅ |
| UX-12 | `engine.py:219` `_is_subsequence` | UI « fuzzy-finder / style fzf », recherche strictement contiguë | 4ᵉ rang `20` pour la sous-séquence — ne repousse jamais un match contigu | ✅ |
| TST-01 | `tests/` | Aucun test sur échec d'index, codes de sortie CLI, fuzzy, purge, plan | 17 tests ajoutés (83 → 100) | ✅ |
| UX-10 | `rofi_mode.py:312` | `fetch_descriptions` (jusqu'à 90 s de `nix eval`) bloquait le lancement rofi pour **tous** les résultats alors qu'un seul était utilisé | Description chargée **après** le choix, pour l'attribut seul | ✅ |

## 6. Findings P2 / P3

| ID | Constat | Statut |
|----|---------|--------|
| QUA-10 | Branche `if key == "ctrl+c"` morte (`if ctrl:` renvoie avant) | ✅ retirée |
| QUA-11 | Imports morts : `rofi_theme.asset_path`, `theme.CONFIG_FILE`, `config.json` | ✅ retirés (2 monkeypatchs de tests devenus morts aussi) |
| UX-08 | Les sauvegardes `packages.nix.bak.<ts>` s'accumulaient à jamais | ✅ `prune_backups(keep=5)` appelée dans `commit_add`/`commit_remove` |
| UX-11 | THEMES.md recommandait un `.rasi` manuel dans `~/.config/rofi/`, **jamais atteint** (le fichier généré est réécrit et prioritaire) | ✅ doc corrigée : priorité explicite + `rofi -theme` pour un rasi complet |
| UI-04 | `colors.rofi.comment` n'était écrit que dans un commentaire CSS = clé sans effet | ✅ `placeholder-color` dans le bloc `entry` (documenté `rofi-theme(5)`) |
| QUA-07 | CHANGELOG incomplet | ✅ section 0.4.0 enrichie |
| UX-10 / PERF-01 | Descriptions bloquantes | ✅ partiel (rofi) ; la TUI était déjà asynchrone |
| TST-02 | Baseline lint : `[tool.ruff]` (17 règles) + job CI, 35 findings traités | ✅ fait (voir §7) |
| QUA-08 | `build/lib/rebuild_runner.py` (artefact setuptools) contenait un `shell=True` hérité d'une ancienne version | ✅ résolu : `build/` supprimé (gitignoré, régénérable) ; **zéro** `shell=True` dans les sources — voir §7 |
| PERF-02 | Scan de repli : `_is_subsequence` en générateur Python → ~90 ms par frappe sur 100k lignes, GIL tenu (TUI saccadée) | ✅ regex compilée par requête (`lru_cache`, `re.escape`) + préfiltre `needle[0]` : ~33 ms, moteur C hors GIL |
| PERF-03 | Autres chemins chauds non mesurés | ✅ vérifié : bucket par initiale + `limit` (2-4 ms courant), `from_dict` 0,13 s/100k, `nix eval` en un batch, descriptions TUI debounce 0,35 s + max 5, index en cache 7 j — RAS |

## 7. Items ouverts — justification

- **TST-02 (lint CI).** ✅ **corrigé** : baseline `[tool.ruff]` explicite dans
  `pyproject.toml` (17 règles, pas de familles larges — évite les faux positifs
  `S607` sur `git`/`notify-send`, `E501`, …), 35 findings traités :
  22 mécaniques (`I001`, `UP035`, `UP017`, `FURB162`, `F401`, `PLR1730`),
  13 manuels. Points sensibles :
  - `tui.py` : tri intra-bloc uniquement — l'ordre `native_env` → `opentui`
    est protégé par `E402` + `# noqa` voulus (contrôlés par `RUF100`) ;
  - `rofi_mode._notify` : `except Exception: pass` intentionnel
    (`noqa: BLE001, S110` + repli stderr) ;
  - `doctor` : `check=False` explicite (returncode inspecté) ;
  - `engine._backup_path` : `time.strftime` local au lieu de `datetime.now()`
    naïf — même valeurs, plus de `DTZ005` ;
  - `ISC004` : concaténations voulues parenthésées (4 sites).
  - Job `lint` ajouté à `.github/workflows/test.yml` (`ruff==0.16.*`,
    Python 3.13) ; `ruff` ajouté à l'extra `dev` (sans effet sur le build Nix,
  qui n'installe pas les extras).
- **QUA-08.** ✅ **résolu** : le `shell=True` existait bien, mais uniquement dans
  `build/lib/rebuild_runner.py` — copie obsolète générée par setuptools
  (elle contenait encore `tui_css.py`, supprimé depuis). Les sources n'ont
  **aucun** `shell=True` (vérifié par grep). `build/` (gitignoré) a été supprimé ;
  il se régénère à la prochaine construction.

## 8. Vérification

| Commande | Résultat |
|----------|----------|
| `pytest -q` | **100 passed** (7,5 s) |
| `ruff check .` | **All checks passed** (baseline `[tool.ruff]`, ruff 0.16.4) |
| `nix flake check` | **all checks passed** (100 tests sandbox + smoke `nixpick`) |
| Bench recherche (100k lignes synthétiques) | courant 2-4 ms ; repli scan complet 96 → **33 ms** (regex + préfiltre) |
| Rendu 100×30 / 90×14 / 40×30 / 30×8 | ok — footer contenu, aide tronquée, overlay trop petit |
| Échec d'index simulé | `loading=False`, hint « index indisponible », `last_error is None` |
