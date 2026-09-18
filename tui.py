"""Interface TUI (Textual) — recherche et ajout de paquets."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, RichLog, Static

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


class ConfirmAddModal(ModalScreen[bool]):
    """Modale de confirmation avec aperçu du diff (style lazygit)."""

    BINDINGS = [
        Binding("y", "confirm", "Oui, écrire"),
        Binding("n", "dismiss", "Non"),
        Binding("escape", "dismiss", "Non"),
    ]

    def __init__(self, plan: AddPlan, dry_run: bool) -> None:
        super().__init__()
        self._plan = plan
        self._dry_run = dry_run

    def compose(self) -> ComposeResult:
        title = "Simulation" if self._dry_run else "Confirmer l'ajout"
        yield Vertical(
            Label(f"[bold]{title}[/] — [cyan]{self._plan.attr}[/]"),
            Label(f"[dim]{self._plan.packages_file}[/]"),
            RichLog(id="diff", highlight=True, markup=True),
            Label(
                "[dim]y[/] confirmer · [dim]n[/] ou [dim]Échap[/] annuler"
                + (" · [yellow]aucun fichier ne sera modifié[/]" if self._dry_run else "")
            ),
            id="confirm-box",
        )

    def on_mount(self) -> None:
        log = self.query_one("#diff", RichLog)
        for line in self._plan.context_lines:
            if line.startswith("+"):
                log.write(f"[green]{line}[/]")
            else:
                log.write(f"[dim]{line}[/]")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_dismiss(self) -> None:
        self.dismiss(False)


class HelpModal(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Fermer"), Binding("q", "dismiss", "Fermer")]

    HELP = """\
[bold]nixpick[/] — raccourcis

[bold cyan]/[/] ou [bold]Ctrl+U[/]     focus recherche
[bold]Entrée[/]              confirmer l'ajout (modale)
[bold]j[/] [bold]k[/]                 naviguer dans la liste
[bold]r[/]                   reconstruire l'index nixpkgs
[bold]d[/]                   basculer mode simulation
[bold]?[/]                   cette aide
[bold]q[/]                   quitter

