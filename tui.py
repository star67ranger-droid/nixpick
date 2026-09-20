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


class ConfirmAddModal(ModalScreen[bool]):
    """Modale de confirmation type lazygit : centrée, aperçu court, actions explicites."""

    CSS = """
    ConfirmAddModal {
        align: center middle;
    }

    #confirm-box {
        width: 78;
        background: #35363b;
        border: round #51a8b3;
        padding: 1 2;
    }

    #modal-title {
        color: #a7aab0;
        margin-bottom: 0;
    }

    #modal-attr {
        text-style: bold;
        color: #57a5e5;
        margin-top: 1;
    }

    #modal-path {
        color: #737994;
    }

    #modal-desc {
        color: #a7aab0;
        margin: 1 0 0 0;
    }

    #modal-badge {
        color: #e5c07b;
        margin-top: 1;
    }

    #diff-panel {
        height: auto;
        max-height: 10;
        margin: 1 0;
        padding: 0 1 1 1;
        background: #2c2d31;
        border: round #737994;
        border-title-color: #dbb671;
        border-title-align: left;
    }

    #diff {
        width: 1fr;
        height: auto;
    }

    #modal-actions {
        height: 1;
        margin-top: 1;
        color: #737994;
    }

    ConfirmAddModal.transparent {
        background: ansi_default;
    }

    ConfirmAddModal.transparent #confirm-box {
        background: ansi_default;
        border: round #737994;
    }

    ConfirmAddModal.transparent #diff-panel {
        background: ansi_default;
        border: round #737994;
    }
    """

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
                "[bold #8fb573]y[/] ou [bold #8fb573]↵[/]  confirmer     "
                "[bold #e06c75]n[/] ou [bold #e06c75]esc[/]  annuler",
                id="modal-actions",
            )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_dismiss(self) -> None:
        self.dismiss(False)


class ConfirmRemoveModal(ModalScreen[bool]):
    """Retirer une entrée de environment.systemPackages."""

    CSS = """
    ConfirmRemoveModal {
        align: center middle;
    }

    #confirm-box {
        width: 78;
        background: #35363b;
        border: round #e06c75;
        padding: 1 2;
    }

    #modal-title {
        color: #e06c75;
        margin-bottom: 0;
    }

    #modal-attr {
        text-style: bold;
        color: #57a5e5;
        margin-top: 1;
    }

    #modal-path {
        color: #737994;
    }

    #modal-badge {
        color: #e5c07b;
        margin-top: 1;
    }

    #diff-panel {
        height: auto;
        max-height: 10;
        margin: 1 0;
        padding: 0 1 1 1;
        background: #2c2d31;
        border: round #737994;
        border-title-color: #e06c75;
        border-title-align: left;
    }

    #diff {
        width: 1fr;
        height: auto;
    }

    #modal-actions {
        height: 1;
        margin-top: 1;
        color: #737994;
    }

    ConfirmRemoveModal.transparent {
        background: ansi_default;
    }

    ConfirmRemoveModal.transparent #confirm-box {
        background: ansi_default;
        border: round #e06c75;
    }

    ConfirmRemoveModal.transparent #diff-panel {
        background: ansi_default;
        border: round #737994;
    }
    """

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
                "[bold #8fb573]y[/] ou [bold #8fb573]↵[/]  confirmer     "
                "[bold #e06c75]n[/] ou [bold #e06c75]esc[/]  annuler",
                id="modal-actions",
            )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_dismiss(self) -> None:
        self.dismiss(False)


class HelpModal(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "dismiss", "Fermer"),
        Binding("q", "dismiss", "Fermer"),
        Binding("question_mark", "dismiss", "Fermer", show=False),
    ]

    HELP = """\
[b #bb70d2]nixpick[/]  [dim]raccourcis[/]

  [b #51a8b3]taper[/]              cherche tout de suite (comme fzf)
  [b #51a8b3]↑ ↓[/]                navigue sans quitter la recherche
  [b #51a8b3]↵[/]                  ajouter le paquet surligné
  [b #51a8b3]x[/]                  retirer (si ● déjà dans packages.nix)
  [b #51a8b3]l[/]                  catalogue des paquets déjà dans la config
  [b #51a8b3]tab[/]                aller à la liste / revenir à la recherche
  [b #51a8b3]esc[/]                vider la recherche, puis quitter
  [b #51a8b3]j k[/]                naviguer (quand la liste a le focus)
  [b #51a8b3]F1[/] / [b #51a8b3]?[/]        aide
  [b #51a8b3]ctrl+r[/]            reconstruire l'index
  [b #51a8b3]i[/] / [b #51a8b3]ctrl+i[/]   masquer les paquets déjà dans la config
  [b #51a8b3]d[/] / [b #51a8b3]ctrl+d[/]   mode simulation
  [b #51a8b3]t[/] / [b #51a8b3]ctrl+t[/]   fond transparent
  [b #51a8b3]q[/]                  quitter

[dim]Transparence réelle = mode ANSI (comme superfile) + Kitty :
dans ~/.config/kitty/kitty.conf → background_opacity 0.85
Puis Ctrl+T ou t. Si ça reste opaque, ton shell/peste peint un fond
couleur : seul le fond « par défaut » du terminal devient transparent.
Un nixos-rebuild n'est jamais lancé seul.[/]
"""

    def compose(self) -> ComposeResult:
        yield Vertical(Static(self.HELP), id="help-box")

    def action_dismiss(self) -> None:
        self.dismiss(None)


