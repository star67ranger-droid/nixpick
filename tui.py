"""Interface TUI v2 — UX type fzf / superfile."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from config import load_transparent_background, save_transparent_background
from theme import TuiColors, get_color_palette, load_color_palette, reset_color_palette_cache
from tui_css import (
    build_app_css,
    build_confirm_add_css,
    build_confirm_remove_css,
)
from engine import (
    AddFailure,
    AddPlan,
    DescriptionCache,
    NixCommandError,
    PackageIndex,
    rebuild_command,
    RemoveFailure,
    RemovePlan,
    TUI_RESULT_LIMIT,
    commit_add,
    commit_remove,
    INDEX_STALE_NOTIFY_DAYS,
    index_age_days,
    list_installed_attrs,
    load_index,
    plan_add,
    plan_remove,
    search_index,
)


@dataclass
class ResultRow:
    attr: str
    version: str
    description: str = ""


# ─── Modales ─────────────────────────────────────────────────────────────────


def _ellipsis(text: str, max_len: int = 68) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _format_diff_markup(context_lines: list[str]) -> str:
    rows: list[str] = []
    for raw in context_lines:
        line = raw.rstrip()
        if line.startswith("+"):
            body = line[1:].strip()
            if "#" in body:
                attr, comment = body.split("#", 1)
                attr = attr.strip()
                comment = _ellipsis(comment.strip(), 52)
                rows.append(
                    f"[bold green]+[/] [bold]{attr}[/]  [dim]# {comment}[/]"
                )
            else:
                rows.append(f"[bold green]+[/] [bold]{_ellipsis(body)}[/]")
        else:
            rows.append(f"[dim]  {_ellipsis(line.strip())}[/]")
    return "\n".join(rows)


def _modal_actions_markup(c: TuiColors) -> str:
    return (
        f"[bold #{c.rich('success')}]y[/] ou [bold #{c.rich('success')}]↵[/]  confirmer     "
        f"[bold #{c.rich('danger')}]n[/] ou [bold #{c.rich('danger')}]esc[/]  annuler"
    )


class ConfirmAddModal(ModalScreen[bool]):
    """Modale de confirmation type lazygit : centrée, aperçu court, actions explicites."""

    CSS = ""

    BINDINGS = [
        Binding("y", "confirm", "Oui"),
        Binding("n", "dismiss", "Non"),
        Binding("escape", "dismiss", "Non"),
        Binding("enter", "confirm", "Oui", show=False),
    ]

    def __init__(self, plan: AddPlan, dry_run: bool, transparent: bool = False) -> None:
        super().__init__()
        self._plan = plan
        self._dry_run = dry_run
        self._transparent = transparent

    def on_mount(self) -> None:
        if self._transparent:
            self.add_class("transparent")

    def compose(self) -> ComposeResult:
        desc = _ellipsis(self._plan.description, 90) if self._plan.description else ""
        diff = _format_diff_markup(self._plan.context_lines)
        mode = (
            "[yellow]simulation[/] — le fichier ne sera pas modifié"
            if self._dry_run
            else "[dim]écriture dans[/] [bold]environment.systemPackages[/]"
        )

        with Vertical(id="confirm-box"):
            yield Static("Confirmer l'ajout", id="modal-title")
            yield Static(self._plan.attr, id="modal-attr")
            yield Static(str(self._plan.packages_file), id="modal-path")
            yield Static(mode, id="modal-badge")
            if desc:
                yield Static(desc, id="modal-desc")
            with Vertical(id="diff-panel") as panel:
                panel.border_title = " aperçu "
                yield Static(diff, id="diff")
            yield Static(
                _modal_actions_markup(get_color_palette().tui),
                id="modal-actions",
            )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_dismiss(self) -> None:
        self.dismiss(False)


class ConfirmRemoveModal(ModalScreen[bool]):
    """Retirer une entrée de environment.systemPackages."""

    CSS = ""

    BINDINGS = [
        Binding("y", "confirm", "Oui"),
        Binding("n", "dismiss", "Non"),
        Binding("escape", "dismiss", "Non"),
        Binding("enter", "confirm", "Oui", show=False),
    ]

    def __init__(self, plan: RemovePlan, dry_run: bool, transparent: bool = False) -> None:
        super().__init__()
        self._plan = plan
        self._dry_run = dry_run
        self._transparent = transparent

    def on_mount(self) -> None:
        if self._transparent:
            self.add_class("transparent")

    def compose(self) -> ComposeResult:
        diff_lines = []
        for raw in self._plan.context_lines:
            line = raw.rstrip()
            if line.startswith("-"):
                body = line[1:].strip()
                diff_lines.append(f"[bold red]-[/] [bold]{_ellipsis(body)}[/]")
            else:
                diff_lines.append(f"[dim]  {_ellipsis(line.strip())}[/]")
        diff = "\n".join(diff_lines)
        mode = (
            "[yellow]simulation[/] — le fichier ne sera pas modifié"
            if self._dry_run
            else "[dim]suppression dans[/] [bold]environment.systemPackages[/]"
        )

        with Vertical(id="confirm-box"):
            yield Static("Retirer de la config", id="modal-title")
            yield Static(self._plan.attr, id="modal-attr")
            yield Static(str(self._plan.packages_file), id="modal-path")
            yield Static(mode, id="modal-badge")
            with Vertical(id="diff-panel") as panel:
                panel.border_title = " aperçu "
                yield Static(diff, id="diff")
            yield Static(
                _modal_actions_markup(get_color_palette().tui),
                id="modal-actions",
            )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_dismiss(self) -> None:
        self.dismiss(False)


def _help_markup(c: TuiColors) -> str:
    a, p, alt = c.rich("accent"), c.rich("primary"), c.rich("accent_alt")
    return f"""\
