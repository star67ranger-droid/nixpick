"""Interface TUI — OpenTUI (composants natifs, signaux réactifs).

Le plan suit le modèle d'un fuzzy-finder (telescope / fzf) : recherche
centrée en haut, hint d'état dessous, liste à gauche (colonnes sélection /
installé / nom / version) et panneau `` détail `` à droite, suggestions au
repos puis footer.

Remplace l'ancienne implémentation Textual. Le modèle (engine, config,
index) est inchangé : seul le rendu et le routage des touches changent.

Routage des touches — un seul handler global (``TuiApp.on_key``) fait la
mux, parce qu'OpenTUI n'acheminera jamais les touches vers un widget de
manière implicite :

* recherche focalisée → frappe déléguée au champ, raccourcis globaux
  (ctrl+*, flèches, pageup/down, ↵, esc, tab, F1, ?) interceptés avant ;
* liste focalisée → raccourcis monolettre (x, l, d, t, i, j, k, q, /).
"""

from __future__ import annotations

import asyncio
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from native_env import ensure_opentui_libs

ensure_opentui_libs()

from opentui import (  # noqa: E402
    Box,
    Dynamic,
    Input,
    Signal,
    Text,
    component,
    render,
    use_keyboard,
    use_on_resize,
    use_paste,
    use_renderer,
)
from opentui.structs import display_width  # noqa: E402
from opentui.text_utils import wrap_text  # noqa: E402

from config import (  # noqa: E402
    format_rebuild_command,
    is_nixos,
    load_transparent_background,
    save_language,
    save_packages_file,
    save_transparent_background,
)
from engine import (  # noqa: E402
    INDEX_STALE_NOTIFY_DAYS,
    TUI_RESULT_LIMIT,
    AddFailure,
    AddPlan,
    DescriptionCache,
    NixCommandError,
    NixSyntaxError,
    PackageIndex,
    RemoveFailure,
    RemovePlan,
    _sanitize_description,
    commit_add,
    commit_remove,
    index_age_days,
    list_installed_attrs,
    load_index,
    packages_file,
    plan_add,
    plan_remove,
    search_index,
)
from i18n import get_language, set_language, t  # noqa: E402
from messages import ISSUES_URL  # noqa: E402
from theme import (  # noqa: E402
    TuiColors,
    get_color_palette,
    load_color_palette,
    reset_color_palette_cache,
)

_SEARCH_DEBOUNCE = 0.22
_DESC_DEBOUNCE = 0.35


def _safe_when_small(key: str, ctrl: bool) -> bool:
    """Touches autorisées sous les seuils : navigation et sorties uniquement.

    On ne valide jamais une modale à l'aveugle derrière l'overlay
    « terminal trop petit » (ni ajout, ni retrait, ni rebuild d'index,
    ni toggle persistant).
    """
    if ctrl:
        return key == "c"  # quitter
    return key in (
        "escape",
        "up",
        "down",
        "pageup",
        "pagedown",
        "tab",
        "f1",
        "question_mark",
        "?",
    )
_ROWS_OVERHEAD = 8  # chrome(1) + recherche(3) + hint(1) + titre liste(1) + suggestions(1) + footer(1)
_SEARCH_MAX_WIDTH = 72  # la barre de recherche est centrée et bornée
_VERSION_COL = 12  # largeur de la colonne « version » (alignée à droite)
_SUGGESTIONS = "firefox · neovim · kitty · htop"
# Sous ces seuils, le plan fixe (8 lignes hors liste) n'a plus de place et la
# liste disparaît sans explication : on affiche plutôt un message explicite.
_MIN_UI_WIDTH = 40
_MIN_UI_HEIGHT = 12

_FOOTER_KEYS = (
    ("↵", "tui.footer_add"),
    # Au focus recherche (le défaut), `x` / `l` / `q` seraient tapés dans la
    # requête : on annonce les variantes `^` (ctrl) et `esc`, qui marchent quel
    # que soit le focus. Notation `^X` = ctrl+x, comme en less / tmux.
    ("^X", "tui.footer_remove"),
    ("^L", "tui.footer_config"),
    ("↑↓", "tui.footer_nav"),
    ("^I", "tui.footer_hide"),
    ("^D", "tui.footer_dry"),
    ("^T", "tui.footer_bg"),
    ("^R", "tui.footer_index"),
    ("?", "tui.footer_help"),
    ("esc", "tui.footer_quit"),
)

_HELP_KEYS = (
    ("taper", "tui.help_type"),
    ("↑ ↓", "tui.help_navigate"),
    ("ctrl+n / p", "tui.help_nextprev"),
    ("pageup / down", "tui.help_page"),
    ("↵", "tui.help_enter"),
    ("x", "tui.help_x"),
    ("l", "tui.help_l"),
    ("tab", "tui.help_tab"),
    ("esc", "tui.help_esc"),
    ("j k", "tui.help_jk"),
    ("F1 / ?", "tui.help_help"),
    ("ctrl+r", "tui.help_rebuild"),
    ("i / ctrl+i", "tui.help_hide"),
    ("d / ctrl+d", "tui.help_dry"),
    ("t / ctrl+t", "tui.help_bg"),
    ("q", "tui.help_quit"),
)


@dataclass
class ResultRow:
    attr: str
    version: str
    description: str = ""


def _ellipsis(text: str, max_len: int = 68) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _index_error_message(err: BaseException) -> str:
    """Message affichable pour un échec de chargement de l'index.

    Toute exception doit finir ici : une seule catchée laissait la TUI bloquée
    sur l'écran de chargement, sans le moindre indice à l'écran.
    """
    if isinstance(err, json.JSONDecodeError):
        return t("tui.index_corrupt")
    if isinstance(err, OSError):
        return t("tui.index_io", err=err)
    if isinstance(err, NixCommandError):
        return str(err) or t("tui.index_nix")
    return t("tui.index_unknown", err=err)


def _line(text: str, fg: Any = None, *, bold: bool = False) -> Text:
    """Une ligne de texte à hauteur fixe : pas de repli, pas de chevauchement.

    Sans ``wrap_mode="none"`` + ``height=1`` + ``flex_shrink=0``, une ligne trop
    longue se replie sur 2 rangées et, dans une boîte à hauteur fixe, yoga
    comprime ses frères jusqu'à les superposer.
    """
    return Text(text, fg=fg, bold=bold, wrap_mode="none", height=1, flex_shrink=0)


def _row(*parts: tuple[str, Any, bool], **kwargs: Any) -> Box:
    """Ligne horizontale de segments stylés — ``Text(Span…)`` ne rend pas.

    Chaque segment reçoit une ``width`` explicite : sans elle, yoga mesure au
    mot et tronque les segments (espaces initiaux perdus, largeur sous-évaluée).
    """
    return Box(
        *(
            Text(
                text,
                fg=fg,
                bold=bold,
                width=display_width(text),
                wrap_mode="none",
                flex_shrink=0,
            )
            for text, fg, bold in parts
        ),
        height=1,
        flex_direction="row",
        flex_shrink=0,
        **kwargs,
    )