# ─── App ─────────────────────────────────────────────────────────────────────


class NixPickApp(App[None]):
    TITLE = "nixpick"
    CSS = """
    Screen {
        background: #2c2d31;
        layout: vertical;
    }

    #chrome {
        height: 1;
        color: #a7aab0;
        padding: 0 1;
        background: #232326;
    }

    #search-row {
        height: 3;
        padding: 0 1;
        background: #232326;
    }

    #search-icon {
        width: 3;
        height: 3;
        content-align: center middle;
        color: #57a5e5;
        background: #232326;
    }

    #search {
        height: 3;
        border: round #737994;
        background: #232326;
        color: #a7aab0;
        padding: 0 1;
    }

    #search:focus {
        border: round #57a5e5;
    }

    #main {
        height: 1fr;
        padding: 0 1 0 1;
    }

    #results {
        width: 1fr;
        border: round #737994;
        border-title-color: #57a5e5;
        border-title-align: left;
        background: #232326;
        scrollbar-color: #57a5e5;
        scrollbar-background: #2c2d31;
    }

    #detail-panel {
        width: 1fr;
        border: round #737994;
        border-title-color: #dbb671;
        border-title-align: left;
        background: #232326;
        padding: 1 2;
    }

    OptionList > .option-list--option-highlighted {
        background: #2c2d31;
        color: #51a8b3;
        text-style: bold;
    }

    #detail-name {
        text-style: bold;
        color: #57a5e5;
    }

    #detail-meta {
        color: #737994;
        margin-bottom: 1;
    }

    #detail-body {
        color: #a7aab0;
    }

    #detail-hint {
        color: #8fb573;
        margin-top: 2;
    }

    #footerbar {
        height: 1;
        color: #737994;
        padding: 0 1;
        background: #232326;
    }

    .key {
        color: #51a8b3;
    }

    #help-box {
        width: 64;
        background: #35363b;
        border: round #bb70d2;
        padding: 1 2;
        margin: 2 4;
    }

    /* Textual en truecolor : l'alpha RGB ne laisse pas voir le bureau Kitty.
       Il faut ansi_default + App(ansi_color=True) — voir FAQ Textual. */
    Screen.transparent {
        background: ansi_default;
    }
    Screen.transparent #chrome,
    Screen.transparent #search-row,
    Screen.transparent #search-icon,
    Screen.transparent #footerbar,
    Screen.transparent #main {
        background: ansi_default;
    }
    Screen.transparent #search {
        background: ansi_default;
        border: round #737994;
    }
    Screen.transparent #search:focus {
        border: round #57a5e5;
    }
    Screen.transparent #results {
        background: ansi_default;
        border: round #737994;
        scrollbar-background: ansi_default;
        scrollbar-background-hover: ansi_default;
        scrollbar-background-active: ansi_default;
    }
    Screen.transparent #detail-panel {
        background: ansi_default;
        border: round #737994;
    }
    Screen.transparent OptionList {
        background: ansi_default;
    }
    Screen.transparent OptionList > .option-list--option-highlighted {
        background: ansi_default;
        color: #51a8b3;
        text-style: bold;
    }
    Screen.transparent #help-box {
        background: ansi_default;
    }
    """

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

        self.query_one("#chrome", Static).update(
            Text.from_markup(
                f"[b #57a5e5]nixpick[/]  [dim]{count}{age_s}[/]{mid}{flag_s}"
            )
        )
        self.query_one("#footerbar", Static).update(
            Text.from_markup(
                "[b #51a8b3]↵[/] ajouter   "
                "[b #51a8b3]x[/] retirer   "
                "[b #51a8b3]l[/] config   "
                "[b #51a8b3]↑↓[/] nav   "
                "[b #51a8b3]ctrl+i[/] masquer ●   "
                "[b #51a8b3]ctrl+d[/] simu   "
                "[b #51a8b3]ctrl+t[/] fond   "
                "[b #51a8b3]ctrl+r[/] index   "
                "[b #51a8b3]?[/] aide   "
                "[b #51a8b3]q[/] quitter"
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
        self.query_one("#chrome", Static).update(
            Text.from_markup(f"[b #57a5e5]nixpick[/]  [dim]{message}[/]")
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
            "[dim]Essaie un mot plus court, ou [b]r[/] pour rafraîchir l'index.[/]"
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
            self.query_one("#detail-hint", Static).update(
                "[yellow]déjà dans packages.nix[/]  ·  "
                "[bold #e06c75]x[/] retirer  ·  [dim]↵ n'ajoute pas[/]"
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


def run_tui(
    refresh: bool = False,
    dry_run: bool = False,
    transparent: bool | None = None,
) -> int:
    try:
        NixPickApp(
            refresh=refresh, dry_run=dry_run, transparent=transparent
        ).run()
    except KeyboardInterrupt:
        return 130
    return 0
