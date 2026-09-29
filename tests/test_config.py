"""config.py : TOML commenté, validation des types (audit #3 UX-10, QUA-03)."""

from __future__ import annotations

from pathlib import Path

import pytest

import config
from config import (
    get_settings,
    load_transparent_background,
    reset_settings_cache,
    save_language,
    save_packages_file,
    save_transparent_background,
)


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.delenv("NIXPICK_PACKAGES_FILE", raising=False)
    monkeypatch.delenv("NIXPICK_PACKAGES_ANCHOR", raising=False)
    monkeypatch.delenv("NIXPICK_REBUILD_COMMAND", raising=False)
    reset_settings_cache()
    return tmp_path


def test_transparent_commentaire_inline_lu(cfg: Path) -> None:
    (cfg / "config.toml").write_text(
        "transparent_background = true # kitty\n", encoding="utf-8"
    )
    assert load_transparent_background() is True


def test_save_remplace_meme_avec_commentaire_inline(cfg: Path) -> None:
    (cfg / "config.toml").write_text(
        "transparent_background = true # kitty\n", encoding="utf-8"
    )
    save_transparent_background(False)
    text = (cfg / "config.toml").read_text(encoding="utf-8")
    assert "transparent_background = false" in text
    assert load_transparent_background() is False


def test_save_ajoute_si_cle_seulement_en_commentaire(cfg: Path) -> None:
    (cfg / "config.toml").write_text(
        "# transparent_background = false\n", encoding="utf-8"
    )
    save_transparent_background(True)
    assert load_transparent_background() is True


def test_anchor_non_string_refusee(cfg: Path) -> None:
    (cfg / "config.toml").write_text(
        "[nixpick]\npackages_anchor = 123\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="packages_anchor"):
        get_settings()


def test_anchor_vide_refusee(cfg: Path) -> None:
    (cfg / "config.toml").write_text(
        '[nixpick]\npackages_anchor = "   "\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="packages_anchor"):
        get_settings()


def test_packages_file_non_string_refuse(cfg: Path) -> None:
    (cfg / "config.toml").write_text(
        "[nixpick]\npackages_file = 123\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="packages_file"):
        get_settings()


def test_save_language_upsert(cfg: Path) -> None:
    save_language("en")
    text = (cfg / "config.toml").read_text(encoding="utf-8")
    assert 'language = "en"' in text
    save_language("fr")
    assert (cfg / "config.toml").read_text(encoding="utf-8").count("language =") == 1


def test_save_language_inconnue_refusee(cfg: Path) -> None:
    with pytest.raises(ValueError, match="langue"):
        save_language("de")


def test_save_packages_file_persiste_et_recharge(cfg: Path) -> None:
    target = cfg / "custom.nix"
    target.write_text("{ }\n", encoding="utf-8")
    saved = save_packages_file(str(target))
    assert saved == target.resolve()
    text = (cfg / "config.toml").read_text(encoding="utf-8")
    assert "custom.nix" in text
    reset_settings_cache()
    assert get_settings().packages_file.resolve() == target.resolve()


def test_save_packages_file_rejette_non_nix(cfg: Path) -> None:
    with pytest.raises(ValueError, match="\\.nix"):
        save_packages_file("/tmp/readme.txt")
