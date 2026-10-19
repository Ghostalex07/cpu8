#!/usr/bin/env python3
"""Tests for ``tools/fpga_report.py`` (the FPGA area/timing budget check).

They feed synthetic ``nextpnr-ice40`` reports to the parser and the budget
check, so no synthesis tool is required.

Run with ``make pytools`` or ``python3 -m pytest tools/test_fpga_report.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fpga_report  # noqa: E402

# A trimmed but realistic fragment of the nextpnr-ice40 output.
REPORT = """
Info: Device utilisation:
Info: \t         ICESTORM_LC:     823/   1280    64%
Info: \t        ICESTORM_RAM:       1/     16     6%
Info: Max frequency for clock 'clk$SB_IO_IN_$glb_clk': 14.84 MHz (PASS at 12.00 MHz)
"""


def test_parse_extracts_lc_and_fmax():
    assert fpga_report.parse(REPORT) == (823, 14.84)


def test_parse_uses_the_slowest_clock():
    text = REPORT + "Info: Max frequency for clock 'other': 9.5 MHz\n"
    assert fpga_report.parse(text) == (823, 9.5)


def test_check_accepts_fitting_design():
    assert fpga_report.check(823, 14.84) == []


def test_check_rejects_oversized_design():
    errors = fpga_report.check(fpga_report.MAX_LC + 1, 14.84)
    assert any("logic cells" in message for message in errors)


def test_check_rejects_slow_design():
    errors = fpga_report.check(823, fpga_report.MIN_FMAX_MHZ - 0.1)
    assert any("Fmax" in message for message in errors)


def test_parse_rejects_report_without_utilisation():
    with pytest.raises(ValueError, match="logic"):
        fpga_report.parse("Info: nothing to see here")


def test_main_returns_zero_for_a_fitting_report(tmp_path, capsys):
    log = tmp_path / "fpga.log"
    log.write_text(REPORT, encoding="utf-8")
    assert fpga_report.main([str(log)]) == 0
    assert "823/1280 LCs (64 %), Fmax 14.84 MHz" in capsys.readouterr().out


def test_main_fails_on_a_missing_report(tmp_path):
    assert fpga_report.main([str(tmp_path / "absent.log")]) == 2
