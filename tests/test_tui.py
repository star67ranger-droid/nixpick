"""Smoke tests de la TUI OpenTUI : rendu, routage des touches, modales.

Ces tests pilotent le renderer de test d'opentui (pas de terminal réel) avec
un index factice : aucune requête nix, aucune écriture de config.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import tui
from engine import AddPlan


class FakeDescCache:
    """DescriptionCache sans nix eval ni écriture du cache disque."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, attr: str) -> str | None:
        return self._data.get(attr)

    def remember(self, attr: str, description: str) -> None:
        self._data[attr] = description

    def fetch_one(self, attr: str) -> str:
        return self._data.get(attr, "description factice")

    def fetch_many(self, attrs: list[str]) -> dict[str, str]:
        return {a: self._data.get(a, "") for a in attrs}


FAKE_INDEX = {
    "firefox": {"version": "154.0", "pname": "firefox"},
    "firefox-esr": {"version": "153.1.0esr", "pname": "firefox"},
    "firejail": {"version": "0.9.72", "pname": "firejail"},
    "firefly": {"version": "2.0", "pname": "firefly"},
    "firebird": {"version": "4.0", "pname": "firebird"},
    "neovim": {"version": "0.10.0", "pname": "neovim"},
    "htop": {"version": "3.3.0", "pname": "htop"},
}


@pytest.fixture
def tui_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """Index factice + descriptions factices + config hors du réel."""
    monkeypatch.setattr(tui, "load_index", lambda refresh=False, on_status=None: dict(FAKE_INDEX))
    monkeypatch.setattr(tui, "index_age_days", lambda: 1.0)
    monkeypatch.setattr(tui, "list_installed_attrs", lambda: {"firefox"})
    monkeypatch.setattr(tui, "DescriptionCache", FakeDescCache)
    monkeypatch.setattr(tui, "load_transparent_background", lambda: False)

    plan = AddPlan(
        attr="neovim",
        description="Fancy Vim",
        new_line="    neovim\n",
        context_lines=[
            "environment.systemPackages = with pkgs; [",
            "    htop",
            "+   neovim",
            "];",
        ],
        packages_file=tmp_path / "packages.nix",
        backup_path=tmp_path / "packages.nix.bak",
    )
    monkeypatch.setattr(tui, "plan_add", lambda attr, description: plan)
    monkeypatch.setattr(tui, "save_transparent_background", lambda enabled: None)
    return {"plan": plan}


async def _boot(**kwargs: Any) -> tuple[tui.TuiApp, Any]:
    app = tui.TuiApp(**kwargs)
    setup = await tui_test_render(app)
    return app, setup


async def tui_test_render(app: tui.TuiApp) -> Any:
    from opentui.testing import test_render

    setup = await test_render(tui._make_app(app), {"width": 100, "height": 30})
    await _pump(setup, lambda: app.pkg_index is not None and not app.loading.peek())
    return setup


async def _pump(
    setup: Any,
    cond: Callable[[], bool] | None = None,
    timeout: float = 2.0,
    step: float = 0.02,
) -> bool:
    """Fait tourner les frames du renderer jusqu'à ``cond`` (ou le délai)."""
    deadline = time.monotonic() + timeout
    while True:
        setup.render_frame()
        if cond is not None and cond():
            setup.render_frame()
            return True
        if time.monotonic() >= deadline:
            return cond is None
        await asyncio.sleep(step)


def _text(setup: Any) -> str:
    return setup.capture_char_frame()


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ── rendu ──────────────────────────────────────────────────────────────────