[dim]Un switch NixOS commit et pousse /etc/nixos — jamais lancé automatiquement.[/]
"""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.HELP, id="help-text"),
            id="help-box",
        )

    def action_dismiss(self) -> None:
        self.dismiss(None)


class NixPickApp(App[None]):
    TITLE = "nixpick"
    SUB_TITLE = "paquets NixOS"

    CSS = """
    Screen {
        background: #11111b;
    }

    #search {
        margin: 0 1 0 1;
        border: tall #89b4fa;
        background: #1e1e2e;
    }

    #main {
        height: 1fr;
        margin: 0 1;
    }

    #results-panel {
        width: 45%;
        border: solid #313244;
        background: #181825;
    }

    #detail-panel {
        width: 55%;
        border: solid #313244;
        background: #1e1e2e;
        padding: 1 2;
    }

    #detail-title {
        text-style: bold;
        color: #89b4fa;
    }

    #detail-version {
        color: #a6adc8;
    }

    #detail-body {
        color: #cdd6f4;
        margin-top: 1;
    }

    #status-bar {
        height: 1;
        background: #313244;
        color: #a6adc8;
        padding: 0 2;
    }

    ListView {
        background: #181825;
        scrollbar-background: #11111b;
        scrollbar-color: #89b4fa;
    }

    ListView > ListItem.--highlight {
        background: #45475a;
    }

    ListItem.installed {
        color: #f9e2af;
    }

    #confirm-box {
        width: 72;
        height: auto;
        max-height: 80%;
        background: #1e1e2e;
        border: thick #89b4fa;
        padding: 1 2;
        margin: 2 4;
    }

    #diff {
        height: 10;
        border: solid #313244;
        margin: 1 0;
        background: #11111b;
    }

    #help-box {
        width: 60;
        background: #1e1e2e;
        border: thick #cba6f7;
        padding: 1 2;
        margin: 2 4;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quitter"),
        Binding("slash", "focus_search", "Rechercher", show=False),
        Binding("ctrl+u", "focus_search", "Rechercher", show=False),
        Binding("j", "cursor_down", "Bas", show=False),
        Binding("k", "cursor_up", "Haut", show=False),
        Binding("r", "refresh_index", "Index"),
        Binding("d", "toggle_dry_run", "Simulation"),
        Binding("question_mark", "help", "Aide"),
        Binding("enter", "install", "Ajouter"),
    ]

    def __init__(self, refresh: bool = False, dry_run: bool = False) -> None:
        super().__init__()
        self._refresh_on_start = refresh
        self._dry_run = dry_run
        self._index: dict = {}
        self._installed: set[str] = set()
        self._rows: list[ResultRow] = []
        self._search_timer = None
        self._search_generation = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="Rechercher un paquet nixpkgs…", id="search")
        with Horizontal(id="main"):
            with Vertical(id="results-panel"):
                yield ListView(id="results")
            with VerticalScroll(id="detail-panel"):
                yield Label("—", id="detail-title")
                yield Label("", id="detail-version")
                yield Static(
                    "Tape un nom d'application ou un mot-clé.\n\n"
                    "Les paquets déjà dans ta config sont en [yellow]jaune[/].",
                    id="detail-body",
                )
        yield Label(self._status_text(), id="status-bar")
        yield Footer()

    def _status_text(self) -> str:
        age = index_age_days()
        age_s = f"index · {age:.0f} j" if age is not None else "index · …"
        mode = " · [SIMULATION]" if self._dry_run else ""
        return f"{age_s}{mode} · ? aide · r reconstruire l'index · d simulation"

    def on_mount(self) -> None:
        self._installed = list_installed_attrs()
        self.query_one("#search", Input).focus()
        self.run_worker(self._load_index_worker, thread=True, exclusive=True)

    @work(thread=True, group="index")
    def _load_index_worker(self) -> None:
        try:
            index = load_index(
                refresh=self._refresh_on_start,
                on_status=lambda m: self.call_from_thread(self._set_status, m),
            )
            self.call_from_thread(self._on_index_ready, index)
        except NixCommandError as err:
            self.call_from_thread(self.notify, str(err), severity="error")

    def _set_status(self, message: str) -> None:
        self.query_one("#status-bar", Label).update(message)

    def _on_index_ready(self, index: dict) -> None:
        self._index = index
        self.query_one("#status-bar", Label).update(self._status_text())
        self.notify(f"Index prêt — {len(index)} paquets.", timeout=3)

    @on(Input.Changed)
    def _on_search_changed(self, event: Input.Changed) -> None:
        if self._search_timer is not None:
            self._search_timer.stop()
        query = event.value
        self._search_timer = self.set_timer(0.15, lambda: self._schedule_search(query))

    def _schedule_search(self, query: str) -> None:
        self._search_generation += 1
        gen = self._search_generation
        self.run_worker(
            self._search_worker,
            query,
            gen,
            thread=True,
            exclusive=True,
            group="search",
        )

    def _search_worker(self, query: str, generation: int) -> None:
        if not self._index:
            return
        results = search(self._index, query, limit=TUI_RESULT_LIMIT)
        attrs = [a for a, _ in results[:28]]
        descs = fetch_descriptions(attrs) if attrs else {}
        rows = [
            ResultRow(attr=a, version=v, description=descs.get(a, ""))
            for a, v in results
        ]
        self.call_from_thread(self._apply_search_results, rows, generation, query)

    def _apply_search_results(
        self, rows: list[ResultRow], generation: int, query: str
    ) -> None:
        if generation != self._search_generation:
            return
        self._rows = rows
        lv = self.query_one("#results", ListView)
        lv.clear()
        if not query.strip():
            self._update_detail(None)
            self.query_one("#status-bar", Label).update(self._status_text())
            return
        if not rows:
            lv.append(ListItem(Label("[dim]Aucun résultat[/]")))
            self._update_detail(None)
        else:
            for row in rows:
                tag = " ✓" if row.attr in self._installed else ""
                css = "installed" if row.attr in self._installed else ""
                lv.append(
                    ListItem(
                        Label(f"{row.attr}{tag}  [dim]{row.version}[/]"),
                        classes=css,
                    )
                )
            lv.index = 0
            self._update_detail(rows[0])
        count = len(rows)
        self.query_one("#status-bar", Label).update(
            f"{count} résultat{'s' if count != 1 else ''} · {self._status_text()}"
        )

    @on(ListView.Selected, "#results")
    def _on_result_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self._rows):
            self._update_detail(self._rows[idx])

    @on(ListView.Highlighted, "#results")
    def _on_result_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.index is not None and 0 <= event.list_view.index < len(
            self._rows
        ):
            self._update_detail(self._rows[event.list_view.index])

    def _update_detail(self, row: ResultRow | None) -> None:
        title = self.query_one("#detail-title", Label)
        version = self.query_one("#detail-version", Label)
        body = self.query_one("#detail-body", Static)
        if row is None:
            title.update("—")
            version.update("")
            body.update("[dim]Sélectionne un paquet dans la liste.[/]")
            return
        title.update(row.attr)
        version.update(row.version)
        installed = (
            "\n\n[yellow]Déjà listé dans environment.systemPackages.[/]"
            if row.attr in self._installed
            else ""
        )
        desc = row.description or "[dim]Pas de description.[/]"
        body.update(f"{desc}{installed}")

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_cursor_down(self) -> None:
        lv = self.query_one("#results", ListView)
        if lv.index is None:
            lv.index = 0
        elif lv.index < len(self._rows) - 1:
            lv.index += 1

    def action_cursor_up(self) -> None:
        lv = self.query_one("#results", ListView)
        if lv.index is None:
            lv.index = 0
        elif lv.index > 0:
            lv.index -= 1

    def action_refresh_index(self) -> None:
        self.notify("Reconstruction de l'index…", timeout=2)
        self.run_worker(self._refresh_index_worker, thread=True, exclusive=True)

    @work(thread=True, group="index")
    def _refresh_index_worker(self) -> None:
        try:
            index = load_index(refresh=True, on_status=lambda m: self.call_from_thread(
                self._set_status, m
            ))
            self.call_from_thread(self._on_index_ready, index)
            q = self.query_one("#search", Input).value
            if q.strip():
                self.call_from_thread(self._schedule_search, q)
        except NixCommandError as err:
            self.call_from_thread(self.notify, str(err), severity="error")

    def action_toggle_dry_run(self) -> None:
        self._dry_run = not self._dry_run
        self.query_one("#status-bar", Label).update(self._status_text())
        state = "activé" if self._dry_run else "désactivé"
        self.notify(f"Mode simulation {state}.")

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    async def action_install(self) -> None:
        lv = self.query_one("#results", ListView)
        if lv.index is None or not self._rows:
            return
        row = self._rows[lv.index]
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
            self.notify("Simulation : aucun fichier modifié.", severity="information")
            return

        try:
            commit_add(plan, dry_run=False)
        except PermissionError:
            self.notify(
                f"Pas les droits sur {plan.packages_file}. Relance avec les droits adaptés.",
                severity="error",
            )
            return

        self._installed.add(row.attr)
        self.notify(
            f"Ajouté. Sauvegarde : {plan.backup_path.name}\nApplique : {REBUILD_CMD}",
            timeout=8,
            severity="information",
        )
        self._schedule_search(self.query_one("#search", Input).value)


def run_tui(refresh: bool = False, dry_run: bool = False) -> int:
    try:
        NixPickApp(refresh=refresh, dry_run=dry_run).run()
    except KeyboardInterrupt:
        return 130
    return 0
