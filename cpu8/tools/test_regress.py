#!/usr/bin/env python3
"""Tests for the regression harness ``tools/regress.py``.

They cover argument parsing and the safety property that ``--update`` never
records traces from a ``.hex`` that does not match its ``.asm``.  No RTL
simulation is needed: the trace generator is stubbed in the update tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "asm"))

import regress  # noqa: E402


def _programa(tmp_path: Path, hex_bytes: list[int] | None) -> Path:
    asm = tmp_path / "prog.asm"
    asm.write_text("LDI A, 1\nHLT\n")
    if hex_bytes is not None:
        (tmp_path / "prog.hex").write_text("".join(f"{b:02X}\n" for b in hex_bytes))
    return asm


def test_unknown_option_is_rejected():
    with pytest.raises(SystemExit) as exc:
        regress.main(["regress.py", "--bogus"])
    assert exc.value.code == 2


def test_help_is_accepted():
    with pytest.raises(SystemExit) as exc:
        regress.main(["regress.py", "--help"])
    assert exc.value.code == 0


def test_negative_fuzz_is_rejected():
    with pytest.raises(SystemExit) as exc:
        regress.main(["regress.py", "--fuzz", "-1"])
    assert exc.value.code == 2


def test_update_refuses_a_stale_hex(tmp_path, monkeypatch, capsys):
    asm = _programa(tmp_path, [0x00])  # wrong on purpose
    monkeypatch.setattr(regress, "_programas", lambda: [asm])
    monkeypatch.setattr(regress, "GOLDEN", tmp_path / "golden")
    monkeypatch.setattr(regress, "TRACES", tmp_path / "golden" / "traces")

    def _no_debe_generar():
        raise AssertionError("traces must not be generated from a stale .hex")

    monkeypatch.setattr(regress, "_generar_trazas", _no_debe_generar)
    assert regress.actualizar() == 1
    assert "stale .hex" in capsys.readouterr().err
    assert not (tmp_path / "golden" / "hex.sha256").exists()


def test_update_uses_fresh_bytes_and_writes_nothing_on_failure(tmp_path, monkeypatch):
    asm = _programa(tmp_path, None)
    fresco = regress.assembler.ensamblar(asm.read_text())[0]
    (tmp_path / "prog.hex").write_text("".join(f"{b:02X}\n" for b in fresco))
    monkeypatch.setattr(regress, "_programas", lambda: [asm])
    monkeypatch.setattr(regress, "GOLDEN", tmp_path / "golden")
    monkeypatch.setattr(regress, "TRACES", tmp_path / "golden" / "traces")
    monkeypatch.setattr(regress, "_generar_trazas", lambda: ({"prog": "=== trace ===\n"}, tmp_path))
    assert regress.actualizar() == 0
    manifest = (tmp_path / "golden" / "hex.sha256").read_text()
    assert manifest.startswith("prog ")
    assert (tmp_path / "golden" / "traces" / "prog.trace").read_text() == "=== trace ===\n"