def test_rendu_chrome_recherche_footer(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            text = _text(setup)
            assert "nixpick" in text
            assert "chargement" not in text  # index déjà prêt
            assert "chercher un paquet" in text  # placeholder de recherche
            assert "résultats" in text  # titre de la liste
            assert "détail" in text
            assert "ajouter" in text and "quitter" in text  # footer
            assert app.last_error is None
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_frappe_recherche_affiche_resultats(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.type_text("firefox")
            ok = await _pump(setup, lambda: bool(app.shown.peek()), timeout=3.0)
            assert ok, "la recherche n'a rien rendu"
            assert app.query.peek() == "firefox"
            text = _text(setup)
            assert "firefox" in text
            assert "neovim" not in text
            assert "résultats ·" in text
            assert app.detail_state.peek() == "row"
            assert app.last_error is None
        finally:
            setup.renderer.stop()

    _run(scenario())


# ── routage des touches ────────────────────────────────────────────────────


def test_monolettre_non_tape_quand_recherche_focalisee(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.type_text("d")
            await _pump(setup, timeout=0.4)
            assert "d" in app.query.peek()
            assert app.dry_run.peek() is False  # 'd' ne bascule pas en mode liste
            assert app.focus.peek() == "search"
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_tab_liste_puis_monolettre_et_navigation(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.type_text("fire")
            assert await _pump(setup, lambda: bool(app.shown.peek()), timeout=3.0)
            assert len(app.shown.peek()) >= 4

            setup.mock_input.press_tab()
            await _pump(setup, timeout=0.1)
            assert app.focus.peek() == "list"

            setup.mock_input.press_key("d")
            await _pump(setup, timeout=0.1)
            assert app.dry_run.peek() is True
            setup.mock_input.press_key("d")
            await _pump(setup, timeout=0.1)
            assert app.dry_run.peek() is False

            for _ in range(3):
                setup.mock_input.press_key("j")
            await _pump(setup, timeout=0.1)
            assert app.cursor.peek() == 3
            setup.mock_input.press_key("k")
            await _pump(setup, timeout=0.1)
            assert app.cursor.peek() == 2
            setup.mock_input.press_key("j")  # remet à 3 avant la borne
            await _pump(setup, timeout=0.1)

            setup.mock_input.press_key("up")
            await _pump(setup, timeout=0.1)
            assert app.cursor.peek() == 2
            setup.mock_input.press_key("down")
            await _pump(setup, timeout=0.1)
            assert app.cursor.peek() == 3

            setup.mock_input.press_key("/")
            await _pump(setup, timeout=0.1)
            assert app.focus.peek() == "search"
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_escape_veid_recherche_puis_quitte(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        quit_calls: list[bool] = []
        app.quit = lambda: quit_calls.append(True)  # type: ignore[method-assign]
        try:
            setup.mock_input.type_text("htop")
            assert await _pump(setup, lambda: bool(app.shown.peek()), timeout=3.0)

            setup.mock_input.press_escape()
            await _pump(setup, timeout=0.1)
            assert app.query.peek() == ""
            assert quit_calls == []

            setup.mock_input.press_escape()
            await _pump(setup, timeout=0.1)
            assert quit_calls == [True]
        finally:
            setup.renderer.stop()

    _run(scenario())


# ── modales ────────────────────────────────────────────────────────────────


def test_aide_s_ouvre_et_se_ferme(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.press_key("?")
            await _pump(setup, timeout=0.1)
            assert app.modal.peek() is not None
            assert app.modal.peek()["kind"] == "help"
            text = _text(setup)
            assert "raccourcis" in text
            assert "taper" in text

            setup.mock_input.press_escape()
            await _pump(setup, timeout=0.1)
            assert app.modal.peek() is None
            assert "raccourcis" not in _text(setup)
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_entree_ouvre_confirmation_annulation(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.type_text("neovim")
            assert await _pump(setup, lambda: bool(app.shown.peek()), timeout=3.0)
            assert "firefox" in app.installed  # paquet déjà listé en fixture

            setup.mock_input.press_key("return")
            await _pump(setup, timeout=0.2)
            payload = app.modal.peek()
            assert payload is not None and payload["kind"] == "add"
            text = _text(setup)
            assert "Confirmer" in text
            assert "neovim" in text
            assert "confirmer" in text

            setup.mock_input.press_key("n")
            await _pump(setup, timeout=0.1)
            assert app.modal.peek() is None
            assert app.last_error is None
        finally:
            setup.renderer.stop()

    _run(scenario())


# ── signaux / toasts ───────────────────────────────────────────────────────


def test_toggle_simu_via_ctrl_d(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.press_key("d", ctrl=True)
            await _pump(setup, timeout=0.1)
            assert app.dry_run.peek() is True
            assert "Simulation on" in _text(setup)

            setup.mock_input.press_key("i", ctrl=True)
            await _pump(setup, timeout=0.1)
            assert app.hide_installed.peek() is True

            setup.mock_input.press_key("t", ctrl=True)
            await _pump(setup, timeout=0.1)
            assert app.transparent.peek() is True
            assert app.last_error is None
        finally:
            setup.renderer.stop()

    _run(scenario())


# ── fuzzy-finder : recherche centrée, suggestions, navigation ──────────────


def test_interface_remplit_toute_la_hauteur(tui_env: dict[str, Any]) -> None:
    """Le footer est sur la dernière ligne (la racine remplit le terminal)."""

    async def scenario() -> None:
        app, setup = await _boot()
        try:
            lines = _text(setup).split("\n")
            assert len(lines) == 30
            assert "quitter" in lines[-1]
            assert app.last_error is None
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_recherche_centree_et_ligne_de_titre(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            text = _text(setup)
            assert "essaie : firefox" in text  # suggestions au repos
            assert "résultats ─" in text  # titre + remplissage, sans bordure
            assert "─ détail ─" in text  # panneau de droite bordé

            setup.mock_input.type_text("fire")
            assert await _pump(setup, lambda: bool(app.shown.peek()), timeout=3.0)
            text = _text(setup)
            assert "essaie :" not in text  # suggestions masquées en recherche
            assert "▸" in text  # marqueur de sélection
            assert "●" in text  # paquet déjà installé (firefox)
            assert "154.0" in text and "153.1.0esr" in text  # versions alignées
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_hints_sous_la_recherche(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.type_text("f")
            await _pump(setup, timeout=0.4)
            assert "caractère" in _text(setup)

            setup.mock_input.type_text("zzzz")
            assert await _pump(
                setup, lambda: app.detail_state.peek() == "empty", timeout=3.0
            )
            text = _text(setup)
            assert "aucun résultat" in text
            assert "résultats · 0" in text
            assert app.last_error is None
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_ctrl_n_p_navigue_depuis_la_recherche(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.type_text("fire")
            assert await _pump(setup, lambda: bool(app.shown.peek()), timeout=3.0)
            assert app.cursor.peek() == 0

            for _ in range(2):
                setup.mock_input.press_key("n", ctrl=True)
            await _pump(setup, timeout=0.1)
            assert app.cursor.peek() == 2

            setup.mock_input.press_key("p", ctrl=True)
            await _pump(setup, timeout=0.1)
            assert app.cursor.peek() == 1

            setup.mock_input.press_key("p", ctrl=True)
            setup.mock_input.press_key("p", ctrl=True)
            await _pump(setup, timeout=0.1)
            assert app.cursor.peek() == 0  # borné à 0
            assert app.focus.peek() == "search"  # la recherche garde le focus
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_pageup_pagedown_par_un_ecran(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.type_text("fire")
            assert await _pump(setup, lambda: bool(app.shown.peek()), timeout=3.0)

            setup.mock_input.press_key("pagedown")
            await _pump(setup, timeout=0.1)
            assert app.cursor.peek() == len(app.shown.peek()) - 1  # écran > 5 résultats

            setup.mock_input.press_key("pageup")
            await _pump(setup, timeout=0.1)
            assert app.cursor.peek() == 0
            assert app.last_error is None
        finally:
            setup.renderer.stop()

    _run(scenario())


# ── pas de chevauchement (hauteurs de lignes) ──────────────────────────────


def test_aide_lignes_intactes_dans_la_boite(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        _app, setup = await _boot()
        try:
            setup.mock_input.press_key("?")
            await _pump(setup, timeout=0.1)
            text = _text(setup)
            assert "background_opacity 0.85" in text
            assert "n'est jamais lancé seul" in text
            last = [ln for ln in text.split("\n") if "n'est jamais lancé seul" in ln]
            assert last and "╰" not in last[0]  # pas posée sur la bordure basse
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_detail_longue_description_ne_chevauche_pas(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.type_text("fire")
            assert await _pump(setup, lambda: bool(app.shown.peek()), timeout=3.0)

            app.shown.peek()[0].description = "mot " * 400
            app.rev_bump()
            await _pump(setup, timeout=0.2)

            lines = _text(setup).split("\n")
            hint = [ln for ln in lines if "ajouter à packages.nix" in ln]
            assert hint, "l'indice « ajouter » a disparu du panneau détail"
            assert not any("mot mot mot" in ln for ln in hint)
            assert app.last_error is None
        finally:
            setup.renderer.stop()

    _run(scenario())


# ── audit 2 : index en échec, plan, terminal petit, coller, footer ─────────


def test_index_en_echec_ne_bloque_pas_la_tui(
    tui_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sans le catch large, le worker meurt : écran de chargement à vie."""

    def boom(refresh: bool = False, on_status: Any = None) -> dict[str, Any]:
        raise ValueError("index illisible")

    monkeypatch.setattr(tui, "load_index", boom)

    async def scenario() -> None:
        app = tui.TuiApp()
        from opentui.testing import test_render

        setup = await test_render(tui._make_app(app), {"width": 100, "height": 30})
        try:
            assert await _pump(setup, lambda: not app.loading.peek(), timeout=4.0)
            assert app.pkg_index is None
            assert app.index_failed.peek() is True
            text = _text(setup)
            # hint persistant (pas seulement le toast de 3 s)
            assert "index indisponible" in text
            # on ne ment pas : pas de « aucun résultat » alors que rien n'est chargé
            assert "aucun résultat" not in text
            assert app.last_error is None
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_plan_liste_plus_detail_tient_dans_la_largeur() -> None:
    for width in range(40, 200, 4):
        listing, detail = tui._split_widths(width)
        assert listing >= 1 and detail >= 1
        assert listing + detail <= width - 2, f"{width}px : {listing}+{detail}"


@pytest.mark.parametrize("width,height", [(40, 30), (100, 30), (160, 30)])
def test_footer_rendu_tient_dans_la_largeur(
    tui_env: dict[str, Any], width: int, height: int
) -> None:
    from opentui.structs import display_width
    from opentui.testing import test_render

    async def scenario() -> None:
        app = tui.TuiApp()
        setup = await test_render(tui._make_app(app), {"width": width, "height": height})
        try:
            assert await _pump(
                setup, lambda: app.pkg_index is not None and not app.loading.peek()
            )
            footer = _text(setup).split("\n")[-1].rstrip()
            assert "quitter" in footer and "?" in footer
            assert display_width(footer) <= width, f"{display_width(footer)} > {width}"
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_footer_nannonce_que_des_touches_accessibles(tui_env: dict[str, Any]) -> None:
    """Au focus recherche, `x`/`l`/`q` sont du texte : le footer ne les annonce pas."""

    async def scenario() -> None:
        app, setup = await _boot()
        try:
            footer = _text(setup).split("\n")[-1]
            assert "^X" in footer and "esc" in footer
            assert " x " not in footer and " l " not in footer
            # et comportement vérifié : une lettre simple reste dans la requête
            setup.mock_input.type_text("x")
            await _pump(setup, timeout=0.2)
            assert "x" in app.query.peek()
            assert app.focus.peek() == "search"
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_aide_tronquee_avec_indicateur_sur_terminal_court(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app = tui.TuiApp()
        from opentui.testing import test_render

        setup = await test_render(tui._make_app(app), {"width": 90, "height": 14})
        try:
            assert await _pump(
                setup, lambda: app.pkg_index is not None and not app.loading.peek()
            )
            setup.mock_input.press_key("?")
            await _pump(setup, timeout=0.2)
            text = _text(setup)
            assert "nixpick" in text  # en-tête visible
            assert "lignes (README" in text  # marqueur de troncature
            assert "background_opacity" not in text  # queue coupée proprement
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_terminal_trop_petit_affiche_un_message(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app = tui.TuiApp()
        from opentui.testing import test_render

        setup = await test_render(tui._make_app(app), {"width": 30, "height": 8})
        try:
            await _pump(setup, lambda: not app.loading.peek(), timeout=4.0)
            text = _text(setup)
            assert "terminal 30×8" in text
            assert "40×12" in text
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_colle_presse_papiers_dans_la_recherche(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app, setup = await _boot()
        try:
            setup.mock_input.paste_text("firefox")
            await _pump(setup, timeout=0.2)
            assert app.query.peek() == "firefox"
            assert app.focus.peek() == "search"
            # coller des retours à la ligne ne casse pas la requête
            app.set_query("")
            await _pump(setup, timeout=0.1)
            setup.mock_input.paste_text("kitty\nterminal")
            await _pump(setup, timeout=0.2)
            assert app.query.peek() == "kitty terminal"
        finally:
            setup.renderer.stop()

    _run(scenario())


def test_indice_detail_elliptique_sur_colonne_etroite(tui_env: dict[str, Any]) -> None:
    async def scenario() -> None:
        app = tui.TuiApp()
        app.dims.set((40, 24))
        c = tui.TuiApp._colors()
        row = tui.ResultRow(
            attr="an-extremely-long-attribute-name-that-never-fits",
            version="1.2.3",
            description="x",
        )
        app.rows.set([row])
        lines = app._detail_for_row(row, c)
        from opentui.structs import display_width

        inner = max(1, tui._split_widths(40)[1] - 4)
        for node in lines:
            content = getattr(node, "_content", None)
            if isinstance(content, str) and content:
                assert display_width(content) <= inner, content
        hint = getattr(lines[-1], "_content", "")
        assert "ajouter" in hint  # le message reste identifiable

    _run(scenario())
