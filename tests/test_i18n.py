"""i18n : parité FR/EN du catalogue, résolution, repli."""

from __future__ import annotations

import pytest

import i18n
from i18n import set_language, t


@pytest.fixture(autouse=True)
def _french_by_default():
    set_language("fr")
    yield
    set_language("fr")


def test_catalogue_parite_fr_en() -> None:
    """Toute clé FR existe en EN (et inversement) : pas de trou."""
    fr_keys = set(i18n.STRINGS["fr"])
    en_keys = set(i18n.STRINGS["en"])
    assert fr_keys, "catalogue FR vide ?"
    assert fr_keys == en_keys, (
        f"FR sans EN : {sorted(fr_keys - en_keys)[:5]} / "
        f"EN sans FR : {sorted(en_keys - fr_keys)[:5]}"
    )


def test_gabarits_valides() -> None:
    """Chaque gabarit {x} se formate sans NameError."""
    for lang in ("fr", "en"):
        set_language(lang)
        for key, template in i18n.STRINGS[lang].items():
            values = {
                name: (2.0 if name == "age" else "X")
                for name in _placeholders(template)
            }
            try:
                template.format(**values)
            except Exception as err:  # noqa: BLE001 — le test doit citer la clé fautive
                pytest.fail(f"{lang}.{key} : gabarit invalide ({err})")


def _placeholders(template: str) -> set[str]:
    import string

    return {
        field
        for _, field, _, _ in string.Formatter().parse(template)
        if field and not field[0].isdigit()
    }


def test_set_language_inconnue_replie_fr() -> None:
    assert set_language("de") == "fr"
    assert set_language("") == "fr"
    assert set_language("en") == "en"
    assert i18n.get_language() == "en"


def test_t_repli_fr_puis_cle() -> None:
    set_language("en")
    assert t("cli.cancelled") == "Aborted."
    assert t("cle_inexistante_zz") == "cle_inexistante_zz"
