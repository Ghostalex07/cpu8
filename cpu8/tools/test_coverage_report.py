"""Tests for tools/coverage_report.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import coverage_report  # noqa: E402

INFO = """TN:
SF:/tmp/rtl/alu.v
DA:1,1
DA:2,3
DA:3,0
BRDA:1,0,a:0->1,1
BRDA:1,0,a:1->0,1
BRDA:2,0,b:0->1,1
BRDA:2,0,b:1->0,0
end_of_record
SF:/tmp/rtl/cpu.v
DA:10,1
end_of_record
"""


def test_parse_counts_covered_and_total() -> None:
    assert coverage_report.parse(INFO) == (3, 4)


def test_parse_ignores_the_optional_checksum() -> None:
    assert coverage_report.parse("DA:7,1,abcdef\n") == (1, 1)


def test_parse_without_records_is_an_error() -> None:
    with pytest.raises(ValueError, match="no DA: records"):
        coverage_report.parse("TN:\n")


def test_parse_branches_counts_brda_records() -> None:
    assert coverage_report.parse_branches(INFO) == (3, 4)


def test_parse_branches_treats_a_dash_as_not_covered() -> None:
    assert coverage_report.parse_branches("BRDA:1,0,x:0->1,-\n") == (0, 1)


def test_check_branches_accepts_a_report_above_the_minimum() -> None:
    assert coverage_report.check_branches(96, 100) == []


def test_check_branches_rejects_a_report_below_the_minimum() -> None:
    failures = coverage_report.check_branches(94, 100)
    assert failures and "94/100 branches" in failures[0]


def test_check_branches_skips_a_report_without_points() -> None:
    assert coverage_report.check_branches(0, 0) == []


def test_check_accepts_a_report_above_the_minimum() -> None:
    assert coverage_report.check(96, 100) == []


def test_check_rejects_a_report_below_the_minimum() -> None:
    failures = coverage_report.check(94, 100)
    assert failures and "94/100" in failures[0]


def test_main_returns_zero_and_prints_the_summary(tmp_path, capsys) -> None:
    path = tmp_path / "coverage.info"
    path.write_text(INFO)
    assert coverage_report.main(["--min", "70", "--min-branch", "70", str(path)]) == 0
    out = capsys.readouterr().out
    assert "COVERAGE: 3/4 lines (75.0 %), minimum 70 %" in out
    assert "COVERAGE: 3/4 branches (75.0 %), minimum 70.0 %" in out


def test_main_fails_below_the_line_minimum(tmp_path, capsys) -> None:
    path = tmp_path / "coverage.info"
    path.write_text(INFO)
    assert coverage_report.main(["--min", "90", "--min-branch", "70", str(path)]) == 1
    assert "below the 90 % minimum" in capsys.readouterr().err


def test_main_fails_below_the_branch_minimum(tmp_path, capsys) -> None:
    path = tmp_path / "coverage.info"
    path.write_text(INFO)
    assert coverage_report.main(["--min", "70", "--min-branch", "90", str(path)]) == 1
    assert "below the 90.0 % minimum" in capsys.readouterr().err


def test_main_skips_the_branch_gate_without_brda(tmp_path, capsys) -> None:
    path = tmp_path / "coverage.info"
    path.write_text("DA:1,1\n")
    assert coverage_report.main(["--min", "50", str(path)]) == 0
    out = capsys.readouterr().out
    assert "branch gate skipped" in out


def test_main_reports_a_missing_file(tmp_path) -> None:
    assert coverage_report.main([str(tmp_path / "nope.info")]) == 2


def test_main_requires_one_argument(capsys) -> None:
    assert coverage_report.main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_rejects_a_non_finite_minimum(tmp_path, capsys) -> None:
    path = tmp_path / "coverage.info"
    path.write_text(INFO)
    assert coverage_report.main(["--min", "nan", str(path)]) == 2
    assert "finite" in capsys.readouterr().err


def test_main_rejects_a_non_finite_branch_minimum(tmp_path, capsys) -> None:
    path = tmp_path / "coverage.info"
    path.write_text(INFO)
    assert coverage_report.main(["--min-branch", "inf", str(path)]) == 2
    assert "finite" in capsys.readouterr().err
