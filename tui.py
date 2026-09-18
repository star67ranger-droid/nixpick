"""Interface TUI v2 — UX type fzf / superfile."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from config import load_transparent_background, save_transparent_background
from engine import (
    AddFailure,
    AddPlan,
    NixCommandError,
    REBUILD_CMD,
    TUI_RESULT_LIMIT,
    commit_add,
    fetch_descriptions,
    index_age_days,
    list_installed_attrs,
    load_index,
    plan_add,
    search,
)


@dataclass
class ResultRow:
    attr: str
    version: str
    description: str = ""


# ─── Modales ─────────────────────────────────────────────────────────────────


class ConfirmAddModal(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "confirm", "Oui"),
        Binding("n", "dismiss", "Non"),
        Binding("escape", "dismiss", "Non"),
        Binding("enter", "confirm", "Oui", show=False),
    ]

    def __init__(self, plan: AddPlan, dry_run: bool) -> None:
        super().__init__()
        self._plan = plan
        self._dry_run = dry_run

    def compose(self) -> ComposeResult:
        kind = "simulation" if self._dry_run else "écrire dans la config"
        yield Vertical(
            Static(f"[b]Ajouter {self._plan.attr}[/]  [dim]· {kind}[/]", id="modal-title"),
            Static(f"[dim]{self._plan.packages_file}[/]"),
            RichLog(id="diff", markup=True, highlight=False),
            Static(
                "[b]y[/] / [b]↵[/]  confirmer    [b]n[/] / [b]esc[/]  annuler"
                + ("    [yellow]aucun fichier ne sera touché[/]" if self._dry_run else ""),
                id="modal-keys",
            ),
            id="confirm-box",
        )

    def on_mount(self) -> None:
        log = self.query_one("#diff", RichLog)
        for line in self._plan.context_lines:
            if line.startswith("+"):
                log.write(f"[green]{line}[/]")
            else:
                log.write(f"[dim]  {line}[/]")

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
  [b #51a8b3]tab[/]                aller à la liste / revenir à la recherche
  [b #51a8b3]esc[/]                vider la recherche, puis quitter
  [b #51a8b3]j k[/]                naviguer (quand la liste a le focus)
  [b #51a8b3]F1[/] / [b #51a8b3]?[/]        aide
  [b #51a8b3]ctrl+r[/]            reconstruire l'index
  [b #51a8b3]r[/]                  idem (hors barre de recherche)
  [b #51a8b3]i[/]                  masquer les paquets déjà dans la config
  [b #51a8b3]d[/]                  mode simulation
  [b #51a8b3]t[/]                  fond transparent
  [b #51a8b3]q[/]                  quitter

[dim]Le fond transparent ne marche que si le terminal a une opacité
(Kitty background_opacity, etc.). Un nixos-rebuild n'est jamais lancé seul.[/]
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

    #confirm-box {
        width: 74;
        background: #35363b;
        border: round #51a8b3;
        padding: 1 2;
        margin: 2 4;
    }

    #modal-title { color: #a7aab0; margin-bottom: 0; }
    #modal-keys { color: #737994; margin-top: 1; }

    #diff {
        height: 8;
        margin: 1 0;
        background: #2c2d31;
        border: round #737994;
    }

    #help-box {
        width: 64;
        background: #35363b;
        border: round #bb70d2;
        padding: 1 2;
        margin: 2 4;
    }

    Screen.transparent { background: transparent; }
    Screen.transparent #chrome { background: transparent; }
    Screen.transparent #search-row { background: transparent; }
    Screen.transparent #search-icon { background: transparent; }
    Screen.transparent #search {
        background: #23232655;
        border: round #73799488;
    }
    Screen.transparent #search:focus {
        border: round #57a5e5cc;
        background: #23232688;
    }
    Screen.transparent #results {
        background: #23232644;
        border: round #73799466;
    }
    Screen.transparent #detail-panel {
        background: #23232633;
        border: round #73799466;
    }
    Screen.transparent OptionList > .option-list--option-highlighted {
        background: #57a5e528;
    }
    Screen.transparent #footerbar { background: transparent; }
    Screen.transparent #confirm-box { background: #35363bee; }
    Screen.transparent #help-box { background: #35363bee; }
    Screen.transparent #diff { background: #2c2d3188; }
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
        Binding("r", "refresh_index", show=False),
        Binding("d", "toggle_dry_run", show=False),
        Binding("t", "toggle_transparent", show=False),
        Binding("i", "toggle_hide_installed", show=False),
        Binding("question_mark", "help", show=False),
    ]

    def __init__(
        self,
        refresh: bool = False,
        dry_run: bool = False,
        transparent: bool | None = None,
    ) -> None:
        super().__init__()
        self._refresh_on_start = refresh
        self._dry_run = dry_run
        self._transparent = (
            transparent if transparent is not None else load_transparent_background()
        )
        self._hide_installed = False
        self._index: dict = {}
        self._installed: set[str] = set()
        self._rows: list[ResultRow] = []
        self._visible: list[ResultRow] = []
        self._search_timer = None
        self._desc_timer = None
        self._search_generation = 0
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

    # ── chrome ───────────────────────────────────────────────────────────────

    def _paint_chrome(self) -> None:
        age = index_age_days()
        n = len(self._index)
        count = f"{n // 1000}k paquets" if n >= 1000 else (f"{n} paquets" if n else "index…")
        age_s = f" · {age:.0f} j" if age is not None and not self._loading else ""
        flags = []
        if self._dry_run:
            flags.append("[yellow]simu[/]")
        if self._transparent:
            flags.append("transp.")
        if self._hide_installed:
            flags.append("sans installés")
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
                "[b #51a8b3]↑↓[/] nav   "
                "[b #51a8b3]i[/] installés   "
                "[b #51a8b3]d[/] simu   "
                "[b #51a8b3]t[/] fond   "
                "[b #51a8b3]r[/] index   "
                "[b #51a8b3]?[/] aide   "
                "[b #51a8b3]q[/] quitter"
            )
        )

    def _apply_transparent_class(self) -> None:
        if self._transparent:
            self.screen.add_class("transparent")
        else:
            self.screen.remove_class("transparent")

    # ── index ────────────────────────────────────────────────────────────────

    @work(thread=True, group="index", exclusive=True)
    def _load_index_worker(self) -> None:
        try:
            index = load_index(
                refresh=self._refresh_on_start,
                on_status=lambda m: self.call_from_thread(self._set_loading, m),
            )
            self.call_from_thread(self._on_index_ready, index)
        except NixCommandError as err:
            self.call_from_thread(self.notify, str(err), severity="error")

    def _set_loading(self, message: str) -> None:
        self._loading = True
        self.query_one("#chrome", Static).update(
            Text.from_markup(f"[b #57a5e5]nixpick[/]  [dim]{message}[/]")
        )

    def _on_index_ready(self, index: dict) -> None:
        self._index = index
        self._loading = False
        self._paint_chrome()
        q = self.query_one("#search", Input).value
        if q.strip():
            self._schedule_search(q)

    # ── recherche ────────────────────────────────────────────────────────────

    @on(Input.Changed, "#search")
    def _on_search_changed(self, event: Input.Changed) -> None:
        if self._search_timer is not None:
            self._search_timer.stop()
        query = event.value
        self._search_timer = self.set_timer(0.12, lambda: self._schedule_search(query))

    def _schedule_search(self, query: str) -> None:
        self._search_generation += 1
        gen = self._search_generation
        self.run_worker(
            lambda: self._search_worker(query, gen),
            thread=True,
            exclusive=True,
            group="search",
        )

    def _search_worker(self, query: str, generation: int) -> None:
        if not self._index:
            return
        results = search(self._index, query, limit=TUI_RESULT_LIMIT)
        attrs = [a for a, _ in results[:24]]
        descs = fetch_descriptions(attrs) if attrs else {}
        rows = [
            ResultRow(attr=a, version=v, description=descs.get(a, ""))
            for a, v in results
        ]
        self.call_from_thread(self._apply_results, rows, generation, query)

    def _apply_results(
        self, rows: list[ResultRow], generation: int, query: str
    ) -> None:
        if generation != self._search_generation:
            return
        self._rows = rows
        self._rebuild_list(query)

    def _rebuild_list(self, query: str | None = None) -> None:
        if query is None:
            query = self.query_one("#search", Input).value
        ol = self.query_one("#results", OptionList)

        if not query.strip():
            self._visible = []
            ol.clear_options()
            ol.border_title = " résultats "
            self._show_idle_detail()
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

        options: list[Option] = []
        for i, row in enumerate(visible):
            options.append(Option(self._format_option(row), id=str(i)))
        ol.add_options(options)
        ol.highlighted = 0
        ol.border_title = f" résultats · {len(visible)} "
        self._show_detail(visible[0])
        self._paint_chrome()

    def _format_option(self, row: ResultRow) -> Text:
        installed = row.attr in self._installed
        mark = "●" if installed else " "
        name = row.attr
        ver = row.version or ""
        t = Text()
        t.append(f" {mark} ", style="yellow" if installed else "dim")
        t.append(name, style="yellow" if installed else "")
        if ver:
            t.append(f"  {ver}", style="dim")
        return t

    # ── détail ───────────────────────────────────────────────────────────────

    def _show_idle_detail(self) -> None:
        self.query_one("#detail-name", Label).update("nixpick")
        self.query_one("#detail-meta", Label).update("nixpkgs → packages.nix")
        self.query_one("#detail-body", Static).update(
            "Tape un nom d'application.\n"
            "[dim]↑↓ pour parcourir · ↵ pour ajouter · ? pour l'aide[/]"
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
        desc = row.description or "[dim]pas de description (chargement…)[/]"
        self.query_one("#detail-body", Static).update(desc)
        if installed:
            self.query_one("#detail-hint", Static).update(
                "[yellow]déjà listé dans environment.systemPackages[/]"
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
        if self._desc_timer is not None:
            self._desc_timer.stop()
        self._desc_timer = self.set_timer(0.05, lambda: self._fetch_one_desc(attr))

    def _fetch_one_desc(self, attr: str) -> None:
        self.run_worker(
            lambda: self._desc_worker(attr),
            thread=True,
            exclusive=True,
            group="desc",
        )

    def _desc_worker(self, attr: str) -> None:
        descs = fetch_descriptions([attr])
        text = descs.get(attr, "")
        if text:
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
        self.notify(
            "Fond transparent." if self._transparent else "Fond opaque.",
            timeout=2,
        )

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_refresh_index(self) -> None:
        self._loading = True
        self._paint_chrome()
        self._refresh_index_worker()

    @work(thread=True, group="index", exclusive=True)
    def _refresh_index_worker(self) -> None:
        try:
            index = load_index(
                refresh=True,
                on_status=lambda m: self.call_from_thread(self._set_loading, m),
            )
            self.call_from_thread(self._on_index_ready, index)
        except NixCommandError as err:
            self.call_from_thread(self.notify, str(err), severity="error")

    async def action_install(self) -> None:
        row = self._current_row()
        if row is None:
            return
        plan = plan_add(row.attr, row.description)
        if isinstance(plan, AddFailure):
            self.notify(plan.message, severity="warning")
            return

        confirmed = await self.push_screen_wait(
            ConfirmAddModal(plan, dry_run=self._dry_run)
        )
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
            f"Ajouté.  apply : {REBUILD_CMD}",
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
