"""Internationalisation FR/EN de toutes les chaînes utilisateur.

Français par défaut (comportement historique, déterministe — jamais de
détection de locale, pour des tests reproductibles). L'anglais s'active via
`language = "en"` dans config.toml, `NIXPICK_LANGUAGE=en`, ou le menu
paramètres de la TUI (temps réel).

Convention : `t("cle")` ou `t("cle", nom=valeur)` pour les gabarits
`{nom}`. Toute clé FR doit exister en EN (testé).
"""

from __future__ import annotations

FRENCH = "fr"
ENGLISH = "en"
SUPPORTED = (FRENCH, ENGLISH)
DEFAULT = FRENCH

_language: str = DEFAULT


def get_language() -> str:
    return _language


def set_language(code: str) -> str:
    """Fixe la langue (repli français si inconnue). Retourne l'effective."""
    global _language
    normalized = (code or "").strip().lower()
    _language = normalized if normalized in SUPPORTED else DEFAULT
    return _language


def t(key: str, **kwargs: object) -> str:
    """Chaîne traduite. Repli : français, puis la clé elle-même."""
    template = STRINGS.get(_language, {}).get(key)
    if template is None:
        template = STRINGS[FRENCH].get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template
    return template


STRINGS: dict[str, dict[str, str]] = {
    FRENCH: {
        # ── messages.py ──────────────────────────────────────────────
        "rofi.confirm_add": "Confirmer l'ajout",
        "rofi.confirm_remove": "Confirmer le retrait",
        "rofi.cancel": "Annuler",
        "rofi.rebuild_now": "\U000f040a Lancer le rebuild",
        "rofi.rebuild_later": "Plus tard",
        "rofi.fix_git": "\U000f02a2 Corriger Git (fix-git)",
        "rofi.sync_now": "Installer via sync",
        "cli.cancelled": "Abandonné.",
        "cli.saved": "Sauvegarde : {path}",
        "cli.apply_rebuild": "Pour appliquer : nixpick rebuild",
        "cli.apply_sync": "Pour installer : nixpick sync",
        "cli.apply_sync_detail": "  (nix profile install nixpkgs#… des listés)",
        "cli.success_rebuild": "Applique avec : nixpick rebuild\n({cmd})",
        "cli.success_sync": "Installe avec : nixpick sync",
        "cli.saved_body": "Sauvegarde : {path}\n{how}",
        "rofi.search_too_short": (
            "Tape au moins 2 caractères.\n"
            "Essaie un nom de paquet ou d'attribut nixpkgs."
        ),
        "rofi.index_title": "nixpick — index",
        "rofi.index_error": (
            "{detail}\nReconstruis l'index : nixpick --build-index-only"
        ),
        "rofi.not_found": (
            "Rien trouvé pour « {term} ».\n"
            "Essaie un autre terme ou vérifie l'orthographe."
        ),
        "rofi.permission_denied": (
            "Pas les droits d'écriture sur {path}.\n"
            "Vérifie les permissions ou adapte NIXPICK_PACKAGES_FILE."
        ),
        "rofi.dry_run_title": "nixpick (dry-run)",
        "rofi.dry_run_remove": (
            "{attr} aurait été retiré — aucune modification sur le disque."
        ),
        "rofi.dry_run_add": (
            "{attr} aurait été ajouté — aucune modification sur le disque."
        ),
        "rofi.removed_title": "nixpick · {attr} retiré",
        "rofi.added_title": "nixpick · {attr} ajouté",
        # ── cli.py ───────────────────────────────────────────────────
        "cli.remove_planned": "Suppression prévue dans {path} :",
        "cli.dry_run_nothing": "\nMode --dry-run : rien n'écrit.",
        "cli.confirm_remove": "\nJe retire ? [o/N] ",
        "cli.no_rights": "Pas les droits d'écriture sur {path}.",
        "cli.removed": "Retiré.",
        "cli.removed_hint_profile": (
            "Retiré de la liste. Pour désinstaller du profil : "
            "nix profile remove {attr}"
        ),
        "cli.confirm_rebuild": "\nLancer nixpick rebuild maintenant ? [o/N] ",
        "cli.fix_then_rebuild": (
            "\nLance : nixpick fix-git --yes   puis   nixpick rebuild"
        ),
        "cli.nothing_found": "Rien trouvé pour « {term} ».",
        "cli.choose": "\nLequel ? [1-{n}, Entrée pour annuler] ",
        "cli.invalid_choice": "Choix invalide.",
        "cli.add_planned": "Modification prévue dans {path} :",
        "cli.confirm_write": "\nJ'écris ? [o/N] ",
        "cli.added": "Ajouté.",
        "cli.file_created": "Fichier créé : {path}",
        "cli.confirm_install": (
            "\nInstaller nixpkgs#{attr} dans ton profil ? [o/N] "
        ),
        "cli.install_failed": (
            "L'ajout a réussi, mais l'installation a échoué (code {code})."
        ),
        # ── doctor.py ────────────────────────────────────────────────
        "doc.title": "Diagnostic nixpick",
        "doc.label_packages": "Fichier packages",
        "doc.pkg_will_create": (
            "{path} n'existe pas encore (sera créé au premier ajout)."
        ),
        "doc.pkg_writable_parent": (
            "{path} n'existe pas encore (le dossier parent est inscriptible)."
        ),
        "doc.pkg_unwritable": (
            "{path} introuvable et le dossier parent n'est pas inscriptible."
        ),
        "doc.pkg_unreadable": "{path} illisible.",
        "doc.pkg_readonly": "{path} existe mais n'est pas modifiable.",
        "doc.pkg_ok": "{path} présent et modifiable.",
        "doc.label_index": "Cache index",
        "doc.index_missing": (
            "Pas d'index dans {parent} "
            "(lance nixpick --build-index-only ou ouvre la TUI)."
        ),
        "doc.index_present": "Index présent ({name}), âge {age} j.",
        "doc.index_stale": (
            " Plus de {days} j — un refresh est conseillé (nixpick --refresh)."
        ),
        "doc.label_lock": "Verrou d'édition",
        "doc.lock_none": "Aucun fichier verrou (.nixpick.lock).",
        "doc.lock_idle": (
            "{name} présent mais inactif (pas d'édition en cours)."
        ),
        "doc.lock_active": (
            "Verrou actif sur {name} — "
            "une session nixpick modifie peut-être le fichier."
        ),
        "doc.lock_untestable": "Impossible de tester le verrou : {err}",
        "doc.label_nixenv": "nix-env",
        "doc.nixenv_ok": "nix-env trouvé dans le PATH.",
        "doc.nixenv_noenv": (
            "nix-env absent — requis pour l'index (nix-env -qaP). "
            "Installe le profil Nix classique ou active nix-command + nix-env."
        ),
        "doc.nixenv_nonix": (
            "Nix absent du PATH — requis pour l'index et les descriptions."
        ),
        "doc.label_rofi": "rofi (optionnel)",
        "doc.rofi_ok": "rofi trouvé (pour nixpick --rofi).",
        "doc.rofi_missing": "rofi absent — seulement utile avec nixpick --rofi.",
        "doc.label_flakelock": "flake.lock (input nixpick)",
        "doc.label_flakegit": "Git flake (fichiers suivis)",
        "doc.label_rebuild": "Commande rebuild",
        "doc.rebuild_empty": (
            "rebuild_command vide — configure config.toml "
            "ou NIXPICK_REBUILD_COMMAND."
        ),
        "doc.rebuild_ok": "Après ajout ou retrait : {cmd}",
        "doc.rebuild_no_nixos": (
            " — sans objet hors NixOS (appliquer avec `nixpick sync`)."
        ),
        "doc.report_failures": "{n} point(s) à corriger.",
        "doc.report_ok": "Tout semble en ordre.",
        "doc.why_invalid": "Attribut invalide : {attr}",
        "doc.why_missing": "Fichier configuré introuvable : {path}",
        # ── engine.py ────────────────────────────────────────────────
        "eng.nix_missing": (
            "{cmd} est introuvable. Installe Nix (voir README § Hors NixOS)."
        ),
        "eng.timeout": "{cmd} a dépassé {timeout} s.",
        "eng.file_missing": "{path} introuvable.",
        "eng.file_missing_why": "{path} introuvable ({err}).",
        "eng.invalid_attr": "Nom d'attribut invalide : {attr!r}",
        "eng.undo_none": "Aucune dernière opération enregistrée.",
        "eng.undo_invalid": "Dernière opération invalide ou illisible.",
        "eng.undo_other_file": (
            "La dernière opération concerne un autre fichier "
            "({recorded}), pas {target}."
        ),
        "eng.undo_bad_path": "Chemin de la dernière opération invalide.",
        "eng.undo_no_backup": "Dernière opération sans sauvegarde associée.",
        "eng.undo_backup_missing": "Sauvegarde introuvable : {path}",
        "eng.undo_backup_mismatch": (
            "La sauvegarde ne correspond pas au fichier cible {target}."
        ),
        "eng.undo_no_rights": "Pas les droits d'écriture sur {target}.",
        "eng.undo_impossible": "Restauration impossible : {err}",
        "eng.undo_add": "ajout",
        "eng.undo_remove": "retrait",
        "eng.undo_done": (
            "Fichier restauré : {target} "
            "(annulation du {verb} de {attr})."
        ),
        "eng.restored": "restauré depuis la sauvegarde",
        "eng.not_restored": "NON restauré",
        "eng.invalid_after_modify": (
            "{path} invalide après modification ({state}).{detail} "
            "Détail : {err}"
        ),
        "eng.already_listed": "{attr} est déjà dans environment.systemPackages.",
        "eng.already_listed_commit": "{attr} est déjà listé.",
        "eng.block_missing": (
            "Bloc « {anchor} » absent, multiple ou dans une forme non prise "
            "en charge. Format attendu : anchor = with pkgs; [ … ];"
        ),
        "eng.block_unbalanced": (
            "Fin du bloc « {anchor} » introuvable ou bloc Nix non équilibré."
        ),
        "eng.line_missing": "Ligne introuvable pour {attr}",
        "eng.build_start": "Construction de l'index nixpkgs (~20 s)…",
        "eng.build_done": "{n} paquets indexés.",
        "eng.stale_rebuild": "Index vieux de {age:.0f} jours, reconstruction…",
        "eng.unreadable": "Index illisible ({err}), reconstruction…",
        # ── nixpick.py ───────────────────────────────────────────────
        "app.interrupted": "Interrompu.",
        "app.report_bug": "\nSignale ce bug : {url}",
        "app.error": "nixpick : {err}",
        "app.desc": "Cherche un paquet nixpkgs et modifie environment.systemPackages.",
        "app.help_doctor": "vérifie config, cache, outils, Git flake et flake.lock (nix/git en lecture)",
        "app.help_doctor_json": "sortie JSON (checks structurés)",
        "app.help_rebuild": "lance la commande rebuild configurée (confirmée)",
        "app.help_yes": "sans demander confirmation",
        "app.help_yes_script": "sans demander confirmation (utile en script)",
        "app.help_terminal": "ouvre un émulateur (kitty, foot…) pour sudo / la sortie",
        "app.help_dry_run": "affiche la commande sans l'exécuter",
        "app.help_fix_git": "git add les fichiers non suivis (??) du dépôt flake NixOS",
        "app.help_fix_git_dry": "affiche la commande git sans l'exécuter",
        "app.help_sync": "installe dans le profil Nix les paquets listés mais absents (hors NixOS)",
        "app.help_sync_dry": "affiche la commande nix sans l'exécuter",
        "app.help_sync_upgrade": "met aussi à jour les listés déjà installés",
        "app.help_print_config": "affiche le fichier cible et la commande rebuild puis quitte",
        "app.help_term": "recherche en mode CLI (sinon ouvre la TUI)",
        "app.help_refresh": "reconstruit l'index nixpkgs au démarrage",
        "app.help_dryrun": "simulation : n'écrit pas dans packages.nix",
        "app.help_transparent": "TUI : fond transparent (comme superfile)",
        "app.help_opaque": "TUI : fond opaque (ignore la config)",
        "app.help_tui": "force la TUI même si un terme est passé",
        "app.help_rofi": "lance la recherche via Rofi (barre glass)",
        "app.help_build_index": "reconstruit l'index puis quitte (sans TUI)",
        "app.help_remove": "retire un paquet de environment.systemPackages (avec le terme CLI)",
        "app.help_list": "liste les attributs déjà présents dans environment.systemPackages",
        "app.help_list_json": "avec --list-installed : une ligne JSON (attrs, count, packages_file, index_age_days)",
        "app.help_undo": "restaure packages.nix depuis la dernière sauvegarde (sans rebuild)",
        "app.help_why": "indique si un attribut est dans le fichier packages configuré",
        "app.help_print": "affiche le meilleur attr sur stdout (composable : scripts, agents)",
        "app.remove_needs_term": (
            "nixpick : --remove exige un terme "
            "(ex. nixpick --remove firefox)."
        ),
        # ── flake_git.py / flake_lock.py ─────────────────────────────
        "git.status_unavailable": "git status indisponible : {err}",
        "git.status_failed": "git status a échoué (code {code}). {detail}",
        "git.paths_skipped": "Attention : {n} chemin(s) ignoré(s) (nom invalide).",
        "git.no_flake_check": "Pas de flake NixOS détecté (check Git ignoré).",
        "git.clean": (
            "Dépôt {top} : aucun fichier non suivi (??) sous le flake. "
            "Racine flake : {rel}/"
        ),
        "git.untracked_head": (
            "{n} fichier(s) non suivi(s) sous le flake — Nix ne les voit pas "
            "tant qu'ils ne sont pas dans git :"
        ),
        "git.untracked_more": "      … et {n} autre(s).",
        "git.untracked_all_included": (
            "      (commande ci-dessus inclut tous les fichiers non suivis.)"
        ),
        "git.preflight_blocked": (
            "Rebuild bloqué avant lancement : des fichiers du flake ne sont "
            "pas suivis par Git.\n{detail}\n"
            "Puis : nixpick fix-git   ou   nixpick rebuild"
        ),
        "lock.no_root": (
            "Pas de flake NixOS détecté à côté de packages_file (check ignoré)."
        ),
        "lock.unreadable": "flake.lock illisible ({err}) — check ignoré.",
        "lock.no_input": "Aucun input path « nixpick » dans flake.lock (check ignoré).",
        "lock.points_missing": (
            "Input nixpick pointe vers {path} (absent). "
            "Corrige flake.nix ou le chemin."
        ),
        "lock.hash_impossible": (
            "Impossible de calculer le hash nix du dépôt nixpick (nix absent ?)."
        ),
        "lock.coherent": "flake.lock cohérent avec {name} ({short}…).",
        "lock.diverged_volatile": (
            "flake.lock diverge de l'arbre nixpick, mais seuls des fichiers "
            "volatils (.git, caches) ont bougé depuis le lock — sources "
            "inchangées, aucune action nécessaire.\n"
            "      lock : {locked}\n"
            "      actuel : {current}"
        ),
        "lock.stale": (
            "flake.lock périmé pour l'input nixpick : hash de chemin divergent "
            "depuis le dernier lock.\n"
            "      lock : {locked}\n"
            "      actuel : {current}\n"
            "      → {hint}"
        ),
        # ── rebuild_runner.py ────────────────────────────────
        "rb.empty_cmd": (
            "rebuild_command vide — configure config.toml "
            "ou NIXPICK_REBUILD_COMMAND."
        ),
        "rb.no_tty": (
            "Rebuild non lancé : pas de terminal interactif.\n"
            "  {cmd}\n"
            "Utilise : nixpick rebuild --yes"
        ),
        "rb.confirm": "Lancer le rebuild ?\n  {cmd}\n[o/N] ",
        "rb.term_invalid": (
            "NIXPICK_REBUILD_TERMINAL={term} introuvable — "
            "repli sur le terminal détecté."
        ),
        "rb.no_term": (
            "Rebuild terminal : aucun émulateur trouvé "
            "(kitty, foot, alacritty, wezterm)."
        ),
        "rb.manual": "Lance manuellement : {cmd}",
        "rb.hints_title": "\n— Aide nixpick (relis l'erreur Nix ci-dessus) —",
        "rb.hints_untracked": "  • Fichiers non suivis par Git :",
        "rb.hints_tracked": (
            "  • Fichier « not tracked by Git » : le flake ne voit que ce qui "
            "est dans git — ex. git -C {root} add dotfiles/…/fichier"
        ),
        "rb.hints_nar": (
            "  • Si le message cite « NAR hash mismatch » et nixpick :"
        ),
        "rb.hints_path_note": (
            "  • Input path nixpick : mets à jour flake.lock après "
            "changement du code."
        ),
        # ── sync_runner.py ───────────────────────────────────
        "sync.install_failed": "nix profile install : {err}",
        "sync.install_exit": (
            "nix profile install a quitté avec le code {code} "
            "(relis la sortie Nix ci-dessus)."
        ),
        "sync.no_nix": "nix introuvable — installe Nix puis relance.",
        "sync.empty_list": "Rien à installer : aucun paquet listé.",
        "sync.list_failed": "nix profile list : {err}",
        "sync.unreadable": "Impossible de lire le profil Nix.",
        "sync.uptodate": "Profil à jour : tout ce qui est listé est installé.",
        "sync.no_tty": (
            "Sync non lancé : pas de terminal interactif.\n"
            "  {cmd}\n"
            "Utilise : nixpick sync --yes"
        ),
        "sync.confirm": "Installer dans le profil ?\n  {cmd}\n[o/N] ",
        "sync.confirm_upgrade": "Mettre à jour dans le profil ?\n  {cmd}\n[o/N] ",
        "sync.confirm_both": (
            "Installer et mettre à jour dans le profil ?\n"
            "  {install}\n"
            "  {upgrade}\n[o/N] "
        ),
        "sync.upgraded": "Profil mis à jour : {refs}",
        "sync.upgrade_failed": "nix profile upgrade a quitté avec le code {code}.",
        "sync.upgrade_failed_os": "nix profile upgrade : {err}",
        "sync.installed": "Installé : {refs}",
        # ── fix_git_runner.py ────────────────────────────────
        "git.no_flake": (
            "Pas de flake NixOS détecté (packages_file hors arbre flake)."
        ),
        "git.no_repo": "{root} : pas de dépôt git — fix-git impossible.",
        "git.inventory": "Fichiers non suivi(s) à ajouter à {top} ({n}) :",
        "git.inventory_more": "  … et {n} autre(s).",
        "git.no_tty": (
            "fix-git non lancé : pas de terminal interactif.\n"
            "  {cmd}\n"
            "Utilise : nixpick fix-git --yes"
        ),
        "git.confirm": "Ajouter ces {n} fichier(s) ? [o/N] ",
        "git.exit_code": "git add a quitté avec le code {code}.",
        "git.added": "{n} fichier(s) ajoutés au suivi git.",
        "git.next": (
            "Étape suivante : git commit (si tu veux versionner), "
            "puis nixpick rebuild"
        ),
        # ── config.py ────────────────────────────────────────
        "cfg.bad_suffix": "packages_file doit être un fichier .nix, reçu : {path}",
        "cfg.bad_type": "packages_file doit être une chaîne (chemin .nix)",
        "cfg.bad_anchor": "packages_anchor doit être une chaîne non vide",
        "cfg.bad_rebuild": (
            "rebuild_command doit être une chaîne ou une liste d'arguments"
        ),
        "cfg.rebuild_empty": "rebuild_command ne peut pas être vide",
        "cfg.bad_lang": "langue inconnue : {code!r}",
        "cfg.bad_toml": "{path} : TOML invalide — {err} (compare avec config.example.toml).",
        "cfg.unreadable": "{path} illisible — {err}",
        # ── tui.py ───────────────────────────────────────────────────
        "tui.footer_add": "ajouter",
        "tui.footer_remove": "retirer",
        "tui.footer_config": "config",
        "tui.footer_nav": "nav",
        "tui.footer_hide": "masquer ●",
        "tui.footer_dry": "simu",
        "tui.footer_bg": "fond",
        "tui.footer_index": "index",
        "tui.footer_help": "aide",
        "tui.footer_quit": "quitter",
        "tui.help_type": "cherche tout de suite (comme fzf)",
        "tui.help_navigate": "navigue sans quitter la recherche",
        "tui.help_nextprev": "suivant / précédent (depuis la recherche)",
        "tui.help_page": "d'un écran de résultats",
        "tui.help_enter": "ajouter le paquet surligné",
        "tui.help_x": "retirer — au focus liste (sinon ^X)",
        "tui.help_l": "catalogue — au focus liste (sinon ^L)",
        "tui.help_tab": "aller à la liste, puis x l i d t q",
        "tui.help_esc": "vider la recherche, puis quitter",
        "tui.help_jk": "naviguer (quand la liste a le focus)",
        "tui.help_help": "aide",
        "tui.help_rebuild": "reconstruire l'index",
        "tui.help_hide": "masquer ● (i : focus liste)",
        "tui.help_dry": "mode simulation (d : focus liste)",
        "tui.help_bg": "fond transparent (t : focus liste)",
        "tui.help_quit": "quitter — au focus liste (sinon esc)",
        "tui.help_title": "  raccourcis",
        "tui.help_colors": (
            "Couleurs : section [colors] dans ~/.config/nixpick/config.toml"
        ),
        "tui.help_themes": "(voir docs/THEMES.md sur GitHub).",
        "tui.help_term1": (
            "Transparence réelle = mode ANSI (comme superfile) + Kitty :"
        ),
        "tui.help_term2": (
            "dans ~/.config/kitty/kitty.conf → background_opacity 0.85"
        ),
        "tui.help_term3": (
            "Puis Ctrl+T ou t. Un nixos-rebuild n'est jamais lancé seul."
        ),
        "tui.help_more": "… +{n} lignes (README § TUI — raccourcis)",
        "tui.index_corrupt": (
            "index illisible (~/.cache/nixpick/index.json) "
            "— Ctrl+R pour le reconstruire"
        ),
        "tui.index_io": "index inaccessible : {err} — Ctrl+R pour réessayer",
        "tui.index_nix": "échec de nix — Ctrl+R pour réessayer",
        "tui.index_unknown": (
            "chargement de l'index impossible : {err} — Ctrl+R pour réessayer"
        ),
        "tui.index_report": " — À signaler : {url}",
        "tui.search_placeholder": "chercher un paquet…",
        "tui.detail_title": " détail ",
        "tui.preview_title": " aperçu ",
        "tui.flag_dry": "simu",
        "tui.flag_transparent": "transp.",
        "tui.flag_no_hidden": "sans installés",
        "tui.flag_catalog": "catalogue config",
        "tui.count_k": "{n}k paquets",
        "tui.count_n": "{n} paquets",
        "tui.count_loading": "index…",
        "tui.age": " · {age:.0f} j",
        "tui.list_title": "résultats",
        "tui.hint_short": "tape encore 1 caractère pour lancer la recherche",
        "tui.hint_none": "aucun résultat pour « {query} »",
        "tui.hint_unavailable": "index indisponible — Ctrl+R pour le reconstruire",
        "tui.loading": "chargement de l'index…",
        "tui.suggest": "essaie : {items}",
        "tui.detail_short_body": (
            "Au moins 2 caractères pour lancer la recherche "
            "(évite de scanner tout nixpkgs)."
        ),
        "tui.detail_empty_name": "rien trouvé",
        "tui.detail_empty_body": (
            "Essaie un mot plus court, ou Ctrl+R pour rafraîchir l'index."
        ),
        "tui.detail_idle_body": (
            "Tape un nom d'application.\n"
            "↑↓ pour parcourir · ↵ pour ajouter · ? pour l'aide"
        ),
        "tui.detail_desc_missing": "description…",
        "tui.detail_meta_installed": "  ·  déjà dans la config",
        "tui.detail_hint_installed": (
            "déjà dans packages.nix   ·  ctrl+x retirer  ·  ↵ n'ajoute pas"
        ),
        "tui.detail_hint_dry": "↵  simuler l'ajout (rien ne sera écrit)",
        "tui.detail_hint_add": "↵  ajouter à packages.nix",
        "tui.toast_rebuilding": "Reconstruction déjà en cours…",
        "tui.state_hidden": "masqués",
        "tui.state_shown": "affichés",
        "tui.toast_hide": "Paquets déjà installés {state}.",
        "tui.toast_catalog": (
            "Catalogue packages.nix — x pour retirer, esc pour quitter le mode."
        ),
        "tui.toast_back_search": "Retour à la recherche nixpkgs.",
        "tui.toast_dry": "Simulation {onoff}.",
        "tui.toast_transparent": (
            "Fond transparent (ANSI). Kitty : background_opacity dans kitty.conf."
        ),
        "tui.toast_opaque": "Fond opaque (thème couleur).",
        "tui.toast_not_installed": (
            "{attr} n'est pas dans packages.nix — rien à retirer."
        ),
        "tui.toast_already": "Déjà dans packages.nix — [x] pour retirer.",
        "tui.toast_dry_nothing": "Simulation : rien n'a été écrit.",
        "tui.toast_no_rights": "Pas les droits sur {path}.",
        "tui.toast_added_rebuild": "Ajouté.  apply : {cmd}",
        "tui.toast_added_sync": (
            "Ajouté.  → `nixpick sync` pour installer dans ton profil"
        ),
        "tui.toast_created": "Fichier créé : {path}.  {msg}",
        "tui.toast_removed": "Retiré.  apply : {cmd}",
        "tui.stale": "Index vieux de {age:.0f} j — Ctrl+R pour reconstruire",
        "tui.too_small": (
            "terminal {w}×{h} : {req} requis — agrandir la fenêtre pour continuer"
        ),
        "tui.confirm_remove_title": "Retirer de la config",
        "tui.confirm_add_title": "Confirmer l'ajout",
        "tui.confirm_dry": "simulation — le fichier ne sera pas modifié",
        "tui.confirm_remove_mode": "suppression dans environment.systemPackages",
        "tui.confirm_add_mode": "écriture dans environment.systemPackages",
        "tui.confirm_yes": "confirmer",
        "tui.confirm_or": " ou ",
        "tui.confirm_no": "annuler",
        "tui.basket_added": "+ {attr} — panier : {n}",
        "tui.basket_removed": "{attr} retiré du panier — {n} restant(s)",
        "tui.basket_title": "Ajouter {n} paquets",
        "tui.basket_more": "… et {n} autre(s)",
        "tui.basket_done": "{n} ajouté(s)",
        "tui.basket_skipped": ", {n} déjà listé(s)",
        "tui.basket_failed": ", {n} échec(s) : {msg}",
        "tui.basket_dry": "Simulation : {n} ajout(s), rien n'écrit.",
        "tui.yanked": "Copié : {attr}",
        "tui.no_clipboard": (
            "Presse-papiers indisponible (wl-copy, xclip ou xsel requis)."
        ),
        "tui.list_title_padded": " résultats ",
        "tui.list_title_zero": " résultats · 0 ",
        "tui.list_title_count": " résultats · {n} ",
        "tui.settings_title": "Paramètres",
        "tui.settings_lang": "Langue",
        "tui.settings_transparent": "Fond transparent",
        "tui.settings_file": "Fichier packages",
        "tui.settings_on": "oui",
        "tui.settings_off": "non",
        "tui.settings_hint": "↑↓ naviguer · ↵ appliquer · esc fermer",
        "tui.settings_edit_hint": "↵ valider · esc annuler",
        "tui.settings_lang_set": "Langue : {lang}",
        "tui.settings_saved": "Fichier packages : {path}",
        "tui.settings_save_failed": "Sauvegarde impossible : {err}",
        # ── errors.py ────────────────────────────────────────────────
        "err.timeout": "Opération trop longue — réessaie (Ctrl+R pour l'index).",
        "err.corrupt_index": (
            "Index corrompu — supprime ~/.cache/nixpick/index.json ou Ctrl+R."
        ),
        "err.missing_binary": "Binaire introuvable : {name} — installe-le.",
        "err.cache_io": (
            "Cache inaccessible — vérifie l'espace disque et les droits de ~/.cache."
        ),
        "err.sigkill": (
            "Processus tué (SIGKILL) — probablement mémoire insuffisante "
            "(évaluer nixpkgs demande plusieurs Go). Libère de la RAM et réessaie."
        ),
        "err.no_channel": (
            "nixpkgs introuvable — ajoute un channel : "
            "nix-channel --add https://nixos.org/channels/nixos-unstable nixpkgs "
            "&& nix-channel --update."
        ),
        "err.untracked_git": (
            "Fichiers non suivis par Git — lance nixpick fix-git."
        ),
    },
    ENGLISH: {
        # ── messages.py ──────────────────────────────────────────────
        "rofi.confirm_add": "Confirm add",
        "rofi.confirm_remove": "Confirm removal",
        "rofi.cancel": "Cancel",
        "rofi.rebuild_now": "\U000f040a Run rebuild",
        "rofi.rebuild_later": "Later",
        "rofi.fix_git": "\U000f02a2 Fix Git (fix-git)",
        "rofi.sync_now": "Install via sync",
        "cli.cancelled": "Aborted.",
        "cli.saved": "Backup: {path}",
        "cli.apply_rebuild": "To apply: nixpick rebuild",
        "cli.apply_sync": "To install: nixpick sync",
        "cli.apply_sync_detail": "  (nix profile install nixpkgs#… of the listed ones)",
        "cli.success_rebuild": "Apply with: nixpick rebuild\n({cmd})",
        "cli.success_sync": "Install with: nixpick sync",
        "cli.saved_body": "Backup: {path}\n{how}",
        "rofi.search_too_short": (
            "Type at least 2 characters.\n"
            "Try a nixpkgs package or attribute name."
        ),
        "rofi.index_title": "nixpick — index",
        "rofi.index_error": (
            "{detail}\nRebuild the index: nixpick --build-index-only"
        ),
        "rofi.not_found": (
            'Nothing found for "{term}".\n'
            "Try another term or check the spelling."
        ),
        "rofi.permission_denied": (
            "No write permission on {path}.\n"
            "Check permissions or set NIXPICK_PACKAGES_FILE."
        ),
        "rofi.dry_run_title": "nixpick (dry-run)",
        "rofi.dry_run_remove": (
            "{attr} would have been removed — no changes on disk."
        ),
        "rofi.dry_run_add": (
            "{attr} would have been added — no changes on disk."
        ),
        "rofi.removed_title": "nixpick · {attr} removed",
        "rofi.added_title": "nixpick · {attr} added",
        # ── cli.py ───────────────────────────────────────────────────
        "cli.remove_planned": "Planned removal in {path}:",
        "cli.dry_run_nothing": "\n--dry-run mode: nothing written.",
        "cli.confirm_remove": "\nRemove it? [y/N] ",
        "cli.no_rights": "No write permission on {path}.",
        "cli.removed": "Removed.",
        "cli.removed_hint_profile": (
            "Removed from the list. To uninstall from the profile: "
            "nix profile remove {attr}"
        ),
        "cli.confirm_rebuild": "\nRun nixpick rebuild now? [y/N] ",
        "cli.fix_then_rebuild": (
            "\nRun: nixpick fix-git --yes   then   nixpick rebuild"
        ),
        "cli.nothing_found": "Nothing found for \"{term}\".",
        "cli.choose": "\nWhich one? [1-{n}, Enter to cancel] ",
        "cli.invalid_choice": "Invalid choice.",
        "cli.add_planned": "Planned change in {path}:",
        "cli.confirm_write": "\nWrite it? [y/N] ",
        "cli.added": "Added.",
        "cli.file_created": "File created: {path}",
        "cli.confirm_install": (
            "\nInstall nixpkgs#{attr} into your profile? [y/N] "
        ),
        "cli.install_failed": (
            "Add succeeded, but installation failed (code {code})."
        ),
        # ── doctor.py ────────────────────────────────────────────────
        "doc.title": "nixpick diagnostics",
        "doc.label_packages": "Packages file",
        "doc.pkg_will_create": (
            "{path} does not exist yet (will be created on first add)."
        ),
        "doc.pkg_writable_parent": (
            "{path} does not exist yet (parent directory is writable)."
        ),
        "doc.pkg_unwritable": (
            "{path} not found and the parent directory is not writable."
        ),
        "doc.pkg_unreadable": "{path} unreadable.",
        "doc.pkg_readonly": "{path} exists but is not writable.",
        "doc.pkg_ok": "{path} present and writable.",
        "doc.label_index": "Index cache",
        "doc.index_missing": (
            "No index in {parent} "
            "(run nixpick --build-index-only or open the TUI)."
        ),
        "doc.index_present": "Index present ({name}), age {age} d.",
        "doc.index_stale": (
            " Older than {days} d — refresh advised (nixpick --refresh)."
        ),
        "doc.label_lock": "Edit lock",
        "doc.lock_none": "No lock file (.nixpick.lock).",
        "doc.lock_idle": (
            "{name} present but idle (no edit in progress)."
        ),
        "doc.lock_active": (
            "Active lock on {name} — "
            "a nixpick session may be editing the file."
        ),
        "doc.lock_untestable": "Cannot test the lock: {err}",
        "doc.label_nixenv": "nix-env",
        "doc.nixenv_ok": "nix-env found in PATH.",
        "doc.nixenv_noenv": (
            "nix-env missing — required for the index (nix-env -qaP). "
            "Install the classic Nix profile or enable nix-command + nix-env."
        ),
        "doc.nixenv_nonix": (
            "Nix missing from PATH — required for the index and descriptions."
        ),
        "doc.label_rofi": "rofi (optional)",
        "doc.rofi_ok": "rofi found (for nixpick --rofi).",
        "doc.rofi_missing": "rofi missing — only needed with nixpick --rofi.",
        "doc.label_flakelock": "flake.lock (nixpick input)",
        "doc.label_flakegit": "Git flake (tracked files)",
        "doc.label_rebuild": "Rebuild command",
        "doc.rebuild_empty": (
            "rebuild_command empty — set config.toml "
            "or NIXPICK_REBUILD_COMMAND."
        ),
        "doc.rebuild_ok": "After add or remove: {cmd}",
        "doc.rebuild_no_nixos": (
            " — not applicable outside NixOS (apply with `nixpick sync`)."
        ),
        "doc.report_failures": "{n} point(s) to fix.",
        "doc.report_ok": "All looks good.",
        "doc.why_invalid": "Invalid attribute: {attr}",
        "doc.why_missing": "Configured file not found: {path}",
        # ── engine.py ────────────────────────────────────────────────
        "eng.nix_missing": (
            "{cmd} not found. Install Nix (see README § Outside NixOS)."
        ),
        "eng.timeout": "{cmd} exceeded {timeout} s.",
        "eng.file_missing": "{path} not found.",
        "eng.file_missing_why": "{path} not found ({err}).",
        "eng.invalid_attr": "Invalid attribute name: {attr!r}",
        "eng.undo_none": "No last operation recorded.",
        "eng.undo_invalid": "Last operation invalid or unreadable.",
        "eng.undo_other_file": (
            "The last operation concerns another file "
            "({recorded}), not {target}."
        ),
        "eng.undo_bad_path": "Last operation path invalid.",
        "eng.undo_no_backup": "Last operation has no associated backup.",
        "eng.undo_backup_missing": "Backup not found: {path}",
        "eng.undo_backup_mismatch": (
            "The backup does not match the target file {target}."
        ),
        "eng.undo_no_rights": "No write permission on {target}.",
        "eng.undo_impossible": "Restore impossible: {err}",
        "eng.undo_add": "add",
        "eng.undo_remove": "removal",
        "eng.undo_done": (
            "File restored: {target} "
            "(undoing the {verb} of {attr})."
        ),
        "eng.restored": "restored from backup",
        "eng.not_restored": "NOT restored",
        "eng.invalid_after_modify": (
            "{path} invalid after modification ({state}).{detail} "
            "Detail: {err}"
        ),
        "eng.already_listed": "{attr} is already in environment.systemPackages.",
        "eng.already_listed_commit": "{attr} is already listed.",
        "eng.block_missing": (
            "Block « {anchor} » missing, multiple or in an unsupported form. "
            "Expected format: anchor = with pkgs; [ … ];"
        ),
        "eng.block_unbalanced": (
            "End of « {anchor} » block not found or unbalanced Nix block."
        ),
        "eng.line_missing": "Line not found for {attr}",
        "eng.build_start": "Building the nixpkgs index (~20 s)…",
        "eng.build_done": "{n} packages indexed.",
        "eng.stale_rebuild": "Index {age:.0f} days old, rebuilding…",
        "eng.unreadable": "Unreadable index ({err}), rebuilding…",
        # ── nixpick.py ───────────────────────────────────────────────
        "app.interrupted": "Interrupted.",
        "app.report_bug": "\nReport this bug: {url}",
        "app.error": "nixpick: {err}",
        "app.desc": "Search nixpkgs and edit environment.systemPackages.",
        "app.help_doctor": "check config, cache, tools, Git flake and flake.lock (read-only nix/git)",
        "app.help_doctor_json": "JSON output (structured checks)",
        "app.help_rebuild": "run the configured rebuild command (confirmed)",
        "app.help_yes": "skip confirmation",
        "app.help_yes_script": "skip confirmation (useful in scripts)",
        "app.help_terminal": "open an emulator (kitty, foot) for sudo / output",
        "app.help_dry_run": "print the command without running it",
        "app.help_fix_git": "git add untracked (??) files of the NixOS flake repo",
        "app.help_fix_git_dry": "print the git command without running it",
        "app.help_sync": "install listed-but-missing packages into the Nix profile (outside NixOS)",
        "app.help_sync_dry": "print the nix command without running it",
        "app.help_sync_upgrade": "also upgrade listed packages already installed",
        "app.help_print_config": "print the target file and rebuild command, then quit",
        "app.help_term": "search in CLI mode (otherwise open the TUI)",
        "app.help_refresh": "rebuild the nixpkgs index at startup",
        "app.help_dryrun": "simulation: do not write packages.nix",
        "app.help_transparent": "TUI: transparent background (like superfile)",
        "app.help_opaque": "TUI: opaque background (ignore the config)",
        "app.help_tui": "force the TUI even with a search term",
        "app.help_rofi": "search via Rofi (glass bar)",
        "app.help_build_index": "rebuild the index then quit (no TUI)",
        "app.help_remove": "remove a package from environment.systemPackages (with the CLI term)",
        "app.help_list": "list attributes already in environment.systemPackages",
        "app.help_list_json": "with --list-installed: one JSON line (attrs, count, packages_file, index_age_days)",
        "app.help_undo": "restore packages.nix from the last backup (no rebuild)",
        "app.help_why": "tell whether an attribute is in the configured packages file",
        "app.help_print": "print the best attr on stdout (composable: scripts, agents)",
        "app.remove_needs_term": (
            "nixpick: --remove needs a term "
            "(e.g. nixpick --remove firefox)."
        ),
        # ── rebuild_runner.py ────────────────────────────────
        "rb.empty_cmd": (
            "rebuild_command empty — set config.toml "
            "or NIXPICK_REBUILD_COMMAND."
        ),
        "rb.no_tty": (
            "Rebuild not started: no interactive terminal.\n"
            "  {cmd}\n"
            "Use: nixpick rebuild --yes"
        ),
        "rb.confirm": "Run the rebuild?\n  {cmd}\n[y/N] ",
        "rb.term_invalid": (
            "NIXPICK_REBUILD_TERMINAL={term} not found — "
            "falling back to the detected terminal."
        ),
        "rb.no_term": (
            "Terminal rebuild: no emulator found "
            "(kitty, foot, alacritty, wezterm)."
        ),
        "rb.manual": "Run manually: {cmd}",
        "rb.hints_title": "\n— nixpick help (see the Nix error above) —",
        "rb.hints_untracked": "  • Files not tracked by Git:",
        "rb.hints_tracked": (
            "  • \u201cnot tracked by Git\u201d file: the flake only sees what "
            "is in git — e.g. git -C {root} add dotfiles/…/file"
        ),
        "rb.hints_nar": (
            "  • If the message mentions \u201cNAR hash mismatch\u201d and nixpick:"
        ),
        "rb.hints_path_note": (
            "  • nixpick path input: update flake.lock after "
            "code changes."
        ),
        # ── sync_runner.py ───────────────────────────────────
        "sync.install_failed": "nix profile install: {err}",
        "sync.install_exit": (
            "nix profile install exited with code {code} "
            "(see the Nix output above)."
        ),
        "sync.no_nix": "nix not found — install Nix and retry.",
        "sync.empty_list": "Nothing to install: no packages listed.",
        "sync.list_failed": "nix profile list: {err}",
        "sync.unreadable": "Cannot read the Nix profile.",
        "sync.uptodate": "Profile up to date: everything listed is installed.",
        "sync.no_tty": (
            "Sync not started: no interactive terminal.\n"
            "  {cmd}\n"
            "Use: nixpick sync --yes"
        ),
        "sync.confirm": "Install into the profile?\n  {cmd}\n[y/N] ",
        "sync.confirm_upgrade": "Upgrade in the profile?\n  {cmd}\n[y/N] ",
        "sync.confirm_both": (
            "Install and upgrade in the profile?\n"
            "  {install}\n"
            "  {upgrade}\n[y/N] "
        ),
        "sync.upgraded": "Profile upgraded: {refs}",
        "sync.upgrade_failed": "nix profile upgrade exited with code {code}.",
        "sync.upgrade_failed_os": "nix profile upgrade: {err}",
        "sync.installed": "Installed: {refs}",
        # ── fix_git_runner.py ────────────────────────────────
        "git.no_flake": (
            "No NixOS flake detected (packages_file outside the flake tree)."
        ),
        "git.no_repo": "{root}: not a git repo — fix-git impossible.",
        "git.inventory": "Untracked file(s) to add in {top} ({n}):",
        "git.inventory_more": "  … and {n} more.",
        "git.no_tty": (
            "fix-git not started: no interactive terminal.\n"
            "  {cmd}\n"
            "Use: nixpick fix-git --yes"
        ),
        "git.confirm": "Add these {n} file(s)? [y/N] ",
        "git.exit_code": "git add exited with code {code}.",
        "git.added": "{n} file(s) added to git tracking.",
        "git.next": (
            "Next step: git commit (to version it), "
            "then nixpick rebuild"
        ),
        # ── config.py ────────────────────────────────────────
        "cfg.bad_suffix": "packages_file must be a .nix file, got: {path}",
        "cfg.bad_type": "packages_file must be a string (.nix path)",
        "cfg.bad_anchor": "packages_anchor must be a non-empty string",
        "cfg.bad_rebuild": (
            "rebuild_command must be a string or a list of arguments"
        ),
        "cfg.rebuild_empty": "rebuild_command cannot be empty",
        "cfg.bad_lang": "unknown language: {code!r}",
        "cfg.bad_toml": "{path}: invalid TOML — {err} (compare with config.example.toml).",
        "cfg.unreadable": "{path} unreadable — {err}",
        # ── flake_git.py / flake_lock.py ─────────────────────
        "git.status_unavailable": "git status unavailable: {err}",
        "git.status_failed": "git status failed (code {code}). {detail}",
        "git.paths_skipped": "Warning: {n} path(s) skipped (invalid name).",
        "git.no_flake_check": "No NixOS flake detected (Git check skipped).",
        "git.clean": (
            "Repo {top}: no untracked (??) files under the flake. "
            "Flake root: {rel}/"
        ),
        "git.untracked_head": (
            "{n} untracked file(s) under the flake — Nix cannot see them "
            "until they are in git:"
        ),
        "git.untracked_more": "      … and {n} more.",
        "git.untracked_all_included": (
            "      (command above includes all untracked files.)"
        ),
        "git.preflight_blocked": (
            "Rebuild blocked before launch: flake files are not tracked "
            "by Git.\n{detail}\n"
            "Then: nixpick fix-git   or   nixpick rebuild"
        ),
        "lock.no_root": (
            "No NixOS flake detected next to packages_file (check skipped)."
        ),
        "lock.unreadable": "flake.lock unreadable ({err}) — check skipped.",
        "lock.no_input": "No \u201cnixpick\u201d path input in flake.lock (check skipped).",
        "lock.points_missing": (
            "nixpick input points to {path} (missing). "
            "Fix flake.nix or the path."
        ),
        "lock.hash_impossible": (
            "Cannot compute the nix hash of the nixpick repo (nix missing?)."
        ),
        "lock.coherent": "flake.lock consistent with {name} ({short}).",
        "lock.diverged_volatile": (
            "flake.lock diverges from the nixpick tree, but only volatile "
            "files (.git, caches) changed since the lock — sources "
            "unchanged, no action needed.\n"
            "      lock: {locked}\n"
            "      current: {current}"
        ),
        "lock.stale": (
            "stale flake.lock for the nixpick input: divergent path hash "
            "since the last lock.\n"
            "      lock: {locked}\n"
            "      current: {current}\n"
            "      → {hint}"
        ),
        # ── tui.py ───────────────────────────────────────────────────
        "tui.footer_add": "add",
        "tui.footer_remove": "remove",
        "tui.footer_config": "config",
        "tui.footer_nav": "nav",
        "tui.footer_hide": "hide",
        "tui.footer_dry": "dry",
        "tui.footer_bg": "bg",
        "tui.footer_index": "index",
        "tui.footer_help": "help",
        "tui.footer_quit": "quit",
        "tui.help_type": "search instantly (like fzf)",
        "tui.help_navigate": "navigate without leaving search",
        "tui.help_nextprev": "next / previous (from search)",
        "tui.help_page": "by one results screen",
        "tui.help_enter": "add the highlighted package",
        "tui.help_x": "remove — list focused (else ^X)",
        "tui.help_l": "catalog — list focused (else ^L)",
        "tui.help_tab": "go to the list, then x l i d t q",
        "tui.help_esc": "clear search, then quit",
        "tui.help_jk": "navigate (when the list is focused)",
        "tui.help_help": "help",
        "tui.help_rebuild": "rebuild the index",
        "tui.help_hide": "hide (i: list focused)",
        "tui.help_dry": "dry-run mode (d: list focused)",
        "tui.help_bg": "transparent background (t: list focused)",
        "tui.help_quit": "quit — list focused (else esc)",
        "tui.help_title": "  shortcuts",
        "tui.help_colors": (
            "Colors: [colors] section in ~/.config/nixpick/config.toml"
        ),
        "tui.help_themes": "(see docs/THEMES.md on GitHub).",
        "tui.help_term1": (
            "True transparency = ANSI mode (like superfile) + Kitty:"
        ),
        "tui.help_term2": (
            "in ~/.config/kitty/kitty.conf → background_opacity 0.85"
        ),
        "tui.help_term3": (
            "Then Ctrl+T or t. nixos-rebuild is never run unattended."
        ),
        "tui.help_more": "… +{n} lines (README § TUI — shortcuts)",
        "tui.index_corrupt": (
            "unreadable index (~/.cache/nixpick/index.json) "
            "— Ctrl+R to rebuild"
        ),
        "tui.index_io": "index unreachable: {err} — Ctrl+R to retry",
        "tui.index_nix": "nix failed — Ctrl+R to retry",
        "tui.index_unknown": (
            "cannot load index: {err} — Ctrl+R to retry"
        ),
        "tui.index_report": " — Report at: {url}",
        "tui.search_placeholder": "search a package…",
        "tui.detail_title": " detail ",
        "tui.preview_title": " preview ",
        "tui.flag_dry": "dry",
        "tui.flag_transparent": "transp.",
        "tui.flag_no_hidden": "no installed",
        "tui.flag_catalog": "config catalog",
        "tui.count_k": "{n}k packages",
        "tui.count_n": "{n} packages",
        "tui.count_loading": "index…",
        "tui.age": " · {age:.0f} d",
        "tui.list_title": "results",
        "tui.hint_short": "type 1 more character to start searching",
        "tui.hint_none": "no results for \"{query}\"",
        "tui.hint_unavailable": "index unavailable — Ctrl+R to rebuild",
        "tui.loading": "loading the index…",
        "tui.suggest": "try: {items}",
        "tui.detail_short_body": (
            "At least 2 characters to start searching "
            "(avoids scanning all of nixpkgs)."
        ),
        "tui.detail_empty_name": "nothing found",
        "tui.detail_empty_body": (
            "Try a shorter word, or Ctrl+R to refresh the index."
        ),
        "tui.detail_idle_body": (
            "Type an application name.\n"
            "↑↓ to browse · ↵ to add · ? for help"
        ),
        "tui.detail_desc_missing": "description…",
        "tui.detail_meta_installed": "  ·  already in config",
        "tui.detail_hint_installed": (
            "already in packages.nix   ·  ctrl+x to remove  ·  ↵ won't add"
        ),
        "tui.detail_hint_dry": "↵  simulate the add (nothing will be written)",
        "tui.detail_hint_add": "↵  add to packages.nix",
        "tui.toast_rebuilding": "Rebuild already in progress…",
        "tui.state_hidden": "hidden",
        "tui.state_shown": "shown",
        "tui.toast_hide": "Already installed packages {state}.",
        "tui.toast_catalog": (
            "packages.nix catalog — x to remove, esc to leave."
        ),
        "tui.toast_back_search": "Back to nixpkgs search.",
        "tui.toast_dry": "Simulation {onoff}.",
        "tui.toast_transparent": (
            "Transparent background (ANSI). Kitty: background_opacity in kitty.conf."
        ),
        "tui.toast_opaque": "Opaque background (color theme).",
        "tui.toast_not_installed": (
            "{attr} is not in packages.nix — nothing to remove."
        ),
        "tui.toast_already": "Already in packages.nix — [x] to remove.",
        "tui.toast_dry_nothing": "Simulation: nothing was written.",
        "tui.toast_no_rights": "No permission on {path}.",
        "tui.toast_added_rebuild": "Added.  apply: {cmd}",
        "tui.toast_added_sync": (
            "Added.  → `nixpick sync` to install into your profile"
        ),
        "tui.toast_created": "File created: {path}.  {msg}",
        "tui.toast_removed": "Removed.  apply: {cmd}",
        "tui.stale": "Index {age:.0f} days old — Ctrl+R to rebuild",
        "tui.too_small": (
            "terminal {w}×{h}: {req} required — enlarge the window to continue"
        ),
        "tui.confirm_remove_title": "Remove from config",
        "tui.confirm_add_title": "Confirm add",
        "tui.confirm_dry": "simulation — the file will not be modified",
        "tui.confirm_remove_mode": "removal from environment.systemPackages",
        "tui.confirm_add_mode": "write to environment.systemPackages",
        "tui.confirm_yes": "confirm",
        "tui.confirm_or": " or ",
        "tui.confirm_no": "cancel",
        "tui.basket_added": "+ {attr} — basket: {n}",
        "tui.basket_removed": "{attr} removed from basket — {n} left",
        "tui.basket_title": "Add {n} packages",
        "tui.basket_more": "… and {n} more",
        "tui.basket_done": "{n} added",
        "tui.basket_skipped": ", {n} already listed",
        "tui.basket_failed": ", {n} failed: {msg}",
        "tui.basket_dry": "Simulation: {n} add(s), nothing written.",
        "tui.yanked": "Copied: {attr}",
        "tui.no_clipboard": (
            "Clipboard unavailable (needs wl-copy, xclip or xsel)."
        ),
        "tui.list_title_padded": " results ",
        "tui.list_title_zero": " results · 0 ",
        "tui.list_title_count": " results · {n} ",
        "tui.settings_title": "Settings",
        "tui.settings_lang": "Language",
        "tui.settings_transparent": "Transparent background",
        "tui.settings_file": "Packages file",
        "tui.settings_on": "yes",
        "tui.settings_off": "no",
        "tui.settings_hint": "↑↓ navigate · ↵ apply · esc close",
        "tui.settings_edit_hint": "↵ confirm · esc cancel",
        "tui.settings_lang_set": "Language: {lang}",
        "tui.settings_saved": "Packages file: {path}",
        "tui.settings_save_failed": "Cannot save: {err}",
        # ── errors.py ────────────────────────────────────────────────
        "err.timeout": "Operation too slow — retry (Ctrl+R for the index).",
        "err.corrupt_index": (
            "Corrupt index — delete ~/.cache/nixpick/index.json or Ctrl+R."
        ),
        "err.missing_binary": "Binary not found: {name} — install it.",
        "err.cache_io": (
            "Cache unreachable — check disk space and ~/.cache permissions."
        ),
        "err.sigkill": (
            "Process killed (SIGKILL) — likely out of memory "
            "(evaluating nixpkgs needs several GB). Free some RAM and retry."
        ),
        "err.no_channel": (
            "nixpkgs not found — add a channel: "
            "nix-channel --add https://nixos.org/channels/nixos-unstable nixpkgs "
            "&& nix-channel --update."
        ),
        "err.untracked_git": (
            "Untracked Git files — run nixpick fix-git."
        ),
    },
}