[b #{alt}]nixpick[/]  [dim]raccourcis[/]

  [b #{a}]taper[/]              cherche tout de suite (comme fzf)
  [b #{a}]↑ ↓[/]                navigue sans quitter la recherche
  [b #{a}]↵[/]                  ajouter le paquet surligné
  [b #{a}]x[/]                  retirer (si ● déjà dans packages.nix)
  [b #{a}]l[/]                  catalogue des paquets déjà dans la config
  [b #{a}]tab[/]                aller à la liste / revenir à la recherche
  [b #{a}]esc[/]                vider la recherche, puis quitter
  [b #{a}]j k[/]                naviguer (quand la liste a le focus)
  [b #{a}]F1[/] / [b #{a}?[/]        aide
  [b #{a}]ctrl+r[/]            reconstruire l'index
  [b #{a}]i[/] / [b #{a}]ctrl+i[/]   masquer les paquets déjà dans la config
  [b #{a}]d[/] / [b #{a}]ctrl+d[/]   mode simulation
  [b #{a}]t[/] / [b #{a}]ctrl+t[/]   fond transparent
  [b #{a}]q[/]                  quitter

[dim]Couleurs : section [colors] dans ~/.config/nixpick/config.toml
(voir docs/THEMES.md sur GitHub).

Transparence réelle = mode ANSI (comme superfile) + Kitty :
dans ~/.config/kitty/kitty.conf → background_opacity 0.85
Puis Ctrl+T ou t. Un nixos-rebuild n'est jamais lancé seul.[/]
"""


class HelpModal(ModalScreen[None]):
    CSS = """
    HelpModal {
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Fermer"),
        Binding("q", "dismiss", "Fermer"),
        Binding("question_mark", "dismiss", "Fermer", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(_help_markup(get_color_palette().tui)),
            id="help-box",
        )

    def action_dismiss(self) -> None:
        self.dismiss(None)


# ─── App ─────────────────────────────────────────────────────────────────────


class NixPickApp(App[None]):
    TITLE = "nixpick"
    CSS = ""

    BINDINGS = [
        Binding("q", "quit", "Quitter", show=False),
        Binding("slash", "focus_search", "Rechercher", show=False),
        Binding("ctrl+u", "clear_search", "Vider", show=False),
        Binding("escape", "escape", "Échap", show=False, priority=True),
        Binding("down", "cursor_down", show=False, priority=True),
        Binding("up", "cursor_up", show=False, priority=True),
        Binding("j", "cursor_down_if_list", show=False),
        Binding("k", "cursor_up_if_list", show=False),
        Binding("tab", "cycle_focus", show=False, priority=True),
        Binding("enter", "install", "Ajouter", show=False, priority=True),
        Binding("f1", "help", show=False, priority=True),
        Binding("ctrl+r", "refresh_index", show=False, priority=True),
        Binding("ctrl+t", "toggle_transparent", show=False, priority=True),
        Binding("ctrl+d", "toggle_dry_run", show=False, priority=True),
        Binding("ctrl+i", "toggle_hide_installed", show=False, priority=True),
        Binding("ctrl+l", "toggle_installed_catalog", show=False, priority=True),
        Binding("x", "remove", "Retirer", show=False, priority=True),
        Binding("ctrl+x", "remove", show=False, priority=True),
        Binding("delete", "remove", show=False, priority=True),
    ]

    _SHORTCUT_KEYS = frozenset({"d", "t", "i", "l"})
    _MODIFIER_ONLY_KEYS = frozenset(
        {
            "left_control",
            "right_control",
            "left_alt",
            "right_alt",
            "left_shift",
            "right_shift",
            "left_meta",
            "right_meta",
            "shift",
            "control",
            "alt",
            "meta",
        }
    )

    def __init__(
        self,
        refresh: bool = False,
        dry_run: bool = False,
        transparent: bool | None = None,
    ) -> None:
        self._transparent = (
            transparent if transparent is not None else load_transparent_background()
        )
        super().__init__(ansi_color=self._transparent)
        self._refresh_on_start = refresh
        self._dry_run = dry_run
        self._hide_installed = False
        self._installed_catalog = False
        self._pkg_index: PackageIndex | None = None
        self._version_by_attr: dict[str, str] = {}
        self._desc_cache = DescriptionCache()
        self._installed: set[str] = set()
        self._rows: list[ResultRow] = []
        self._visible: list[ResultRow] = []
        self._search_timer = None
        self._desc_timer = None
        self._search_generation = 0
        self._desc_generation = 0
        self._last_search_query = ""
        self._loading = True

    def compose(self) -> ComposeResult:
        yield Static("", id="chrome")
        with Horizontal(id="search-row"):
            yield Static(">", id="search-icon")
            yield Input(placeholder="chercher un paquet…", id="search")
        with Horizontal(id="main"):
            results = OptionList(id="results")
            results.border_title = " résultats "
            yield results
            with VerticalScroll(id="detail-panel") as detail:
                detail.border_title = " détail "
                yield Label("nixpick", id="detail-name")
                yield Label("", id="detail-meta")
                yield Static(
                    "Commence à taper. Les flèches bougent la sélection\n"
                    "sans quitter la recherche — comme fzf.",
                    id="detail-body",
                )
                yield Static("", id="detail-hint")
        yield Static("", id="footerbar")

    def on_mount(self) -> None:
        self._installed = list_installed_attrs()
        self._apply_transparent_class()
        self._paint_chrome()
        age = index_age_days()
        if age is not None and age > INDEX_STALE_NOTIFY_DAYS:
            self.notify(
                f"Index vieux de {age:.0f} j — Ctrl+R pour reconstruire",
                timeout=8,
            )
        self.query_one("#search", Input).focus()
        self._load_index_worker()

    def on_key(self, event: Key) -> None:
        """d / t / i / ? même quand la recherche a le focus (sinon elles s'écrivent dans l'input)."""
        if len(self.screen_stack) > 1:
            return
        key = event.key
        if key in self._MODIFIER_ONLY_KEYS or "+" in key:
            return
        if key in self._SHORTCUT_KEYS:
            {
                "d": self.action_toggle_dry_run,
                "t": self.action_toggle_transparent,
                "i": self.action_toggle_hide_installed,
                "l": self.action_toggle_installed_catalog,
            }[key]()
            event.prevent_default()
            event.stop()
            return
        if key == "question_mark" or event.character == "?":
            self.action_help()
            event.prevent_default()
            event.stop()

    # ── chrome ───────────────────────────────────────────────────────────────

    def _paint_chrome(self) -> None:
        age = index_age_days()
        n = len(self._pkg_index) if self._pkg_index else 0
        count = f"{n // 1000}k paquets" if n >= 1000 else (f"{n} paquets" if n else "index…")
        age_s = f" · {age:.0f} j" if age is not None and not self._loading else ""
        flags = []
        if self._dry_run:
            flags.append("[yellow]simu[/]")
        if self._transparent:
            flags.append("transp.")
        if self._hide_installed:
            flags.append("sans installés")
        if self._installed_catalog:
            flags.append("catalogue config")
        flag_s = ("  " + " · ".join(flags)) if flags else ""

        shown = len(self._visible)
        total = len(self._rows)
        if self._loading:
            mid = "  chargement de l'index…"
        elif shown:
            mid = f"  {shown}" + (f"/{total}" if shown != total else "") + " résultat" + (
                "s" if shown != 1 else ""
            )
        else:
            mid = ""

        c = get_color_palette().tui
        self.query_one("#chrome", Static).update(
            Text.from_markup(
                f"[b #{c.rich('primary')}]nixpick[/]  [dim]{count}{age_s}[/]{mid}{flag_s}"
            )
        )
        a = c.rich("accent")
        self.query_one("#footerbar", Static).update(
            Text.from_markup(
                f"[b #{a}]↵[/] ajouter   "
                f"[b #{a}]x[/] retirer   "
                f"[b #{a}]l[/] config   "
                f"[b #{a}]↑↓[/] nav   "
                f"[b #{a}]ctrl+i[/] masquer ●   "
                f"[b #{a}]ctrl+d[/] simu   "
                f"[b #{a}]ctrl+t[/] fond   "
                f"[b #{a}]ctrl+r[/] index   "
                f"[b #{a}]?[/] aide   "
                f"[b #{a}]q[/] quitter"
            )
        )

    def _apply_transparent_class(self) -> None:
        self.ansi_color = self._transparent
        if self._transparent:
            self.screen.add_class("transparent")
        else:
            self.screen.remove_class("transparent")

    # ── index ────────────────────────────────────────────────────────────────

    @work(thread=True, group="index", exclusive=True)
    def _load_index_worker(self) -> None:
        try:
            raw = load_index(
                refresh=self._refresh_on_start,
                on_status=lambda m: self.call_from_thread(self._set_loading, m),
            )
            pkg_index = PackageIndex.from_dict(raw)
            self.call_from_thread(self._on_index_ready, pkg_index)
        except NixCommandError as err:
            self.call_from_thread(self.notify, str(err), severity="error")

    def _set_loading(self, message: str) -> None:
        self._loading = True
        p = get_color_palette().tui.rich("primary")
        self.query_one("#chrome", Static).update(
            Text.from_markup(f"[b #{p}]nixpick[/]  [dim]{message}[/]")
        )

    def _on_index_ready(self, pkg_index: PackageIndex) -> None:
        self._pkg_index = pkg_index
        self._version_by_attr = {row.attr: row.version for row in pkg_index.rows}
        self._loading = False
        self._paint_chrome()
        q = self.query_one("#search", Input).value
        if self._installed_catalog and not q.strip():
            self._rebuild_list()
        elif len(q.strip()) >= 2:
            self._schedule_search(q)

    # ── recherche ────────────────────────────────────────────────────────────

    @on(Input.Changed, "#search")
    def _on_search_changed(self, event: Input.Changed) -> None:
        if self._search_timer is not None:
            self._search_timer.stop()
        query = event.value
        self._search_timer = self.set_timer(0.22, lambda: self._schedule_search(query))

    def _schedule_search(self, query: str) -> None:
        q = query.strip()
        if q == self._last_search_query:
            return
        if len(q) < 2:
            self._search_generation += 1
            self._last_search_query = q
            self._rows = []
            self._rebuild_list(query)
            return
        self._search_generation += 1
        gen = self._search_generation
        self.run_worker(
            lambda: self._search_worker(query, gen),
            thread=True,
            exclusive=True,
            group="search",
        )

    def _search_worker(self, query: str, generation: int) -> None:
        if not self._pkg_index or generation != self._search_generation:
            return
        results = search_index(self._pkg_index, query, limit=TUI_RESULT_LIMIT)
        if generation != self._search_generation:
            return
        rows = [ResultRow(attr=a, version=v) for a, v in results]
        self.call_from_thread(self._apply_results, rows, generation, query)

    def _apply_results(
        self, rows: list[ResultRow], generation: int, query: str
    ) -> None:
        if generation != self._search_generation:
            return
        self._last_search_query = query.strip()
        self._rows = rows
        self._rebuild_list(query)
        self._prefetch_descriptions(rows)

    def _prefetch_descriptions(self, rows: list[ResultRow]) -> None:
        attrs = [r.attr for r in rows[:12] if not r.description]
        attrs = [a for a in attrs if not self._desc_cache.get(a)]
        if not attrs:
            return
        self.run_worker(
            lambda: self._desc_cache.fetch_many(attrs),
            thread=True,
            exclusive=True,
            group="desc-batch",
        )

    def _rebuild_list(self, query: str | None = None) -> None:
        if query is None:
            query = self.query_one("#search", Input).value
        ol = self.query_one("#results", OptionList)

        q = query.strip()
        if not q:
            if self._installed_catalog:
                self._fill_installed_catalog(ol)
                return
            self._visible = []
            ol.clear_options()
            ol.border_title = " résultats "
            self._show_idle_detail()
            self._paint_chrome()
            return

        if len(q) < 2:
            self._visible = []
            ol.clear_options()
            ol.border_title = " résultats "
            self._show_short_query_detail()
            self._paint_chrome()
            return

        visible = [
            r
            for r in self._rows
            if not (self._hide_installed and r.attr in self._installed)
        ]
        self._visible = visible
        ol.clear_options()

        if not visible:
            ol.add_option(Option("[dim]aucun résultat[/]", disabled=True))
            ol.border_title = " résultats · 0 "
            self._show_empty_detail()
            self._paint_chrome()
            return

        ol.add_options(
            [Option(self._format_option(row), id=str(i)) for i, row in enumerate(visible)]
        )
        ol.highlighted = 0
        ol.border_title = f" résultats · {len(visible)} "
        self._show_detail(visible[0])
        self._paint_chrome()

    def _format_option(self, row: ResultRow) -> str:
        installed = row.attr in self._installed
        mark = "●" if installed else " "
        ver = f"  {row.version}" if row.version else ""
        return f" {mark} {row.attr}{ver}"

    def _fill_installed_catalog(self, ol: OptionList) -> None:
        attrs = sorted(self._installed)
        rows = [
            ResultRow(attr=a, version=self._version_by_attr.get(a, ""))
            for a in attrs
        ]
        self._rows = rows
        self._visible = rows
        ol.clear_options()
        if not rows:
            ol.add_option(Option("[dim]aucun paquet dans packages.nix[/]", disabled=True))
            ol.border_title = " config · 0 "
            self._show_idle_detail()
            self._paint_chrome()
            return
        ol.add_options(
            [Option(self._format_option(row), id=str(i)) for i, row in enumerate(rows)]
        )
        ol.highlighted = 0
        ol.border_title = f" config · {len(rows)} "
        self._show_detail(rows[0])
        self._paint_chrome()

    # ── détail ───────────────────────────────────────────────────────────────

    def _show_idle_detail(self) -> None:
        self.query_one("#detail-name", Label).update("nixpick")
        self.query_one("#detail-meta", Label).update("nixpkgs → packages.nix")
        self.query_one("#detail-body", Static).update(
            "Tape un nom d'application.\n"
            "[dim]↑↓ pour parcourir · ↵ pour ajouter · ? pour l'aide[/]"
        )
        self.query_one("#detail-hint", Static).update("")

    def _show_short_query_detail(self) -> None:
        self.query_one("#detail-name", Label).update("…")
        self.query_one("#detail-meta", Label).update("")
        self.query_one("#detail-body", Static).update(
            "[dim]Au moins 2 caractères pour lancer la recherche (évite de scanner tout nixpkgs).[/]"
        )
        self.query_one("#detail-hint", Static).update("")

    def _show_empty_detail(self) -> None:
        self.query_one("#detail-name", Label).update("rien trouvé")
        self.query_one("#detail-meta", Label).update("")
        self.query_one("#detail-body", Static).update(
            "[dim]Essaie un mot plus court, ou [b]Ctrl+R[/] pour rafraîchir l'index.[/]"
        )
        self.query_one("#detail-hint", Static).update("")

    def _show_detail(self, row: ResultRow) -> None:
        installed = row.attr in self._installed
        self.query_one("#detail-name", Label).update(row.attr)
        self.query_one("#detail-meta", Label).update(
            row.version + ("  ·  déjà dans la config" if installed else "")
        )
        cached = row.description or self._desc_cache.get(row.attr) or ""
        if cached:
            row.description = cached
        desc = cached or "[dim]description…[/]"
        self.query_one("#detail-body", Static).update(desc)
        if installed:
            d = get_color_palette().tui.rich("danger")
            self.query_one("#detail-hint", Static).update(
                "[yellow]déjà dans packages.nix[/]  ·  "
                f"[bold #{d}]x[/] retirer  ·  [dim]↵ n'ajoute pas[/]"
            )
        elif self._dry_run:
            self.query_one("#detail-hint", Static).update(
                "[yellow]↵  simuler l'ajout (rien ne sera écrit)[/]"
            )
        else:
            self.query_one("#detail-hint", Static).update(
                "[green]↵  ajouter à packages.nix[/]"
            )
        if not row.description:
            self._schedule_desc(row.attr)

    def _schedule_desc(self, attr: str) -> None:
        if self._desc_cache.get(attr):
            return
        if self._desc_timer is not None:
            self._desc_timer.stop()
        self._desc_generation += 1
        gen = self._desc_generation
        self._desc_timer = self.set_timer(
            0.35, lambda: self._fetch_one_desc(attr, gen)
        )

    def _fetch_one_desc(self, attr: str, generation: int) -> None:
        if generation != self._desc_generation:
            return
        self.run_worker(
            lambda: self._desc_worker(attr, generation),
            thread=True,
            exclusive=True,
            group="desc",
        )

    def _desc_worker(self, attr: str, generation: int) -> None:
        if generation != self._desc_generation:
            return
        text = self._desc_cache.fetch_one(attr)
        if text and generation == self._desc_generation:
            self.call_from_thread(self._apply_one_desc, attr, text)

    def _apply_one_desc(self, attr: str, text: str) -> None:
        for row in self._rows:
            if row.attr == attr:
                row.description = text
        current = self._current_row()
        if current and current.attr == attr:
            self.query_one("#detail-body", Static).update(text)

    def _current_row(self) -> ResultRow | None:
        ol = self.query_one("#results", OptionList)
        idx = ol.highlighted
        if idx is None or not self._visible:
            return None
        if 0 <= idx < len(self._visible):
            return self._visible[idx]
        return None

    @on(OptionList.OptionHighlighted, "#results")
    def _on_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        row = self._current_row()
        if row:
            self._show_detail(row)

    # ── actions ──────────────────────────────────────────────────────────────

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_clear_search(self) -> None:
        inp = self.query_one("#search", Input)
        inp.value = ""
        inp.focus()

    def action_escape(self) -> None:
        inp = self.query_one("#search", Input)
        if inp.value:
            inp.value = ""
            inp.focus()
            self._rebuild_list()
            return
        if self._installed_catalog:
            self._installed_catalog = False
            self._rebuild_list()
            inp.focus()
            return
        self.exit()

    def action_cycle_focus(self) -> None:
        if self.focused and self.focused.id == "search":
            self.query_one("#results", OptionList).focus()
        else:
            self.query_one("#search", Input).focus()

    def _move(self, delta: int) -> None:
        ol = self.query_one("#results", OptionList)
        if not self._visible:
            return
        idx = ol.highlighted if ol.highlighted is not None else 0
        nxt = max(0, min(len(self._visible) - 1, idx + delta))
        ol.highlighted = nxt

    def action_cursor_down(self) -> None:
        self._move(1)

    def action_cursor_up(self) -> None:
        self._move(-1)

    def action_cursor_down_if_list(self) -> None:
        if self.focused and self.focused.id == "search":
            return
        self._move(1)

    def action_cursor_up_if_list(self) -> None:
        if self.focused and self.focused.id == "search":
            return
        self._move(-1)

    def action_toggle_hide_installed(self) -> None:
        self._hide_installed = not self._hide_installed
        self._rebuild_list()
        state = "masqués" if self._hide_installed else "affichés"
        self.notify(f"Paquets déjà installés {state}.", timeout=2)

    def action_toggle_installed_catalog(self) -> None:
        self._installed_catalog = not self._installed_catalog
        if self._installed_catalog:
            self.query_one("#search", Input).value = ""
        self._rebuild_list()
        if self._installed_catalog:
            self.notify(
                "Catalogue packages.nix — x pour retirer, esc pour quitter le mode.",
                timeout=3,
            )
        else:
            self.notify("Retour à la recherche nixpkgs.", timeout=2)

    def action_toggle_dry_run(self) -> None:
        self._dry_run = not self._dry_run
        self._paint_chrome()
        row = self._current_row()
        if row:
            self._show_detail(row)
        self.notify("Simulation " + ("on" if self._dry_run else "off") + ".", timeout=2)

    def action_toggle_transparent(self) -> None:
        self._transparent = not self._transparent
        save_transparent_background(self._transparent)
        self._apply_transparent_class()
        self._paint_chrome()
        self.refresh()
        hint = (
            "Fond transparent (ANSI). Kitty : background_opacity dans kitty.conf."
            if self._transparent
            else "Fond opaque (thème couleur)."
        )
        self.notify(hint, timeout=4)

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_refresh_index(self) -> None:
        self._loading = True
        self._paint_chrome()
        self._refresh_index_worker()

    @work(thread=True, group="index", exclusive=True)
    def _refresh_index_worker(self) -> None:
        try:
            raw = load_index(
                refresh=True,
                on_status=lambda m: self.call_from_thread(self._set_loading, m),
            )
            pkg_index = PackageIndex.from_dict(raw)
            self.call_from_thread(self._on_index_ready, pkg_index)
        except NixCommandError as err:
            self.call_from_thread(self.notify, str(err), severity="error")

    def action_remove(self) -> None:
        row = self._current_row()
        if row is None:
            return
        if row.attr not in self._installed:
            self.notify(
                f"{row.attr} n'est pas dans packages.nix — rien à retirer.",
                severity="warning",
                timeout=3,
            )
            return
        plan = plan_remove(row.attr)
        if isinstance(plan, RemoveFailure):
            self.notify(plan.message, severity="warning")
            return
        self.push_screen(
            ConfirmRemoveModal(
                plan, dry_run=self._dry_run, transparent=self._transparent
            ),
            lambda confirmed: self._after_remove_confirm(confirmed, plan, row),
        )

    def _after_remove_confirm(
        self, confirmed: bool | None, plan: RemovePlan, row: ResultRow
    ) -> None:
        if not confirmed:
            return
        if self._dry_run:
            self.notify("Simulation : rien n'a été écrit.", timeout=3)
            return
        try:
            commit_remove(plan, dry_run=False)
        except PermissionError:
            self.notify(f"Pas les droits sur {plan.packages_file}.", severity="error")
            return
        except LookupError as err:
            self.notify(str(err), severity="error")
            return

        self._installed.discard(row.attr)
        self._rebuild_list()
        self.notify(
            f"Retiré.  apply : {rebuild_command()}",
            timeout=6,
        )

    def action_install(self) -> None:
        row = self._current_row()
        if row is None:
            return
        if row.attr in self._installed:
            self.notify(
                "Déjà dans packages.nix — [x] pour retirer.",
                severity="warning",
                timeout=3,
            )
            return
        plan = plan_add(row.attr, row.description)
        if isinstance(plan, AddFailure):
            self.notify(plan.message, severity="warning")
            return

        self.push_screen(
            ConfirmAddModal(
                plan, dry_run=self._dry_run, transparent=self._transparent
            ),
            lambda confirmed: self._after_install_confirm(confirmed, plan, row),
        )

    def _after_install_confirm(
        self, confirmed: bool | None, plan: AddPlan, row: ResultRow
    ) -> None:
        if not confirmed:
            return
        if self._dry_run:
            self.notify("Simulation : rien n'a été écrit.", timeout=3)
            return
        try:
            commit_add(plan, dry_run=False)
        except PermissionError:
            self.notify(f"Pas les droits sur {plan.packages_file}.", severity="error")
            return

        self._installed.add(row.attr)
        self._rebuild_list()
        self.notify(
            f"Ajouté.  apply : {rebuild_command()}",
            timeout=6,
        )


def apply_tui_theme() -> None:
    """Applique la palette config.toml aux classes Textual (à appeler avant .run())."""
    from rofi_theme import sync_rofi_themes

    reset_color_palette_cache()
    palette = load_color_palette()
    c = palette.tui
    NixPickApp.CSS = build_app_css(c)
    ConfirmAddModal.CSS = build_confirm_add_css(c)
    ConfirmRemoveModal.CSS = build_confirm_remove_css(c)
    sync_rofi_themes(palette)


def run_tui(
    refresh: bool = False,
    dry_run: bool = False,
    transparent: bool | None = None,
) -> int:
    try:
        apply_tui_theme()
        NixPickApp(
            refresh=refresh, dry_run=dry_run, transparent=transparent
        ).run()
    except KeyboardInterrupt:
        return 130
    return 0
