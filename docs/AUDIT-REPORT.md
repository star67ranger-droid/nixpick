# Rapport d'audit — nixpick 0.3.6

## 1. Résumé exécutif

Audit du working tree de `nixpick` (22 fichiers modifiés non commités depuis le HEAD du 23/09,
commit de départ `a480b25`). État global : moteur et configuration sains (63/63 tests en 0,50 s,
index performant, aucun secret détecté), mais la couche TUI/Rofi accumule des défauts de
robustesse et deux diagnostics sont mensongers.

**Findings : 22 au total — 1 haute, 8 moyennes, 13 basses.**

Trois risques principaux :

1. **UX-01 (haute)** — les raccourcis monolettre annoncés (`d t i l x ?`) sont inertes dans l'état par défaut de la TUI : le champ de recherche avale les touches avant le handler applicatif. README, aide et footer décrivent un produit qui ne se comporte pas comme prévu.
2. **UI-01 (moyenne)** — markup Rich non échappé injecté depuis des données externes : crash de la TUI sur `[/]` et perte silencieuse de texte courant (`[nom]`).
3. **QUA-01 / UX-04 (moyennes)** — le verrou `.packages.nix.nixpick.lock` est tracké et recommitté dans le dépôt de configuration, et le doctor accuse à tort `flake.lock` (hash incluant `.git` / `.pytest_cache`), poussant à des `--update-input` inutiles.

**Verdict : correctifs urgents requis avant production généralisée — le noyau est fiable, mais la
TUI par défaut contredit sa propre documentation et deux diagnostics produisent des faux positifs.**

## 2. Périmètre et méthodologie

- **Date :** 27/09/2026. **Commit de départ :** `a480b25` (`git log -1 --format=%h`). **Version :** 0.3.6 (`pyproject.toml`, cohérente avec `flake.nix` et la doc).
- **Dépôt :** working tree, 22 fichiers modifiés/supprimés non commités (`tui.py`, `cli.py`, `engine.py`, `config.py`, `flake_git.py`, `theme.py`, `doctor.py`, `rebuild_runner.py`, `rofi_theme.py`, `messages.py`, `bin/nixpick`, `scripts/install.sh`, `.github/workflows/test.yml`, `tests/*`, `CHANGELOG.md`, `README.md`, `pyproject.toml`, `flake.nix`, `config.example.toml`, `requirements.txt` supprimé), plus 3 non suivis.
- **Modules examinés :** `engine.py`, `config.py`, `tui.py`, `cli.py`, `rofi_mode.py`, `flake_git.py`, `flake_lock.py`, `theme.py`, `doctor.py`, `rebuild_runner.py`, `nixpick.py`, `scripts/install.sh`, `assets/rofi/`, `tests/`, CI.
- **Outils et mesures :** `pytest` (63 tests, 0,50 s, Python 3.14, textual 8.2.8) ; TUI pilotée headless (44×12 et 90×24, pressions simulées) ; `git ls-files` / `git check-ignore` sur `/etc/nixos` ; `git add` de chemins quotés ; `--print-config`, `--list-installed` sur la config réelle ; expérience NAR hash isolée dans `/tmp/opencode/narhash2`.
- **Non audité :** rendu Rofi en conditions réelles ; `nixos-rebuild` et `nix flake lock --update-input nixpick` (cause du hash mismatch prouvée, conséquence « rebuild échouera » non vérifiée) ; `install.sh`, `nix flake check`, CI, cibles Python 3.11/3.12 ; encodage non UTF-8 de `packages.nix` ; dépôt root-owned ; hypothèse `attr_name` sans préfixe racine ; couverture réelle (`pytest-cov` absent) ; aucun linter/typecheck configuré.

## 3. Synthèse

| Sévérité | Sécurité | UX | UI | Qualité | Perf | Tests | Total |
|----------|----------|----|----|---------|------|-------|-------|
| Haute    | 0        | 1  | 0  | 0       | 0    | 0     | 1     |
| Moyenne  | 3        | 3  | 1  | 1       | 0    | 0     | 8     |
| Basse    | 0        | 4  | 0  | 7       | 1    | 1     | 13    |
| **Total**| **3**    | **8** | **1** | **8** | **1** | **1** | **22** |

*Note : le résumé du fichier de findings annonce « 20 constats, dont 11 bas » ; son propre tableau et sa section détail en listent 22 (13 basses). Le tableau détaillé fait foi.*

