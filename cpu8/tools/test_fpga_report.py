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
Info: Max frequency for clock 'clk$SB_IO_IN_$glb_clk': 18.42 MHz (PASS at 16.00 MHz)
"""


def test_parse_extracts_lc_fmax_and_ram():
    assert fpga_report.parse(REPORT) == (823, 18.42, 1)


def test_parse_uses_the_slowest_clock():
    text = REPORT + "Info: Max frequency for clock 'other': 9.5 MHz\n"
    assert fpga_report.parse(text) == (823, 9.5, 1)


def test_check_accepts_fitting_design():
    assert fpga_report.check(823, 18.42, 1) == []


def test_check_rejects_oversized_design():
    errors = fpga_report.check(fpga_report.MAX_LC + 1, 18.42, 1)
    assert any("logic cells" in message for message in errors)


def test_check_rejects_slow_design():
    errors = fpga_report.check(823, fpga_report.MIN_FMAX_MHZ - 0.1, 1)
    assert any("Fmax" in message for message in errors)


def test_check_rejects_missing_bram():
    errors = fpga_report.check(823, 18.42, 0)
    assert any("block RAM" in message for message in errors)


def test_check_rejects_extra_bram():
    errors = fpga_report.check(823, 18.42, 2)
    assert any("block RAM" in message for message in errors)


def test_parse_rejects_report_without_utilisation():
    with pytest.raises(ValueError, match="logic"):
        fpga_report.parse("Info: nothing to see here")


def test_parse_rejects_report_without_bram():
    text = "\n".join(line for line in REPORT.splitlines() if "ICESTORM_RAM" not in line)
    with pytest.raises(ValueError, match="block RAM"):
        fpga_report.parse(text)


def test_main_returns_zero_for_a_fitting_report(tmp_path, capsys):
    log = tmp_path / "fpga.log"
    log.write_text(REPORT, encoding="utf-8")
    assert fpga_report.main([str(log)]) == 0
    assert "823/1280 LCs (64 %), Fmax 18.42 MHz, RAM 1/16" in capsys.readouterr().out


def test_main_fails_on_a_missing_report(tmp_path):
    assert fpga_report.main([str(tmp_path / "absent.log")]) == 2


def test_parse_rejects_an_ignored_pcf_setting():
    text = REPORT + "Warning: Ignoring PCF setting '--pullup' for cell pmod_in[0]\n"
    with pytest.raises(ValueError, match="Ignoring PCF setting"):
        fpga_report.parse(text)


def test_parse_rejects_an_unmatched_constraint():
    text = REPORT + "Info: unmatched constraint pmod_in[8]\n"
    with pytest.raises(ValueError, match="unmatched constraint"):
        fpga_report.parse(text)


def test_main_fails_on_an_ignored_pcf_setting(tmp_path, capsys):
    log = tmp_path / "fpga.log"
    log.write_text(
        REPORT + "Warning: Ignoring PCF setting '--pullup' for cell pmod_in[0]\n",
        encoding="utf-8",
    )
    assert fpga_report.main([str(log)]) == 1
    assert "Ignoring PCF setting" in capsys.readouterr().err
