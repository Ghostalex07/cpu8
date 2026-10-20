"""Check the RTL line coverage reported by Verilator against a budget.

The input is the lcov ``.info`` file that ``make coverage`` writes with
``verilator_coverage -write-info``.  Only the ``DA:<line>,<count>`` records are
used: each one is a source line, and a count of zero means it was never
executed.  The check fails (exit status 1) when the global line percentage is
below ``MIN_LINE_PCT``.

Usage::

    python3 tools/coverage_report.py build/verilator-cov/coverage.info
    python3 tools/coverage_report.py --min 90 build/verilator-cov/coverage.info
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

# The demo suite reaches 99.4 % today; the remaining lines are defensive
# ``default:`` branches that no instruction can reach.  Keep a little headroom
# so that a new module does not fail because of a single untested line.
MIN_LINE_PCT = 95.0

_DA_RE = re.compile(r"^DA:(\d+),(\d+)")


def parse(text: str) -> tuple[int, int]:
    """Return ``(covered, total)`` line counters from an lcov ``.info`` file."""
    total = 0
    covered = 0
    for line in text.splitlines():
        match = _DA_RE.match(line)
        if match is None:
            continue
        total += 1
        if int(match.group(2)) > 0:
            covered += 1
    if total == 0:
        raise ValueError("no DA: records found in the coverage report")
    return covered, total


def check(covered: int, total: int, minimum: float = MIN_LINE_PCT) -> list[str]:
    """Return the budget failures (empty when the coverage is good enough)."""
    pct = 100.0 * covered / total
    if pct + 1e-9 < minimum:
        return [f"{covered}/{total} lines ({pct:.1f} %) is below the {minimum:.0f} % minimum"]
    return []


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    minimum = MIN_LINE_PCT
    if "--min" in args:
        index = args.index("--min")
        try:
            minimum = float(args[index + 1])
        except (IndexError, ValueError):
            print(
                "usage: coverage_report.py [--min PCT] <coverage.info>",
                file=sys.stderr,
            )
            return 2
        del args[index : index + 2]
        if not math.isfinite(minimum):
            print("coverage_report: --min must be a finite number", file=sys.stderr)
            return 2
    if len(args) != 1:
        print(
            "usage: coverage_report.py [--min PCT] <coverage.info>",
            file=sys.stderr,
        )
        return 2

    try:
        text = Path(args[0]).read_text()
    except OSError as exc:
        print(f"coverage_report: {exc}", file=sys.stderr)
        return 2

    try:
        covered, total = parse(text)
    except ValueError as exc:
        print(f"coverage_report: {exc}", file=sys.stderr)
        return 1

    failures = check(covered, total, minimum)
    pct = 100.0 * covered / total
    print(f"COVERAGE: {covered}/{total} lines ({pct:.1f} %), minimum {minimum:.0f} %")
    for failure in failures:
        print(f"coverage_report: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