## 4. Findings

### 4.1 Sévérité haute

#### [UX-01] Raccourcis monolettre morts dès que la recherche a le focus — haute

- **Catégorie / Fichier :** UX — `tui.py:365-386` (preuves : `tui.py:362`, `tui.py:366`, `tui.py:372-386`, `README.md:109-113`, `tui.py:214-219`)
- **Problème :** la TUI focalise `#search` au démarrage (`tui.py:362`) ; la docstring `tui.py:366` annonce « d / t / i / ? même quand la recherche a le focus » et `tui.py:372-386` les traite — or le widget `Input` consomme les touches caractères avant le handler applicatif.
- **Preuve :** mesure headless, focus `Input` :

  ```text
  press d/t/i/l/x/? → input = "dti l x ?" ; flags _dry_run/_hide_installed/
                      _installed_catalog/_transparent inchangés ; screen_stack 1→1 (x)
  Tab (focus OptionList) puis d → _dry_run False→True ; puis x → screen_stack 1→2
  ```

  Contradit `README.md:109-113` (« ↵ ajouter · **x** retirer · **l** catalogue · **i** masquer · **d** simulation · **?** aide ») et l'aide `tui.py:214-219`.
- **Impact :** 6 interactions annoncées inutilisables dans l'état par défaut ; `x` et `?` (retrait, aide) sont les plus pénalisants. `ctrl+d`/`ctrl+i`/`ctrl+t`/`ctrl+l`/`F1`/`↵` fonctionnent avec le focus recherche (vérifié) : contournement partiel, non documenté.
- **Recommandation :** intercepter ces caractères avant le widget focalisé (filtre en amont de l'`Input`), ou documenter `Tab` + `ctrl+*` comme parcours normal.

### 4.2 Sévérité moyenne

#### [UI-01] Markup Rich injecté sans échappement — moyenne

- **Catégorie / Fichier :** UI — `tui.py:650` (aussi `tui.py:131`, `tui.py:83`, `tui.py:218`)
- **Problème :** des données externes (descriptions nixpkgs, diff, littérales) sont insérées dans des `Static` comme markup Rich interprété.
- **Preuve :** `self.query_one("#detail-body", Static).update(desc)` (`tui.py:650`), `Static(desc, id="modal-desc")` (`tui.py:131`), diff inséré tel quel (`tui.py:83`). Rejeté en tête d'app : description `"Print differences between files [/] and more"` → `MarkupError` (WorkerFailed) ; `"Lightweight web browser [sic]"` → rendu `"Lightweight web browser "` (fin avalée). Typo `tui.py:218` `[b #{a}?[/]` → aide affichée littéralement `F1 / [b #51a8b3?[/]        aide` (mesuré).
- **Impact :** crash de la TUI sur un contenu `[/]`, disparition silencieuse de texte courant (`[nom]`), ligne d'aide cassée.
- **Recommandation :** `Text.from_markup`/échappement ou `Text(...)` brut pour toute donnée issue de l'index, du fichier ou d'une literal non close ; corriger `tui.py:218`.

#### [SEC-01] Config TOML invalide ignorée silencieusement — moyenne

- **Catégorie / Fichier :** sécurité — `config.py:111` (aussi `nixpick.py:176-182`, `theme.py:17`)
- **Problème :** toute erreur de parse ou de lecture du TOML redirige silencieusement vers la config par défaut, sans diagnostic.
- **Preuve :** `except (tomllib.TOMLDecodeError, OSError):` → retour aux défauts, aucun message (`config.py:111`), et `nixpick.py:176-182` affiche le résultat sans source. Testé avec `config.toml` contenant `packages_anchor = "foo` (non fermé) pointant vers `/tmp/DOES-NOT-EXIST/custom.nix` : `--print-config` affiche `packages_file=/etc/nixos/modules/packages.nix`, `--list-installed` lit ce fichier. Séparément, `primary = "blue"` lève un `ValueError` non intercepté (`theme.py:17`).
- **Impact :** une faute de frappe redirige silencieusement les écritures vers le fichier par défaut (visible dans la confirmation, invisible pour `--list-installed` / `--why`).
- **Recommandation :** signaler l'erreur de parse (et refuser de démarrer) plutôt que de retomber sur les défauts.

#### [SEC-02] `git status --porcelain` non déquoté — moyenne

- **Catégorie / Fichier :** sécurité — `flake_git.py:82` (aussi `flake_git.py:114-138`)
- **Problème :** les guillemets que Git pose sur les chemins contenant espace ou non-ASCII sont conservés puis rejoués dans `git add`.
- **Preuve :** `rel = line[3:].strip()` (`flake_git.py:82`) conserve les guillemets ; `flake_git.py:114-138` rejoue ces noms dans `git add`. Vérifié : `git add -- '"with space.txt"'` → `fatal: le chemin … ne correspond à aucun fichier`, exit 128. Aucun chemin concerné dans `/etc/nixos` (0 occurrence) → latent.
- **Impact :** `fix-git` et le conseil de préflight échouent sur espaces/non-ASCII ; risque de stager un fichier homonyme littéralement nommé `"a b"`.
- **Recommandation :** `-z` + split sur NUL (ou retrait des guillemets) avant de réutiliser les chemins.

#### [SEC-03] Rofi : exceptions métier non interceptées — moyenne

- **Catégorie / Fichier :** sécurité — `rofi_mode.py:282` (blocs `rofi_mode.py:280-285` et `rofi_mode.py:310-315`)
- **Problème :** seul `PermissionError` est intercepté, alors que `commit_add`/`commit_remove` peuvent lever `NixSyntaxError` (`engine.py:612`) et `LookupError` (`engine.py:704`, `engine.py:804`).
- **Preuve :** `rofi_mode.py:280-285` et `310-315` n'interceptent que `PermissionError`, alors que la CLI (`cli.py:161-166`) et la TUI (`tui.py:868-873`) attrapent les trois.
- **Impact :** en Rofi, une validation Nix échouée ou une ligne introuvable termine en traceback Python sans notification (le flux Rofi n'affiche rien d'utile).
- **Recommandation :** aligner les `except` du parcours Rofi sur ceux de CLI/TUI.

#### [UX-02] TUI bloquée sur « chargement » après échec d'index — moyenne

- **Catégorie / Fichier :** UX — `tui.py:456` (blocs `tui.py:447-458`, `tui.py:460`, `tui.py:464`)
- **Problème :** après un échec de construction de l'index, `_loading` n'est jamais remis à `False`.
- **Preuve :** `except NixCommandError` se contente d'un `notify` (`tui.py:447-458`), `_set_loading` force `self._loading = True` (`tui.py:460`), et `_loading = False` n'existe que dans `_on_index_ready` (`tui.py:464`), jamais appelé ici. Reproduit avec un `PATH` sans `nix-env` : chrome affiché « Construction de l'index nixpkgs (~20 s)… » en permanence alors que l'erreur est déjà passée.
- **Impact :** interface utilisable mais état mensonger ; l'utilisateur croit une opération en cours.
- **Recommandation :** `_loading = False` dans le bloc d'exception, avec message d'état explicite.

#### [UX-03] Couleur invalide → traceback au démarrage — moyenne

- **Catégorie / Fichier :** UX — `tui.py:953` (blocs `tui.py:946-959`, `theme.py:14-17`, `rofi_mode.py:219-222`)
- **Problème :** `run_tui` ne catch que `KeyboardInterrupt` alors que la validation de couleur lève `ValueError` ; `run_rofi` appelle `sync_rofi_themes()` avant tout.
- **Preuve :** `theme.py:14-17` lève `ValueError … couleur invalide`, `tui.py:946-959` ne catch que `KeyboardInterrupt`, `rofi_mode.py:219-222` synchronise avant tout. Testé : `run_tui()` → `NON-INTERCEPTED: ValueError colors.primary : couleur invalide 'blue' (attendu #RGB ou #RRGGBB)`. `docs/THEMES.md:89` décrit pourtant un dépannage.
- **Impact :** une faute de saisie dans `[colors]` rend la TUI et `--rofi` inutilisables avec un traceback.
- **Recommandation :** attraper `ValueError` à l'entrée de `run_tui`/`run_rofi` et afficher `notify`/message d'erreur lisible.

#### [UX-04] Doctor : alarme `flake.lock` intenable + aide fausse — moyenne

- **Catégorie / Fichier :** UX — `flake_lock.py:104` (blocs `flake_lock.py:41-47`, `flake_lock.py:93-111`, aide `nixpick.py:49`)
- **Problème :** le doctor compare le `narHash` verrouillé à `nix hash path` de l'arbre complet du dépôt d'entrée : `.git` et les caches entrent dans le hash.
- **Preuve :** `flake_lock.py:41-47` exécute `nix hash path <dépôt>` (l'aide `nixpick.py:49` « sans lancer Nix » est fausse — mesuré, 0,23 s) ; `flake_lock.py:93-111` compare `sha256-CAhE…`/actuel `sha256-91Ii…` et affirme « le rebuild échouera (NAR hash mismatch) ». Sources inchangées depuis le lock (`flake.nix` verrouillé 26/09 14:57:36, aucun `*.py` modifié) alors que `.git` (auto-commits du 27/09) et `.pytest_cache` ont changé. Expérience `/tmp/opencode/narhash2` : pour un input `type: path`, le `narHash` verrouillé **vaut** `nix hash path` de l'arbre complet, et un simple `git commit` le modifie (aucun filtrage git) → alarme après chaque commit.
- **Impact :** doctor accuse un « échec » permanent dès un commit ou un `pytest` ; `nix flake lock --update-input nixpick` est systématiquement proposé ; la prévision de rebuild échoué n'est pas démontrée par ce code (aide après échec, `rebuild_runner.py:103`).
- **Recommandation :** exclure `.git`, `.venv`, `__pycache__` et caches du hash (ou comparer les sources), corriger l'aide `--help`.

#### [QUA-01] Fichier de verrou nixpick tracké dans le dépôt de config — moyenne

- **Catégorie / Fichier :** qualité — `engine.py:470` (blocs `engine.py:467-477`, `flake_git.py:13-14`)
- **Problème :** le verrou `.{packages_file}.nixpick.lock` est créé dans le dossier du flake, jamais supprimé, jamais ignoré.
- **Preuve :** `engine.py:467-477` crée `.{packages_file}.nixpick.lock` et ne le supprime pas ; `flake_git.py:13-14` n'ignore que les suffixes `".bak."` ; `/etc/nixos/.gitignore` n'a aucune règle (`git check-ignore` : non ignoré). Constat : `git -C /etc/nixos ls-files` → `modules/.packages.nix.nixpick.lock` (0 octet) **tracké**, régulièrement recommitté par les `chore: auto-commit apres rebuild`.
- **Impact :** artefact transitoire versionné dans le dépôt de configuration, régulièrement modifié par nixpick, et stageable par `fix-git`.
- **Recommandation :** ajouter `.nixpick.lock` à `_IGNORE_UNTRACKED_SUFFIXES`, supprimer le fichier après usage et le désindexer.

### 4.3 Sévérité basse

#### [UX-05] Sauvegardes `.bak.*` jamais purgées — basse

- **Catégorie / Fichier :** UX — `engine.py:463` (`engine.py:459-464`)
- **Preuve :** un `.bak.<horodatage>` par écriture, aucun nettoyage ; constat : 6 fichiers du 20/09 au 25/09 dans `/etc/nixos/modules/`, dont 4 déjà trackés dans le dépôt flake.
- **Impact :** accumulation de sauvegardes obsolètes, dont des fichiers versionnés. **Recommandation :** conserver N sauvegardes glissantes, purger les plus anciennes.

#### [UX-06] Permissions perdues à l'écriture — basse

- **Catégorie / Fichier :** UX — `engine.py:620` (`engine.py:620-628`)
- **Preuve :** `mkstemp` → 0600 puis `os.replace` conserve ce mode ; constat `modules/packages.nix` `-rw-------` alors que tous les modules voisins sont `-rw-r--r--`.
- **Impact :** mode de fichier de config incohérent avec le dépôt. **Recommandation :** réappliquer le mode source sur le fichier final.

#### [UX-07] `fix-git -y` sans inventaire des fichiers stageés — basse

- **Catégorie / Fichier :** UX — `rofi_mode.py:144` (aussi `rofi_mode.py:167`)
- **Preuve :** `run_fix_git(yes=True)` appelé sans la liste des fichiers, contrairement au parcours explicite.
- **Impact :** stager sans que l'utilisateur ait vu quoi que ce soit. **Recommandation :** lister les fichiers avant de stager, y compris en Rofi.

#### [UX-08] Réécriture des thèmes Rofi à chaque appel — basse

- **Catégorie / Fichier :** UX — `config.py:200`
- **Preuve :** `sync_rofi_themes()` via `rofi_theme_paths()`, donc à chaque écran Rofi et au démarrage de la TUI (`tui.py:945`) → 2 `write_text` non atomiques par appel (`_rofi` invoqué ~5 fois par flux).
- **Impact :** écritures disque inutiles et non atomiques à chaque interaction. **Recommandation :** écrire seulement si le contenu diffère, de façon atomique.

#### [QUA-02] Codes retour et drapeaux incohérents — basse

- **Catégorie / Fichier :** qualité — `cli.py:135` (`cli.py:133-135`, `rofi_mode.py:294-297`, `nixpick.py:221-224`)
- **Preuve :** `AddFailure` → `return 0` (`cli.py:133-135`, idem Rofi) alors que `run_cli_remove` renvoie 1 sur échec ; `--remove` sans `--term` ne rentre pas dans `if args.term` (`nixpick.py:221-224`) → chute sur la TUI silencieusement.
- **Impact :** échec d'ajout signalé comme succès au shell ; usage de `--remove` mal diagnostiqué. **Recommandation :** sortie 1 sur échec, message d'usage si `--remove` sans terme.

#### [QUA-03] Mauvais outcome pour attribut invalide — basse

- **Catégorie / Fichier :** qualité — `engine.py:662` (`engine.py:660-662`, `engine.py:762`)
- **Preuve :** `_validate_attr_name` échoue → `AddOutcome.BLOCK_MISSING` (message correct, code d'issue faux), alors que `plan_remove` dispose de `RemoveOutcome.INVALID_ATTR` (`engine.py:762`).
- **Impact :** diagnostics et tests trompeurs sur le vrai motif d'échec. **Recommandation :** réutiliser/ajouter `INVALID_ATTR` côté ajout.

#### [QUA-04] Bloc Nix non détecté à cause des crochets en chaîne — basse

- **Catégorie / Fichier :** qualité — `engine.py:416`
- **Preuve :** `depth += stripped.count("[") - stripped.count("]")` sur une ligne dont les guillemets sont ignorés. Reproduit : description `"say [hi"` → `_find_package_block` = `(2, None)` → `plan_add` : `AddFailure("Fin du bloc … non équilibré")` ; `"say hi]"` → `(None, None)` (`list_installed_attrs()` → `set()`), alors que le bloc est valide.
- **Impact :** édition bloquée ou inventaire vide sur un fichier pourtant valide. **Recommandation :** ignorer le contenu des chaînes/attributs avant le comptage.

#### [QUA-05] Restauration annoncée à tort — basse

- **Catégorie / Fichier :** qualité — `engine.py:609` (`engine.py:604-615`)
- **Preuve :** `OSError` du `shutil.copy2` (lignes 609-611) avalé puis l'exception annonce « restauré depuis la sauvegarde » ; `copy2` n'est pas atomique (fichier partiellement lu possible).
- **Impact :** l'utilisateur croit un rollback effectué alors qu'il a échoué. **Recommandation :** propager ou signaler explicitement l'échec de restauration.

#### [QUA-06] CHANGELOG incomplet — basse

- **Catégorie / Fichier :** qualité — `CHANGELOG.md:3`
- **Preuve :** entrées 0.2.0 et 0.3.1 absentes alors que `git log` les mentionne (version courante 0.3.6 cohérente entre `pyproject.toml`, `flake.nix` et la doc).
- **Impact :** historique incomplet pour les utilisateurs et le release management. **Recommandation :** remonter les entrées manquantes (interdit à cette étape).

#### [QUA-07] Copie morte `build/lib/` avec `shell=True` — basse

- **Catégorie / Fichier :** qualité — `build/lib/rebuild_runner.py:77`
- **Preuve :** `subprocess.run(cmd, shell=True, check=False)` ; copie gitignorée via `build/` dans `.gitignore`, diverge du code réel `rebuild_runner.py` sans `shell`.
- **Impact :** dette et risque de confusion si la copie est exécutée par erreur. **Recommandation :** supprimer `build/`.

#### [QUA-08] Assets Rofi copiés puis systématiquement écrasés — basse

- **Catégorie / Fichier :** qualité — `scripts/install.sh:9` (aussi `config.py:200-205`)
- **Preuve :** `install.sh` place les assets dans `~/.config/rofi` (rang 2) alors que `config.py:200-205` régénère le rang 1 à chaque lancement → `assets/rofi/*.rasi` (porteurs d'un `textbox` d'instructions absent du template) inutilisés dès la première exécution.
- **Impact :** travail d'install sans effet, instructions visibles seulement au premier lancement. **Recommandation :** cesser de les copier, ou les servir en secours réel.

#### [TST-01] Zone aveugle : TUI et CLI sans aucun test — basse

- **Catégorie / Fichier :** tests — `tui.py` / `cli.py` (`.github/workflows/test.yml:23-24`, `pyproject.toml:26`, `tests/test_flake_lock.py:20`)
- **Preuve :** imports dans `tests/` : `config` 10, `engine` 8, `rofi_mode` 1, `theme` 1, `nixpick` 1, `flake_lock` 1, `flake_git` 1, `fix_git_runner` 1, `doctor` 1, `rebuild_runner` 1, **`cli` 0, `tui` 0** ; CI = pip + pytest (`test.yml:23-24`), ni lint ni typecheck (`pyproject.toml:26` : `dev = ["pytest"]`) ; `tests/test_flake_lock.py:20` : chemin codé en dur `/home/pikeo/Projets/nixpick`.
- **Impact :** `tui.py` (960 lignes) et `cli.py` (171 lignes) non couverts ; la CI ne détecte ni régression d'UI ni erreur de style. **Recommandation :** smoke tests headless TUI/CLI + ruff/mypy en CI ; sortir le chemin codé en dur du test.

#### [PER-01] Descriptions bloquantes en CLI/Rofi — basse

- **Catégorie / Fichier :** perf — `cli.py:111` (`engine.py:337-353`, `rofi_mode.py:246`)
- **Preuve :** `nix eval --json --impure` avec `timeout=90` (`engine.py:337-353`), appelé synchrone depuis `cli.py:111` et `rofi_mode.py:246` sans indicateur (la TUI a un worker : correctement servie).
- **Impact :** jusqu'à 90 s de gel en CLI et en Rofi, sans feedback. **Recommandation :** limiter/afficher une progression, ou différer la récupération des descriptions.

## 5. Plan d'action priorisé

### A. Correctifs immédiats (bloquants)

| ID | Fiche (fichier à toucher) | Effort | Risque si ignoré |
|----|---------------------------|--------|------------------|
| UX-01 | Raccourcis — `tui.py:365-386` (handler avant `Input`) ; doc `README.md:109-113`, `tui.py:214-219` | M | 6 interactions annoncées inutilisables, produit perçu cassé |
| UI-01 | Markup — `tui.py:650`, `tui.py:131`, `tui.py:83`, typo `tui.py:218` | M | Crash TUI sur `[/]`, perte de texte silencieuse |
| QUA-01 | Verrou — `engine.py:467-477`, `flake_git.py:13-14`, `.gitignore` de `/etc/nixos` | S | Artefact transitoire permanent dans le dépôt de config |
| UX-04 | Doctor — `flake_lock.py:41-47`, `flake_lock.py:93-111`, aide `nixpick.py:49` | M | Faux positifs permanents → `--update-input` inutiles |
| SEC-02 | Déquotage — `flake_git.py:82` (`-z` + split NUL), `flake_git.py:114-138` | S | `fix-git` fatal sur espaces/non-ASCII, stager faux |

### B. Corrections courtes (cette semaine)

| ID | Fiche (fichier à toucher) | Effort | Risque si ignoré |
|----|---------------------------|--------|------------------|
| SEC-01 | Parse config — `config.py:111` (+ `theme.py:17`) | M | Écritures redirigées silencieusement vers le défaut |
| SEC-03 | Exceptions Rofi — `rofi_mode.py:280-285`, `rofi_mode.py:310-315` | S | Traceback sans notification en mode Rofi |
| UX-02 | État chargement — `tui.py:447-458` | S | Écran « chargement » mensonger après échec |
| UX-03 | Couleurs — `tui.py:946-959`, `rofi_mode.py:219-222` | S | TUI/--rofi inutilisables au démarrage |
| UX-05 | Purge `.bak` — `engine.py:459-464` | S | Sauvegardes obsolètes accumulées et versionnées |
| UX-06 | Permissions — `engine.py:620-628` | S | Mode 0600 au lieu de 0644 |
| UX-07 | Inventaire fix-git — `rofi_mode.py:144`, `rofi_mode.py:167` | S | Staging sans visibilité |
| UX-08 | Écriture thèmes — `config.py:200` | S | Écritures non atomiques à chaque écran |
| QUA-02 | Exit codes — `cli.py:133-135`, `rofi_mode.py:294-297`, `nixpick.py:221-224` | S | Échec signalé comme succès |
| QUA-03 | Outcome — `engine.py:660-662` | S | Code d'issue faux |
| QUA-05 | Restauration — `engine.py:604-615` | S | Rollback annoncé à tort |
| QUA-07 | Supprimer `build/` | S | Copie morte avec `shell=True` |
| QUA-08 | Assets — `scripts/install.sh:9`, `config.py:200-205` | S | Install sans effet réel |

### C. Améliorations de fond

| ID | Fiche (fichier à toucher) | Effort | Risque si ignoré |
|----|---------------------------|--------|------------------|
| QUA-04 | Comptage de blocs — `engine.py:416` | M | Édition bloquée / inventaire vide sur fichier valide |
| QUA-06 | Entrées manquantes — `CHANGELOG.md` (0.2.0, 0.3.1) | M | Historique de release incomplet |
| TST-01 | Tests TUI/CI — `tests/`, `.github/workflows/test.yml:23-24`, `pyproject.toml:26`, `tests/test_flake_lock.py:20` | L | 960 lignes de TUI sans filet, CI sans lint ni typecheck |
| PER-01 | Descriptions — `engine.py:337-353`, `cli.py:111`, `rofi_mode.py:246` | L | Gels de 90 s sans feedback en CLI/Rofi |

### D. À ne pas faire / hors périmètre

- Ne pas conclure « le rebuild échouera » à partir de UX-04 : conséquence non vérifiée (aucun `nixos-rebuild` exécuté pendant l'audit).
- Ne pas « corriger » les chemins `/etc/nixos` en dur : défauts documentés (`config.example.toml`, README).
- Rendu Rofi en conditions réelles, `nix flake check`, cibles Python 3.11/3.12, écriture sur dépôt root-owned : à valider dans une passe dédiée.
- Ne pas traiter l'hypothèse `attr_name` sans préfixe racine ni l'encodage non UTF-8 sans cas de reproduction.
- Interdit à cette étape : version, `CHANGELOG.md`, `README.md` (rapport seul).

## 6. Annexe

**Chaîne de commande de l'audit**

```bash
git log -1 --format=%h                    # a480b25
git status --porcelain                    # 22 fichiers modifiés/supprimés non commités
grep -n "^version" pyproject.toml         # 0.3.6
pytest                                    # 63 passed, 0.50s
git -C /etc/nixos ls-files                # modules/.packages.nix.nixpick.lock tracké
git check-ignore modules/.packages.nix.nixpick.lock   # non ignoré
# TUI headless : pressions d/t/i/l/x/? avec focus Input puis OptionList
# Expérience NAR hash : /tmp/opencode/narhash2
```

Sources : findings bruts (`/tmp/opencode/nixpick-audit-findings.md`), dépôt `/home/pikeo/Projets/nixpick`, dépôt de configuration `/etc/nixos`.

**Liens internes vers les modules**

| Module | Rôle | Findings |
|--------|------|----------|
| `tui.py` | Interface Textual | UX-01, UI-01, UX-02, UX-03, TST-01 |
| `cli.py` | CLI argparse | QUA-02, PER-01, TST-01 |
| `engine.py` | Lecture/écriture de `packages.nix` | QUA-01, UX-05, UX-06, QUA-03, QUA-04, QUA-05 |
| `config.py` | Chargement TOML, thèmes Rofi | SEC-01, UX-08 |
| `flake_git.py` | Git du dépôt de config | SEC-02, QUA-01 |
| `flake_lock.py` | Doctor `flake.lock` | UX-04 |
| `rofi_mode.py` | Mode Rofi | SEC-03, UX-07 |
| `theme.py` | Validation des couleurs | SEC-01, UX-03 |
| `nixpick.py` | Point d'entrée, aides | SEC-01, UX-04, QUA-02 |
| `build/lib/rebuild_runner.py` | Copie obsolète | QUA-07 |
| `scripts/install.sh` | Installation | QUA-08 |
| `tests/`, CI | Tests et workflow | TST-01 |
| `CHANGELOG.md` | Historique | QUA-06 |
