#!/usr/bin/env python3
"""Tests for ``tools/difftest.py`` that do not need a Verilog simulator.

The RTL-side functions are stubbed; the real RTL comparison is covered by
``make difftest``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "asm"))

import difftest  # noqa: E402


def test_missing_tools_produce_a_clear_message(monkeypatch):
    monkeypatch.setattr(difftest.shutil, "which", lambda _: None)
    msg = difftest._comprobar_herramientas()
    assert msg is not None
    assert "iverilog" in msg and "not found in PATH" in msg


def test_main_returns_2_without_a_simulator(monkeypatch, capsys):
    monkeypatch.setattr(difftest.shutil, "which", lambda _: None)
    assert difftest.main(["--progs"]) == 2
    assert "iverilog" in capsys.readouterr().err


def test_run_iss_reports_how_many_irqs_were_taken():
    programa, _, _ = difftest.assembler.ensamblar("EI\nHLT\n.org 0x08\nHLT\n")
    dump, irqs = difftest.run_iss(programa, 20, irq_at=0)
    assert irqs == 1
    assert dump


@pytest.mark.parametrize(("irqs", "texto"), [(1, "taken"), (0, "not taken")])
def test_probar_labels_the_real_irq_status(monkeypatch, capsys, tmp_path, irqs, texto):
    lineas = ["I 00 00 00 00 00 00 00 00 00 00 00 F0", "END 00 00"]
    monkeypatch.setattr(difftest, "run_rtl", lambda *a: lineas)
    monkeypatch.setattr(difftest, "run_iss", lambda *a: (lineas, irqs))
    assert difftest.probar(
        "demo", "HLT\n", [0xF0], tmp_path / "x.vvp", 10, tmp_path / "fallos", irq_at=3
    )
    salida = capsys.readouterr().out
    assert f"[irq>=3, {texto}]" in salida


def test_comparar_detects_a_length_mismatch():
    ok, k, detalle = difftest.comparar(["I 00"], ["I 00", "END 00"])
    assert not ok
    assert k == 1
    assert "different lengths" in detalle
