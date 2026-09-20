"""Tests doctor / --why (sans Nix réel)."""

from __future__ import annotations

import fcntl
import io
import json
from pathlib import Path

import pytest

import engine
from config import reset_settings_cache
from doctor import (
    Check,
    collect_checks,
    explain_why,
    format_doctor_report,
    packages_lock_path,
    run_doctor,
    run_why,
)

SAMPLE_NIX = """{ config, pkgs, ... }:
{
  environment.systemPackages = with pkgs; [
    firefox
    vim
  ];
}
"""


@pytest.fixture
def pkg_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "packages.nix"
    path.write_text(SAMPLE_NIX, encoding="utf-8")
    monkeypatch.setenv("NIXPICK_PACKAGES_FILE", str(path))
    monkeypatch.setenv("NIXPICK_PACKAGES_ANCHOR", "environment.systemPackages")
    reset_settings_cache()
    return path


@pytest.fixture
def fake_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "cache"
    cache.mkdir()
    index = cache / "index.json"
    index.write_text("{}")
    monkeypatch.setattr(engine, "INDEX_FILE", index)
    monkeypatch.setattr(engine, "CACHE_DIR", cache)
    return index


def _mock_nix_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "doctor.shutil.which",
        lambda name: "/usr/bin/nix-env" if name == "nix-env" else None,
    )


def test_explain_why_listed(pkg_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _ = pkg_file
    code = run_why("firefox")
    assert code == 0
    out = capsys.readouterr().out
    assert "firefox" in out
    assert "ligne" in out


def test_explain_why_missing(pkg_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _ = pkg_file
    code = run_why("unknown-pkg")
    assert code == 0
    assert "apparaît" in capsys.readouterr().out.lower()


def test_doctor_json(
    pkg_file: Path, fake_index: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _ = pkg_file
    _mock_nix_env(monkeypatch)
    code = run_doctor(as_json=True)
    assert code in (0, 1)
    data = json.loads(capsys.readouterr().out)
    assert "checks" in data
    assert isinstance(data["checks"], list)


def test_doctor_text_ok(
    pkg_file: Path, fake_index: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_nix_env(monkeypatch)
    buf = io.StringIO()
    assert run_doctor(out=buf) == 0
    assert "Tout semble en ordre" in buf.getvalue()


def test_doctor_missing_index(pkg_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "no-index.json"
    monkeypatch.setattr(engine, "INDEX_FILE", missing)
    _mock_nix_env(monkeypatch)
    idx = next(c for c in collect_checks() if c.label == "Cache index")
    assert not idx.ok


def test_doctor_active_lock(
    pkg_file: Path, fake_index: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = packages_lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w", encoding="utf-8") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        _mock_nix_env(monkeypatch)
        lock_check = next(c for c in collect_checks() if c.label == "Verrou d'édition")
        assert not lock_check.ok
        fcntl.flock(held.fileno(), fcntl.LOCK_UN)


def test_format_report_marks_failures() -> None:
    text = format_doctor_report(
        [Check("A", True, "ok"), Check("B", False, "bad")]
    )
    assert "[OK]" in text
    assert "[!!]" in text
    assert "1 point(s) à corriger" in text


def test_explain_why_invalid(pkg_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _ = pkg_file
    assert explain_why("../evil") == 2
    assert capsys.readouterr().err