def _split_widths(width: int) -> tuple[int, int]:
    """Largeurs (liste, détail) du plan principal — source unique de vérité.

    ``listing + detail`` doit tenir dans ``width - 2`` (padding horizontal de
    la rangée) : sinon le rendu, qui se calque sur ce tuple, dessine plus large
    que le conteneur réel et la dernière colonne part sous le bord droit.
    """
    available = max(14, width - 2)
    detail = min(44, max(20, available * 40 // 100))
    listing = available - detail
    if listing < 16:
        # Sous ~40 colonnes, on reprend au détail plutôt qu'à la liste.
        listing = min(16, max(4, available - 12))
        detail = available - listing
    return max(1, listing), max(1, detail)


def _footer_text(c: TuiColors, width: int) -> Any:
    """Ligne du footer, tronquée à la largeur disponible.

    ``?`` et ``esc`` sont réservés en priorité : ce sont les sorties de secours.
    """
    budget = max(20, width - 2)
    essential = {"?", "esc"}
    entries = [(key, t(label_key)) for key, label_key in _FOOTER_KEYS]
    reserved = sum(
        display_width(key) + display_width(f" {label}") + 3
        for key, label in entries
        if key in essential
    )
    chosen: list[tuple[str, str]] = []
    used = 0
    deferred: list[tuple[str, str]] = []
    for key, label in entries:
        cost = display_width(key) + display_width(f" {label}") + (3 if chosen else 0)
        if key in essential:
            deferred.append((key, label))
            continue
        if used + cost + reserved <= budget:
            chosen.append((key, label))
            used += cost
    for key, label in deferred:
        cost = display_width(key) + display_width(f" {label}") + (3 if chosen else 0)
        if used + cost > budget:
            break
        chosen.append((key, label))
        used += cost

    parts: list[tuple[str, Any, bool]] = []
    for index, (key, label) in enumerate(chosen):
        if index:
            parts.append(("   ", c.text_muted, False))
        parts.append((key, c.accent, True))
        parts.append((f" {label}", c.text_muted, False))
    return _row(*parts)


def _help_lines(c: TuiColors) -> list[Any]:
    lines: list[Any] = [
        _row(
            ("nixpick", c.primary, True), (t("tui.help_title"), c.text_muted, False)
        ),
        _line(""),
    ]
    for key, label_key in _HELP_KEYS:
        padded = f"{key:<14}"
        lines.append(
            _row((f"  {padded}", c.accent, True), (t(label_key), c.text, False))
        )
    lines.append(_line(""))
    lines.append(_line(t("tui.help_colors"), c.text_muted))
    lines.append(_line(t("tui.help_themes"), c.text_muted))
    lines.append(_line(t("tui.help_term1"), c.text_muted))
    lines.append(_line(t("tui.help_term2"), c.text_muted))
    lines.append(_line(t("tui.help_term3"), c.text_muted))
    return lines


def _diff_lines(context_lines: list[str], sign: str, c: TuiColors) -> list[Any]:
    rows: list[Any] = []
    for raw in context_lines:
        line = raw.rstrip()
        if line.startswith(sign):
            body = line[1:].strip()
            color = c.success if sign == "+" else c.danger
            if sign == "+" and "#" in body:
                attr, comment = body.split("#", 1)
                rows.append(
                    _row(
                        ("+ ", color, True),
                        (_ellipsis(attr.strip(), 60), c.text, True),
                        (f"  # {_ellipsis(comment.strip(), 48)}", c.text_muted, False),
                    )
                )
            else:
                rows.append(
                    _row(
                        (f"{sign} ", color, True),
                        (_ellipsis(body, 66), c.text, False),
                    )
                )
        else:
            rows.append(_line(f"  {_ellipsis(line.strip(), 66)}", c.text_muted))
    return rows


class TuiApp:
    """État, logique et régions réactives de l'interface (aucun rendu direct)."""

    def __init__(
        self,
        refresh: bool = False,
        dry_run: bool = False,
        transparent: bool | None = None,
    ) -> None:
        self.refresh_on_start = refresh

        # modèle
        self.pkg_index: PackageIndex | None = None
        self.version_by_attr: dict[str, str] = {}
        self.desc_cache = DescriptionCache()
        self.installed: set[str] = set()
        self.detail_state = Signal("idle")
        self.last_error: BaseException | None = None

        # signaux de rendu
        self.query = Signal("")
        self.rows: Signal = Signal([])
        self.shown: Signal = Signal([])
        self.cursor = Signal(0)
        self.rows_title = Signal(t("tui.list_title_padded"))
        self.empty_hint = Signal("")
        self.focus = Signal("search")
        self.dry_run = Signal(bool(dry_run))
        self.hide_installed = Signal(False)
        self.catalog = Signal(False)
        self.transparent = Signal(
            load_transparent_background() if transparent is None else bool(transparent)
        )
        self.loading = Signal(True)
        self.status = Signal("chargement de l'index…")
        self.index_failed = Signal(False)
        self.rev = Signal(0)
        self.modal: Signal = Signal(None)
        self.toast: Signal = Signal(None)
        self.toast_level = Signal("info")
        # panier multi-sélection : attr -> description (commentaire à l'ajout)
        self.basket: dict[str, str] = {}
        # menu paramètres : sélection, édition du chemin
        self.settings_choice = 0
        self.settings_editing = False
        self.settings_draft = ""
        self.settings_current = ""
        self.dims = Signal((80, 24))

        # générateurs / minuteries
        self._search_generation = 0
        self._desc_generation = 0
        self._index_generation = 0
        self._last_search_query = ""
        self._search_seq = 0
        self._toast_seq = 0
        self._window_start = 0

        # exécution asynchrone : tout passe par la file, vidée à chaque frame
        self._queue: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self._timers: list[tuple[float, int, Callable[[], None]]] = []
        self._timer_seq = 0
        self._timers_lock = threading.Lock()

        # rendu
        self._input: Input | None = None
        self._settings_input: Input | None = None
        self._renderer: Any = None

    # ── boucle utilitaire ──────────────────────────────────────────────────

    def bind_renderer(self, renderer: Any) -> None:
        if self._renderer is renderer:
            return
        self._renderer = renderer
        renderer.set_frame_callback(self.tick)
        self.dims.set((renderer.width, renderer.height))

    def attach_input(self, value: Input) -> None:
        self._input = value

    def attach_settings_input(self, value: Input) -> None:
        self._settings_input = value

    def post(self, fn: Callable[[], None]) -> None:
        """Planifie ``fn`` sur le thread du rendu (frame suivante)."""
        self._queue.put(fn)

    def call_later(self, delay: float, fn: Callable[[], None]) -> None:
        with self._timers_lock:
            self._timer_seq += 1
            self._timers.append((time.monotonic() + delay, self._timer_seq, fn))

    def tick(self, _delta: float = 0.0) -> None:
        while True:
            try:
                job = self._queue.get_nowait()
            except queue.Empty:
                break
            self._run_safely(job)

        now = time.monotonic()
        with self._timers_lock:
            due = [t for t in self._timers if t[0] <= now]
            self._timers = [t for t in self._timers if t[0] > now]
        for _, _, job in sorted(due, key=lambda item: item[1]):
            self._run_safely(job)

    def _run_safely(self, job: Callable[[], None]) -> None:
        try:
            job()
        except Exception as err:  # noqa: BLE001 — une erreur ne doit pas tuer la boucle
            self.last_error = err

    def start(self) -> None:
        self.installed = list_installed_attrs()
        age = index_age_days()
        if age is not None and age > INDEX_STALE_NOTIFY_DAYS:
            self.notify(
                t("tui.stale", age=age), timeout=8
            )
        self.load_index_worker(refresh=self.refresh_on_start)

    # ── index ──────────────────────────────────────────────────────────────

    def load_index_worker(self, refresh: bool) -> None:
        self._index_generation += 1
        generation = self._index_generation

        def work() -> None:
            # Une exception non attrapée laisserait `loading` bloqué à True :
            # l'écran de chargement ne s'effacerait jamais et aucun message
            # ne s'afficherait (régression UX-02 de l'audit). Le message est
            # figé *avant* le `post` : `err` est effacé en fin de bloc except.
            try:
                raw = load_index(refresh=refresh, on_status=self._post_status)
                if generation != self._index_generation:
                    return  # un refresh plus récent a pris le relais
                pkg_index = PackageIndex.from_dict(raw)
            except Exception as err:  # noqa: BLE001 — tout échec doit être signalé
                message = _index_error_message(err)
                # NixCommandError = panne routinière documentée (pas de channel,
                # OOM, timeout) : pas d'URL. Le reste est inattendu → signalable.
                reportable = not isinstance(err, NixCommandError)
                self.post(
                    lambda m=message, r=reportable: self._on_index_error(m, r)
                )
                return
            if generation != self._index_generation:
                return
            self.post(lambda: self._on_index_ready(pkg_index))

        self.loading.set(True)
        threading.Thread(target=work, daemon=True, name="nixpick-index").start()

    def _post_status(self, message: str) -> None:
        self.post(lambda: self._on_status(message))

    def _on_status(self, message: str) -> None:
        self.loading.set(True)
        self.status.set(message)

    def _on_index_error(self, message: str, reportable: bool = True) -> None:
        self.loading.set(False)
        self.status.set("")
        self.index_failed.set(True)
        self.rev_bump()
        if reportable:
            message = f"{message}{t('tui.index_report', url=ISSUES_URL)}"
        self.notify(message, level="error")

    def _on_index_ready(self, pkg_index: PackageIndex) -> None:
        self.pkg_index = pkg_index
        self.version_by_attr = {row.attr: row.version for row in pkg_index.rows}
        self.loading.set(False)
        self.status.set("")
        self.index_failed.set(False)
        query = self._input.value if self._input else ""
        if self.catalog.peek() and not query.strip():
            self._rebuild_list()
        elif len(query.strip()) >= 2:
            self._schedule_search(query)

    def action_refresh_index(self) -> None:
        # Pas de pile-up : un rebuild déjà en cours ignore la demande (le
        # worker orphelin, lui, finit son nix-env sans appliquer le résultat).
        if self.loading.peek():
            self.notify(t("tui.toast_rebuilding"), timeout=2)
            return
        self.load_index_worker(refresh=True)

    # ── recherche ──────────────────────────────────────────────────────────

    def on_query_input(self, value: str) -> None:
        self.query.set(value)
        self._search_seq += 1
        seq = self._search_seq
        self.call_later(_SEARCH_DEBOUNCE, lambda: self._schedule_search_if(seq, value))

    def on_paste(self, event: Any) -> None:
        """Colle le presse-papiers dans la recherche (bracketed paste)."""
        text = " ".join(str(getattr(event, "text", "") or "").split())
        if not text or self._input is None or self.modal.peek() is not None:
            return
        if self.focus.peek() != "search":
            self._set_focus("search")
        self._input.insert_text(text)
        self.on_query_input(self._input.value)

    def _schedule_search_if(self, seq: int, value: str) -> None:
        if seq != self._search_seq:
            return
        self._schedule_search(value)

    def set_query(self, value: str) -> None:
        if self._input is not None:
            self._input.value = value
        self.query.set(value)
        self._search_seq += 1
        self._schedule_search(value)

    def _schedule_search(self, query: str) -> None:
        q = query.strip()
        if q == self._last_search_query:
            return
        if len(q) < 2:
            self._search_generation += 1
            self._last_search_query = q
            self.rows.set([])
            self._rebuild_list(query)
            return

        self._search_generation += 1
        generation = self._search_generation

        def work() -> None:
            if not self.pkg_index or generation != self._search_generation:
                return
            results = search_index(self.pkg_index, query, limit=TUI_RESULT_LIMIT)
            if generation != self._search_generation:
                return
            rows = [ResultRow(attr=attr, version=version) for attr, version in results]
            self.post(lambda: self._apply_results(rows, generation, query))

        threading.Thread(target=work, daemon=True, name="nixpick-search").start()

    def _apply_results(
        self, rows: list[ResultRow], generation: int, query: str
    ) -> None:
        if generation != self._search_generation:
            return
        self._last_search_query = query.strip()
        self.rows.set(rows)
        self._rebuild_list(query)
        self._prefetch_descriptions(rows)

    def _prefetch_descriptions(self, rows: list[ResultRow]) -> None:
        attrs = [row.attr for row in rows[:12] if not row.description]
        attrs = [attr for attr in attrs if not self.desc_cache.get(attr)]
        if not attrs:
            return

        def work() -> None:
            self.desc_cache.fetch_many(attrs)
            self.post(self.rev_bump)

        threading.Thread(target=work, daemon=True, name="nixpick-desc-batch").start()

    def _rebuild_list(self, query: str | None = None) -> None:
        if query is None:
            query = self._input.value if self._input else ""
        q = query.strip()
        self._window_start = 0

        if not q:
            if self.catalog.peek():
                self._fill_catalog()
                return
            self.shown.set([])
            self.rows_title.set(t("tui.list_title_padded"))
            self.empty_hint.set("")
            self.detail_state.set("idle")
            self.cursor.set(0)
            self.rev_bump()
            return

        if len(q) < 2:
            self.shown.set([])
            self.rows_title.set(t("tui.list_title_padded"))
            self.empty_hint.set("")
            self.detail_state.set("short")
            self.cursor.set(0)
            self.rev_bump()
            return

        hide = self.hide_installed.peek()
        visible = [
            row
            for row in self.rows.peek()
            if not (hide and row.attr in self.installed)
        ]
        self.shown.set(visible)
        self.cursor.set(0)
        self.empty_hint.set("")
        if not visible:
            self.rows_title.set(t("tui.list_title_zero"))
            self.detail_state.set("empty")
        else:
            self.rows_title.set(t("tui.list_title_count", n=len(visible)))
            self.detail_state.set("row")
        self.rev_bump()

    def _fill_catalog(self) -> None:
        attrs = sorted(self.installed)
        rows = [
            ResultRow(attr=attr, version=self.version_by_attr.get(attr, ""))
            for attr in attrs
        ]
        self.rows.set(rows)
        self.shown.set(rows)
        self.cursor.set(0)
        if not rows:
            self.rows_title.set(" config · 0 ")
            self.empty_hint.set("aucun paquet dans packages.nix")
            self.detail_state.set("idle")
        else:
            self.rows_title.set(f" config · {len(rows)} ")
            self.empty_hint.set("")
            self.detail_state.set("row")
        self.rev_bump()

    # ── descriptions ───────────────────────────────────────────────────────

    def schedule_desc(self, attr: str) -> None:
        if self.desc_cache.get(attr):
            return
        self._desc_generation += 1
        generation = self._desc_generation
        self.call_later(
            _DESC_DEBOUNCE, lambda: self._fetch_one_desc(attr, generation)
        )

    def _fetch_one_desc(self, attr: str, generation: int) -> None:
        if generation != self._desc_generation:
            return

        def work() -> None:
            if generation != self._desc_generation:
                return
            text = self.desc_cache.fetch_one(attr)
            if text and generation == self._desc_generation:
                self.post(lambda: self._apply_one_desc(attr, text))

        threading.Thread(target=work, daemon=True, name="nixpick-desc").start()

    def _apply_one_desc(self, attr: str, text: str) -> None:
        for row in self.rows.peek():
            if row.attr == attr:
                row.description = text
        for row in self.shown.peek():
            if row.attr == attr:
                row.description = text
        self.rev_bump()

    # ── navigation ─────────────────────────────────────────────────────────

    def current_row(self) -> ResultRow | None:
        rows = self.shown.peek()
        index = self.cursor.peek()
        if 0 <= index < len(rows):
            return rows[index]
        return None

    def move(self, delta: int) -> None:
        rows = self.shown.peek()
        if not rows:
            return
        index = self.cursor.peek()
        self.cursor.set(max(0, min(len(rows) - 1, index + delta)))

    def _set_focus(self, target: str) -> None:
        if self.focus.peek() == target:
            return
        self.focus.set(target)
        if self._input is not None:
            self._input.focused = target == "search"

    def action_focus_search(self) -> None:
        self._set_focus("search")

    def action_clear_search(self) -> None:
        self.set_query("")
        self._set_focus("search")

    def action_cycle_focus(self) -> None:
        self._set_focus("list" if self.focus.peek() == "search" else "search")

    def action_escape(self) -> None:
        if self.modal.peek() is not None:
            self.resolve_modal(False)
            return
        if self.query.peek():
            self.set_query("")
            self._set_focus("search")
            return
        if self.catalog.peek():
            self.catalog.set(False)
            self._rebuild_list()
            self._set_focus("search")
            return
        self.quit()

    def quit(self) -> None:
        if self._renderer is not None:
            self._renderer.stop()

    # ── bascules ───────────────────────────────────────────────────────────

    def action_toggle_hide_installed(self) -> None:
        self.hide_installed.set(not self.hide_installed.peek())
        self._rebuild_list()
        state = t("tui.state_hidden") if self.hide_installed.peek() else t("tui.state_shown")
        self.notify(t("tui.toast_hide", state=state), timeout=2)

    def action_toggle_catalog(self) -> None:
        enabled = not self.catalog.peek()
        self.catalog.set(enabled)
        if enabled:
            self.set_query("")
            self._fill_catalog()
            self.notify(t("tui.toast_catalog"), timeout=3)
        else:
            self._rebuild_list()
            self.notify(t("tui.toast_back_search"), timeout=2)

    def action_toggle_dry_run(self) -> None:
        self.dry_run.set(not self.dry_run.peek())
        self.rev_bump()
        self.notify(t("tui.toast_dry", onoff="on" if self.dry_run.peek() else "off"), timeout=2)

    def action_toggle_transparent(self) -> None:
        enabled = not self.transparent.peek()
        self.transparent.set(enabled)
        save_transparent_background(enabled)
        self.rev_bump()
        hint = (
            t("tui.toast_transparent")
            if enabled
            else t("tui.toast_opaque")
        )
        self.notify(hint, timeout=4)

    def action_help(self) -> None:
        self._open_modal({"kind": "help"})

    def action_settings(self) -> None:
        self.settings_choice = 0
        self.settings_editing = False
        self.settings_draft = ""
        self._open_modal({"kind": "settings"})

    def _settings_key(self, key: str, event: Any) -> None:
        if self.settings_editing:
            if key == "escape":
                self.settings_editing = False
                self.rev_bump()
                return
            if key in ("return", "enter"):
                self._settings_validate_path()
                return
            inp = self._settings_input
            editable = key in ("backspace", "delete", "left", "right", "home", "end") or (
                len(key) == 1 and not getattr(event, "alt", False)
            )
            if inp is not None and editable and inp.handle_key(event):
                self.settings_draft = inp.value
                self.rev_bump()
            return
        if key == "escape":
            self.resolve_modal(False)
            return
        if key in ("up", "k"):
            self.settings_choice = (self.settings_choice - 1) % 3
            self.rev_bump()
            return
        if key in ("down", "j", "tab"):
            self.settings_choice = (self.settings_choice + 1) % 3
            self.rev_bump()
            return
        if key in ("return", "enter"):
            self._settings_activate()
            return

    def _settings_activate(self) -> None:
        if self.settings_choice == 0:
            self._settings_cycle_language()
        elif self.settings_choice == 1:
            self.action_toggle_transparent()
        else:
            try:
                current = str(packages_file())
            except ValueError:
                current = ""
            # Champ vide (la frappe remplace, au lieu de s'ajouter) ; le
            # chemin actuel est mémorisé pour l'affichage ci-dessus.
            self.settings_draft = ""
            self.settings_current = current
            if self._settings_input is not None:
                self._settings_input.value = ""
                self._settings_input.focused = True
            self.settings_editing = True
            self.rev_bump()

    def _settings_cycle_language(self) -> None:
        new = "en" if get_language() == "fr" else "fr"
        try:
            save_language(new)
        except OSError as err:
            self.notify(t("tui.settings_save_failed", err=err), level="error")
            return
        set_language(new)
        self.rows_title.set(t("tui.list_title_padded"))
        self._rebuild_list()
        self.rev_bump()
        self.notify(t("tui.settings_lang_set", lang=new), timeout=3)

    def _settings_validate_path(self) -> None:
        try:
            saved = save_packages_file(self.settings_draft)
        except ValueError as err:
            self.notify(str(err), level="error", timeout=4)
            return
        self.settings_editing = False
        if self._settings_input is not None:
            self._settings_input.focused = False
        self.installed = list_installed_attrs()
        self._rebuild_list()
        self.rev_bump()
        self.notify(t("tui.settings_saved", path=saved), timeout=4)

    # ── modales ────────────────────────────────────────────────────────────

    def _open_modal(self, payload: dict[str, Any]) -> None:
        if self._input is not None:
            self._input.focused = False
        self.modal.set(payload)

    def resolve_modal(self, confirmed: bool) -> None:
        payload = self.modal.peek()
        self.modal.set(None)
        if self._input is not None:
            self._input.focused = self.focus.peek() == "search"
        if payload is None or not confirmed:
            return
        kind = payload.get("kind")
        if kind == "add":
            self._commit_add(payload["plan"], payload.get("row"))
        elif kind == "remove":
            self._commit_remove(payload["plan"], payload.get("row"))
        elif kind == "add_multi":
            self._commit_basket(payload["attrs"])

    # ── actions sur la config ──────────────────────────────────────────────

    @staticmethod
    def _clipboard_argv() -> list[str] | None:
        if shutil.which("wl-copy"):
            return ["wl-copy"]
        if shutil.which("xclip"):
            return ["xclip", "-selection", "clipboard"]
        if shutil.which("xsel"):
            return ["xsel", "--clipboard", "--input"]
        return None

    def action_yank(self) -> None:
        row = self.current_row()
        if row is None:
            return
        argv = self._clipboard_argv()
        if argv is None:
            self.notify(t("tui.no_clipboard"), level="warning", timeout=3)
            return
        try:
            subprocess.run(
                argv, input=row.attr, capture_output=True, text=True,
                timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            self.notify(t("tui.no_clipboard"), level="warning", timeout=3)
            return
        self.notify(t("tui.yanked", attr=row.attr), timeout=2)

    def action_toggle_basket(self) -> None:
        row = self.current_row()
        if row is None:
            return
        if row.attr in self.basket:
            del self.basket[row.attr]
            self.notify(
                t("tui.basket_removed", attr=row.attr, n=len(self.basket)),
                timeout=2,
            )
        else:
            self.basket[row.attr] = row.description
            self.notify(
                t("tui.basket_added", attr=row.attr, n=len(self.basket)),
                timeout=2,
            )
        self.rev_bump()

    def action_remove(self) -> None:
        row = self.current_row()
        if row is None:
            return
        if row.attr not in self.installed:
            self.notify(
                t("tui.toast_not_installed", attr=row.attr),
                level="warning",
                timeout=3,
            )
            return
        plan = plan_remove(row.attr)
        if isinstance(plan, RemoveFailure):
            self.notify(plan.message, level="warning")
            return
        self._open_modal({"kind": "remove", "plan": plan, "row": row})

    def action_install(self) -> None:
        if self.basket:
            self._open_modal({"kind": "add_multi", "attrs": sorted(self.basket)})
            return
        row = self.current_row()
        if row is None:
            return
        if row.attr in self.installed:
            self.notify(
                t("tui.toast_already"),
                level="warning",
                timeout=3,
            )
            return
        plan = plan_add(row.attr, row.description)
        if isinstance(plan, AddFailure):
            self.notify(plan.message, level="warning")
            return
        self._open_modal({"kind": "add", "plan": plan, "row": row})

    def _commit_basket(self, attrs: list[str]) -> None:
        if self.dry_run.peek():
            self.notify(t("tui.basket_dry", n=len(attrs)), timeout=4)
            self.basket.clear()
            self.rev_bump()
            return
        live = {row.attr: row.description for row in self.rows.peek()}
        ok = skipped = failed = 0
        first_err = ""
        for attr in attrs:
            plan = plan_add(attr, live.get(attr) or self.basket.get(attr, ""))
            if isinstance(plan, AddFailure):
                if plan.outcome.name == "ALREADY_LISTED":
                    skipped += 1
                else:
                    failed += 1
                    first_err = first_err or plan.message
                continue
            try:
                commit_add(plan, dry_run=False)
            except (PermissionError, LookupError, NixSyntaxError) as err:
                failed += 1
                first_err = first_err or str(err)
                continue
            ok += 1
        self.basket.clear()
        self.installed = list_installed_attrs()
        self._rebuild_list()
        self.rev_bump()
        msg = t("tui.basket_done", n=ok)
        if skipped:
            msg += t("tui.basket_skipped", n=skipped)
        if failed:
            msg += t("tui.basket_failed", n=failed, msg=first_err)
            self.notify(msg, level="error", timeout=8)
        else:
            self.notify(msg, timeout=6)

    def _commit_add(self, plan: AddPlan, row: ResultRow | None) -> None:
        if self.dry_run.peek():
            self.notify(t("tui.toast_dry_nothing"), timeout=3)
            return
        try:
            commit_add(plan, dry_run=False)
        except PermissionError:
            self.notify(t("tui.toast_no_rights", path=plan.packages_file), level="error")
            return
        except LookupError as err:
            self.installed = list_installed_attrs()
            self._rebuild_list()
            self.notify(str(err), level="warning", timeout=4)
            return
        except NixSyntaxError as err:
            self.notify(str(err), level="error", timeout=8)
            return
        self.installed = list_installed_attrs()
        self._rebuild_list()
        if is_nixos():
            msg = t("tui.toast_added_rebuild", cmd=format_rebuild_command())
        else:
            msg = t("tui.toast_added_sync")
        if plan.created_file:
            msg = t("tui.toast_created", path=plan.packages_file, msg=msg)
        self.notify(msg, timeout=6)

    def _commit_remove(self, plan: RemovePlan, row: ResultRow | None) -> None:
        if self.dry_run.peek():
            self.notify(t("tui.toast_dry_nothing"), timeout=3)
            return
        try:
            commit_remove(plan, dry_run=False)
        except PermissionError:
            self.notify(t("tui.toast_no_rights", path=plan.packages_file), level="error")
            return
        except LookupError as err:
            self.notify(str(err), level="error")
            return
        except NixSyntaxError as err:
            self.notify(str(err), level="error", timeout=8)
            return
        if row is not None:
            self.installed.discard(row.attr)
        self._rebuild_list()
        self.notify(t("tui.toast_removed", cmd=format_rebuild_command()), timeout=6)

    # ── notifications ──────────────────────────────────────────────────────

    def notify(self, message: str, level: str = "info", timeout: float = 3) -> None:
        self.toast_level.set(level)
        self.toast.set(message)
        self._toast_seq += 1
        seq = self._toast_seq
        self.call_later(timeout, lambda: self._clear_toast(seq))

    def _clear_toast(self, seq: int) -> None:
        if seq == self._toast_seq:
            self.toast.set(None)

    def rev_bump(self) -> None:
        self.rev.set(self.rev.peek() + 1)

    # ── routage des touches ────────────────────────────────────────────────

    def _too_small(self) -> bool:
        width, height = self.dims()
        return width < _MIN_UI_WIDTH or height < _MIN_UI_HEIGHT

    def on_key(self, event: Any) -> None:
        key = str(getattr(event, "key", "") or "")
        ctrl = bool(getattr(event, "ctrl", False))

        if self.modal.peek() is not None:
            # Modale ouverte sur terminal trop petit : seul esc annule.
            if self._too_small() and key != "escape":
                return
            self._modal_key(key, event)
            return
        if self._too_small() and not _safe_when_small(key, ctrl):
            return
        if ctrl:
            self._ctrl_key(key)
            return
        if key in ("f1", "question_mark", "?"):
            self.action_help()
            return
        if key == "escape":
            self.action_escape()
            return
        if key in ("return", "enter"):
            self.action_install()
            return
        if key in ("up", "down"):
            self.move(-1 if key == "up" else 1)
            return
        if key in ("pageup", "pagedown"):
            page = max(1, self.dims()[1] - _ROWS_OVERHEAD)
            self.move(page if key == "pagedown" else -page)
            return
        if key == "tab":
            self.action_cycle_focus()
            return
        # `ctrl+c` est traité plus haut par `if ctrl:` → `_ctrl_key` (qui
        # route "c" vers `quit`) : cette branche était donc morte.

        if self.focus.peek() == "list":
            self._list_key(key)
            return
        self._search_key(event, key)

    def _modal_key(self, key: str, event: Any) -> None:
        payload = self.modal.peek() or {}
        if payload.get("kind") == "help":
            if key in ("escape", "q", "?", "question_mark", "f1", "n", "return", "enter"):
                self.resolve_modal(False)
            return
        if payload.get("kind") == "settings":
            self._settings_key(key, event)
            return
        if key in ("escape", "n"):
            self.resolve_modal(False)
        elif key in ("return", "enter", "y"):
            self.resolve_modal(True)

    def _ctrl_key(self, key: str) -> None:
        if key == "n":
            self.move(1)
            return
        if key == "p":
            self.move(-1)
            return
        actions = {
            "d": self.action_toggle_dry_run,
            "i": self.action_toggle_hide_installed,
            "l": self.action_settings,
            "t": self.action_toggle_transparent,
            "r": self.action_refresh_index,
            "u": self.action_clear_search,
            "x": self.action_remove,
            "c": self.quit,
        }
        action = actions.get(key)
        if action is not None:
            action()

    def _list_key(self, key: str) -> None:
        actions: dict[str, Callable[[], None]] = {
            "j": lambda: self.move(1),
            "k": lambda: self.move(-1),
            "q": self.quit,
            "x": self.action_remove,
            "y": self.action_yank,
            " ": self.action_toggle_basket,
            "delete": self.action_remove,
            "l": self.action_toggle_catalog,
            "d": self.action_toggle_dry_run,
            "t": self.action_toggle_transparent,
            "i": self.action_toggle_hide_installed,
            "/": self.action_focus_search,
        }
        action = actions.get(key)
        if action is not None:
            action()

    def _search_key(self, event: Any, key: str) -> None:
        if self._input is None:
            return
        if key in ("backspace", "delete", "left", "right", "home", "end"):
            if self._input.handle_key(event):
                self.query.set(self._input.value)
                self.on_query_input(self._input.value)
            return
        if (
            len(key) == 1
            and not getattr(event, "alt", False)
            and self._input.handle_key(event)
        ):
            self.query.set(self._input.value)
            self.on_query_input(self._input.value)

    # ── régions réactives ──────────────────────────────────────────────────

    @staticmethod
    def _colors() -> TuiColors:
        return get_color_palette().tui

    def footer_region(self) -> list[Any]:
        c = self._colors()
        _ = self.rev()
        width, _ = self.dims()
        return [_footer_text(c, width - 2)]

    def chrome_region(self) -> list[Any]:
        c = self._colors()
        _ = self.rev()
        loading = self.loading()
        flags: list[str] = []
        if self.dry_run():
            flags.append(t("tui.flag_dry"))
        if self.transparent():
            flags.append(t("tui.flag_transparent"))
        if self.hide_installed():
            flags.append(t("tui.flag_no_hidden"))
        if self.catalog():
            flags.append(t("tui.flag_catalog"))

        index = self.pkg_index
        count_n = len(index) if index else 0
        count = (
            t("tui.count_k", n=count_n // 1000)
            if count_n >= 1000
            else (t("tui.count_n", n=count_n) if count_n else t("tui.count_loading"))
        )
        age = index_age_days()
        age_s = t("tui.age", age=age) if age is not None and not loading else ""

        parts: list[tuple[str, Any, bool]] = [
            ("nixpick", c.primary, True),
            (f"  {count}{age_s}", c.text_muted, False),
        ]
        if flags:
            parts.append(("  " + " · ".join(flags), c.accent_alt, False))
        return [_row(*parts)]

    def list_title_region(self) -> list[Any]:
        """Titre de la colonne gauche : « résultats · 12 ──── » (sans bordure)."""
        c = self._colors()
        _ = self.rev()
        width, _ = self.dims()
        list_w, _ = _split_widths(width)
        inner = max(12, list_w - 2)
        title = self.rows_title().strip() or t("tui.list_title")
        head = f" {title} "
        parts: list[tuple[str, Any, bool]] = [(head, c.text_muted, True)]
        pad = inner - display_width(head)
        if pad > 0:
            parts.append(("─" * pad, c.text_muted, False))
        return [_row(*parts)]

    def hint_region(self) -> list[Any]:
        """Ligne d'état sous la recherche (chargement, requête trop courte…)."""
        c = self._colors()
        _ = self.rev()
        width, _ = self.dims()
        if self.loading():
            return self._hint_line(self.status() or t("tui.loading"), c.warning, width)
        if self.index_failed():
            # Sans cette branche, on affichait « aucun résultat pour « x » » :
            # l'utilisateur croyait à une faute de frappe au lieu de réparer.
            return self._hint_line(
                t("tui.hint_unavailable"), c.danger, width
            )
        query = self.query().strip()
        if query and len(query) < 2:
            return self._hint_line(
                t("tui.hint_short"), c.text_muted, width
            )
        if query and not self.shown():
            return self._hint_line(t("tui.hint_none", query=query), c.text_muted, width)
        hint = self.empty_hint()
        return self._hint_line(hint, c.text_muted, width)

    @staticmethod
    def _hint_line(text: str, color: Any, width: int) -> list[Any]:
        if not text:
            return []
        return [_line(_ellipsis(text, max(8, width - 6)), color)]

    def suggestions_region(self) -> list[Any]:
        """Suggestions dim au repos (style telescope / fzf)."""
        c = self._colors()
        _ = self.rev()
        width, _ = self.dims()
        if self.query() or self.catalog() or self.loading():
            return []
        return [_line(_ellipsis(t("tui.suggest", items=_SUGGESTIONS), max(8, width - 6)), c.text_muted)]

    def rows_region(self) -> list[Any]:
        c = self._colors()
        _ = self.rev()
        rows = self.shown()
        current = self.cursor()
        hint = self.empty_hint()
        width, height = self.dims()
        list_w, _ = _split_widths(width)
        inner = max(12, list_w - 2)
        attr_w = max(4, inner - 4 - _VERSION_COL)
        visible = max(1, height - _ROWS_OVERHEAD)

        if not rows:
            if not hint:
                return []
            return [Box(_line(hint, c.text_muted), height=1, flex_shrink=0)]

        total = len(rows)
        start = self._window_start
        start = min(start, current)
        if current >= start + visible:
            start = current - visible + 1
        start = max(0, min(start, max(0, total - visible)))
        self._window_start = start

        boxes: list[Any] = []
        for index in range(start, min(total, start + visible)):
            row = rows[index]
            selected = index == current
            installed = row.attr in self.installed
            marker = "▸ " if selected else "  "
            if installed:
                dot, dot_color = "● ", c.success
            elif row.attr in self.basket:
                dot, dot_color = "+ ", c.accent
            else:
                dot, dot_color = "  ", c.text_muted
            name = _ellipsis(row.attr, attr_w)
            name += " " * max(0, attr_w - display_width(name))
            version = _ellipsis(row.version, _VERSION_COL - 1)
            version = " " * max(0, _VERSION_COL - display_width(version)) + version
            boxes.append(
                _row(
                    (marker, c.primary if selected else c.text_muted, selected),
                    (dot, dot_color, False),
                    (name, c.primary if selected else c.text, selected),
                    (version, c.text_muted, False),
                    background_color=c.list_highlight_bg if selected else None,
                )
            )
        return boxes

    def detail_region(self) -> list[Any]:
        c = self._colors()
        _ = self.rev()
        rows = self.shown()
        current = self.cursor()
        state = self.detail_state()

        if state == "row" and 0 <= current < len(rows):
            return self._detail_for_row(rows[current], c)

        if state == "short":
            name, meta = "…", ""
            body = t("tui.detail_short_body")
        elif state == "empty":
            name, meta = t("tui.detail_empty_name"), ""
            body = t("tui.detail_empty_body")
        else:
            name, meta = "nixpick", "nixpkgs → packages.nix"
            body = t("tui.detail_idle_body")

        return [
            _line(name, c.primary, bold=True),
            _line(meta, c.text_muted),
            _line(""),
            *self._detail_body(body, c),
            _line(""),
            _line("", c.success),
        ]

    def _detail_body(self, body: str, c: TuiColors) -> list[Any]:
        """Corps du panneau : découpé ici, en lignes de hauteur fixe.

        Un ``Text`` multi-lignes confié à yoga garde une mesure obsolète quand
        la réconciliation recopie ``_content`` sans invalider la mesure du
        nœud : les lignes restent alors figées à la hauteur du premier rendu.
        On découpe donc nous-mêmes, et on plafonne faute de quoi une longue
        description fait déborder la colonne et yoga comprime les lignes
        fixes (nom / méta / indice) jusqu'à les superposer.
        """
        width, height = self.dims()
        _, detail_w = _split_widths(width)
        inner = max(1, detail_w - 4)
        # Hauteur du plan principal : 30 − (chrome 1 + recherche 3 + hint 1
        # + suggestions 1 + footer 1) = 23 ; moins bordure/padding du panneau
        # (4) et lignes fixes autour du corps (5).
        budget = max(2, height - 16)
        lines = wrap_text(body or "description…", inner, "word")
        if len(lines) > budget:
            lines = lines[:budget]
            lines[-1] = _ellipsis(lines[-1], inner)
        return [_line(ln, c.text) for ln in lines]

    def _detail_for_row(self, row: ResultRow, c: TuiColors) -> list[Any]:
        installed = row.attr in self.installed
        meta = row.version + (t("tui.detail_meta_installed") if installed else "")
        cached = row.description or self.desc_cache.get(row.attr) or ""
        if cached:
            row.description = cached
        body = cached if cached else t("tui.detail_desc_missing")

        if installed:
            hint_text = t("tui.detail_hint_installed")
            hint_color = c.warning
        elif self.dry_run():
            hint_text = t("tui.detail_hint_dry")
            hint_color = c.warning
        else:
            hint_text = t("tui.detail_hint_add")
            hint_color = c.success

        inner = max(1, _split_widths(self.dims()[0])[1] - 4)
        self.schedule_desc(row.attr)
        return [
            _line(_ellipsis(row.attr, inner), c.primary, bold=True),
            _line(_ellipsis(meta, inner), c.text_muted),
            _line(""),
            *self._detail_body(body if body else t("tui.detail_desc_missing"), c),
            _line(""),
            _line(_ellipsis(hint_text, inner), hint_color),
        ]

    def toast_region(self) -> list[Any]:
        message = self.toast()
        if not message:
            return []
        c = self._colors()
        level = self.toast_level()
        color = {
            "error": c.danger,
            "warning": c.warning,
        }.get(level, c.text)
        screen_w, _ = self.dims()
        box_width = min(max(20, display_width(message) + 2), max(20, screen_w - 4))
        return [
            Box(
                Text(f" {message} ", fg=color, width=max(1, box_width - 2), wrap_mode="none"),
                background_color=c.surface_elevated,
                position="absolute",
                top=0,
                left=max(0, screen_w - box_width - 2),
                width=box_width,
                height=1,
                z_index=20,
                overflow="hidden",
            )
        ]

    def too_small_region(self) -> list[Any]:
        """Message bloquant quand le terminal est trop petit pour le plan."""
        width, height = self.dims()
        if width >= _MIN_UI_WIDTH and height >= _MIN_UI_HEIGHT:
            return []
        c = self._colors()
        message = _ellipsis(
            t(
                "tui.too_small",
                w=width,
                h=height,
                req=f"{_MIN_UI_WIDTH}×{_MIN_UI_HEIGHT}",
            ),
            max(20, width - 4),
        )
        return [
            Box(
                Box(
                    _line(message, c.warning),
                    background_color=c.surface,
                    padding_x=1,
                    flex_shrink=0,
                ),
                position="absolute",
                top=0,
                left=0,
                width=width,
                height=height,
                justify_content="center",
                align_items="center",
                z_index=40,
                background_color=c.background,
            )
        ]

    def modal_region(self) -> list[Any]:
        payload = self.modal()
        _ = self.rev()
        if payload is None:
            return []
        c = self._colors()
        width, height = self.dims()
        if payload.get("kind") == "help":
            inner = self._help_box(c, width, height)
        elif payload.get("kind") == "settings":
            inner = self._settings_box(c, width, height)
        elif payload.get("kind") == "add_multi":
            inner = self._confirm_multi_box(payload["attrs"], c, width, height)
        else:
            inner = self._confirm_box(payload, c, width, height)
        return [
            Box(
                inner,
                position="absolute",
                top=0,
                left=0,
                width=width,
                height=height,
                justify_content="center",
                align_items="center",
                z_index=10,
                overflow="hidden",
            )
        ]

    def _help_box(self, c: TuiColors, width: int, height: int) -> Box:
        # 72 → 68 utiles : la ligne « Couleurs : … » fait 62 colonnes.
        box_width = min(72, max(40, width - 4))
        # +4 : bordure (2) et padding vertical (2) — sinon la dernière ligne
        # se pose sur la bordure basse.
        max_box = max(8, height - 2)
        capacity = max(1, max_box - 4)
        lines = _help_lines(c)
        if len(lines) > capacity:
            # Sans troncature, la dernière ligne restait sur la bordure ou
            # disparaissait : on coupe proprement et on le dit.
            visible = lines[: capacity - 1]
            hidden = len(lines) - len(visible)
            visible.append(
                _line(t("tui.help_more", n=hidden), c.text_muted)
            )
            lines = visible
        box_height = len(lines) + 4
        return Box(
            *lines,
            width=box_width,
            height=box_height,
            background_color=c.surface_elevated,
            border=True,
            border_style="single",
            border_color=c.text_muted,
            padding_x=2,
            padding_y=1,
            overflow="hidden",
            flex_shrink=1,
        )

    def _settings_box(self, c: TuiColors, width: int, height: int) -> Box:
        box_width = min(78, max(44, width - 4))
        lang_value = "français" if get_language() == "fr" else "English"
        transp_value = (
            t("tui.settings_on") if self.transparent.peek() else t("tui.settings_off")
        )
        try:
            current_path = str(packages_file())
        except ValueError:
            current_path = ""
        rows = [
            (t("tui.settings_lang"), lang_value),
            (t("tui.settings_transparent"), transp_value),
            (t("tui.settings_file"), current_path),
        ]
        children: list[Any] = [
            _line(t("tui.settings_title"), c.primary, bold=True),
            _line(""),
        ]
        for index, (label, value) in enumerate(rows):
            selected = index == self.settings_choice and not self.settings_editing
            children.append(
                _row(
                    ("> " if selected else "  ", c.accent if selected else c.text_muted, selected),
                    (label, c.text if selected else c.text_muted, selected),
                    background_color=c.list_highlight_bg if selected else None,
                )
            )
            if index == 2 and self.settings_editing:
                children.append(
                    _row(
                        (f"    {_ellipsis(self.settings_current, max(8, box_width - 10))}", c.text_muted, False),
                    )
                )
                if self._settings_input is not None:
                    children.append(self._settings_input)
            else:
                children.append(
                    _row(
                        (f"    {_ellipsis(value, max(8, box_width - 10))}", c.text_muted, False),
                    )
                )
        children.append(_line(""))
        children.append(
            _line(
                t("tui.settings_edit_hint") if self.settings_editing else t("tui.settings_hint"),
                c.text_muted,
            )
        )
        return Box(
            *children,
            width=box_width,
            background_color=c.surface_elevated,
            border=True,
            border_style="single",
            border_color=c.text_muted,
            padding_x=2,
            padding_y=1,
            max_height=max(10, height - 2),
            overflow="hidden",
            flex_shrink=1,
        )

    @staticmethod
    def _confirm_keys_row(c: TuiColors) -> Any:
        return _row(
            ("y", c.success, True),
            (t("tui.confirm_or"), c.text_muted, False),
            ("↵", c.success, True),
            (f"  {t('tui.confirm_yes')}     ", c.text_muted, False),
            ("n", c.danger, True),
            (t("tui.confirm_or"), c.text_muted, False),
            ("esc", c.danger, True),
            (f"  {t('tui.confirm_no')}", c.text_muted, False),
        )

    def _confirm_multi_box(
        self, attrs: list[str], c: TuiColors, width: int, height: int
    ) -> Box:
        box_width = min(78, max(40, width - 4))
        content_width = max(20, box_width - 4)
        children: list[Any] = [
            _line(t("tui.basket_title", n=len(attrs)), c.text, bold=True),
            _line(""),
        ]
        for attr in attrs[:12]:
            children.append(_line(_ellipsis(attr, content_width), c.primary, bold=True))
        if len(attrs) > 12:
            children.append(_line(t("tui.basket_more", n=len(attrs) - 12), c.text_muted))
        children.append(_line(""))
        mode = (
            t("tui.confirm_dry")
            if self.dry_run.peek()
            else t("tui.confirm_add_mode")
        )
        children.append(_line(mode, c.warning))
        children.append(_line(""))
        children.append(self._confirm_keys_row(c))
        return Box(
            *children,
            width=box_width,
            background_color=c.surface_elevated,
            border=True,
            border_style="single",
            border_color=c.text_muted,
            padding_x=2,
            padding_y=1,
            max_height=max(10, height - 2),
            overflow="hidden",
            flex_shrink=1,
        )

    def _confirm_box(
        self, payload: dict[str, Any], c: TuiColors, width: int, height: int
    ) -> Box:
        plan = payload["plan"]
        removing = payload.get("kind") == "remove"
        title = t("tui.confirm_remove_title") if removing else t("tui.confirm_add_title")
        title_color = c.danger if removing else c.text
        dry = self.dry_run.peek()
        mode = (
            t("tui.confirm_dry")
            if dry
            else (
                t("tui.confirm_remove_mode")
                if removing
                else t("tui.confirm_add_mode")
            )
        )

        box_width = min(78, max(40, width - 4))
        content_width = max(20, box_width - 4)
        children: list[Any] = [
            _line(title, title_color),
            _line(""),
            _line(plan.attr, c.primary, bold=True),
            _line(str(plan.packages_file), c.text_muted),
            _line(mode, c.warning),
        ]
        description = getattr(plan, "description", "")
        if description:
            children.append(_line(""))
            # Description assainie (pas de \n) avant troncature : une meta
            # multiligne cassait la modale (ligne height=1, sans repli).
            children.append(
                _line(_ellipsis(_sanitize_description(description), content_width), c.text)
            )

        diff = _diff_lines(plan.context_lines, "-" if removing else "+", c)
        children.append(_line(""))
        children.append(
            Box(
                *diff,
                title=t("tui.preview_title"),
                border=True,
                border_style="single",
                border_color=c.danger if removing else c.text_muted,
                background_color=c.background,
                padding_x=1,
                max_height=12,
                flex_shrink=1,
                overflow="hidden",
            )
        )
        children.append(_line(""))
        children.append(self._confirm_keys_row(c))

        return Box(
            *children,
            width=box_width,
            background_color=c.surface_elevated,
            border=True,
            border_style="single",
            border_color=c.danger if removing else c.text_muted,
            padding_x=2,
            padding_y=1,
            max_height=max(8, height - 2),
            overflow="hidden",
            flex_shrink=1,
        )


def _make_app(app: TuiApp) -> Any:
    c = get_color_palette().tui

    def surface() -> str | None:
        return None if app.transparent() else c.surface

    def background() -> str | None:
        return None if app.transparent() else c.background

    def search_border() -> str:
        return c.primary if app.focus() == "search" else c.text_muted

    def search_width() -> int:
        width, _ = app.dims()
        return min(_SEARCH_MAX_WIDTH, max(24, width - 6))

    def detail_width() -> int:
        width, _ = app.dims()
        return _split_widths(width)[1]

    @component
    def NixPickApp() -> Any:
        renderer = use_renderer()
        app.bind_renderer(renderer)
        use_keyboard(app.on_key)
        use_paste(app.on_paste)
        use_on_resize(lambda width, height: app.dims.set((width, height)))

        search_input = Input(
            value=app.query.peek(),
            placeholder=t("tui.search_placeholder"),
            focused=True,
            height=1,
            flex_grow=1,
            fg=c.text,
            cursor_color=c.primary,
        )
        app.attach_input(search_input)
        settings_input = Input(
            value="",
            placeholder="",
            focused=False,
            height=1,
            flex_grow=1,
            fg=c.text,
            cursor_color=c.primary,
        )
        app.attach_settings_input(settings_input)
        app.start()

        return Box(
            # ── chrome : marque + compteurs + flags (1 ligne)
            Box(
                Dynamic(render=app.chrome_region),
                height=1,
                padding_x=1,
                flex_shrink=0,
                background_color=surface,
            ),
            # ── recherche centrée (barre unique, largeur bornée)
            Box(
                Box(
                    Text("> ", fg=c.primary, bold=True, width=2, wrap_mode="none", flex_shrink=0),
                    search_input,
                    border=True,
                    border_style="single",
                    border_color=search_border,
                    background_color=surface,
                    padding_x=1,
                    width=search_width,
                    height=3,
                    flex_direction="row",
                    align_items="center",
                    flex_shrink=0,
                ),
                height=3,
                flex_direction="row",
                justify_content="center",
                padding_x=1,
                flex_shrink=0,
            ),
            # ── hint centré sous la recherche
            Box(
                Dynamic(
                    render=app.hint_region,
                    flex_direction="row",
                    justify_content="center",
                ),
                height=1,
                padding_x=1,
                flex_shrink=0,
            ),
            # ── plan principal : liste à gauche, détail à droite
            Box(
                Box(
                    Box(
                        Dynamic(render=app.list_title_region),
                        height=1,
                        flex_shrink=0,
                    ),
                    Box(
                        Dynamic(
                            render=app.rows_region,
                            flex_direction="column",
                            min_height=0,
                            min_width=0,
                        ),
                        flex_grow=1,
                        flex_basis=0,
                        min_height=0,
                        min_width=0,
                        overflow="hidden",
                    ),
                    flex_direction="column",
                    flex_grow=1,
                    flex_basis=0,
                    min_height=0,
                    min_width=0,
                    padding_x=1,
                    overflow="hidden",
                    background_color=background,
                ),
                Box(
                    Dynamic(render=app.detail_region, flex_direction="column"),
                    title=t("tui.detail_title"),
                    border=True,
                    border_style="single",
                    border_color=c.detail_title,
                    background_color=surface,
                    padding_x=2,
                    padding_y=1,
                    width=detail_width,
                    min_height=0,
                    overflow="hidden",
                    flex_shrink=0,
                ),
                flex_direction="row",
                flex_grow=1,
                flex_basis=0,
                min_height=0,
                min_width=0,
                padding_x=1,
                background_color=background,
                overflow="hidden",
            ),
            # ── suggestions centrées (au repos seulement)
            Box(
                Dynamic(
                    render=app.suggestions_region,
                    flex_direction="row",
                    justify_content="center",
                ),
                height=1,
                padding_x=1,
                flex_shrink=0,
            ),
            # ── footer responsive centré
            Box(
                Dynamic(
                    render=app.footer_region,
                    flex_direction="row",
                    justify_content="center",
                ),
                height=1,
                padding_x=1,
                flex_shrink=0,
                background_color=surface,
            ),
            Dynamic(
                render=app.toast_region,
                position="absolute",
                top=0,
                left=0,
                width=lambda: app.dims()[0],
                height=lambda: app.dims()[1],
                z_index=20,
                flex_shrink=0,
            ),
            Dynamic(
                render=app.modal_region,
                position="absolute",
                top=0,
                left=0,
                width=lambda: app.dims()[0],
                height=lambda: app.dims()[1],
                z_index=30,
                flex_shrink=0,
            ),
            Dynamic(
                render=app.too_small_region,
                position="absolute",
                top=0,
                left=0,
                width=lambda: app.dims()[0],
                height=lambda: app.dims()[1],
                z_index=40,
                flex_shrink=0,
            ),
            flex_direction="column",
            height="100%",
            width="100%",
            flex_grow=1,
            background_color=background,
        )

    return NixPickApp


def apply_tui_theme() -> None:
    """Recharge la palette config.toml et régénère les thèmes Rofi."""
    from rofi_theme import sync_rofi_themes

    reset_color_palette_cache()
    palette = load_color_palette()
    sync_rofi_themes(palette)


def run_tui(
    refresh: bool = False,
    dry_run: bool = False,
    transparent: bool | None = None,
) -> int:
    try:
        apply_tui_theme()
    except ValueError as err:
        print(f"nixpick : {err}", file=sys.stderr)
        return 1
    app = TuiApp(refresh=refresh, dry_run=dry_run, transparent=transparent)
    try:
        asyncio.run(render(_make_app(app)))
    except KeyboardInterrupt:
        return 130
    if app.last_error is not None:
        print(f"nixpick : erreur interne TUI — {app.last_error}", file=sys.stderr)
        return 1
    return 0
