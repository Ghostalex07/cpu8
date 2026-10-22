"""Check the RTL line and toggle/branch coverage against a budget.

The input is the lcov ``.info`` file that ``make coverage`` writes with
``verilator_coverage -write-info``.  ``DA:<line>,<count>`` records give line
coverage; ``BRDA`` records give the toggle/branch points (Verilator labels them
``signal:0->1`` / ``signal:1->0``).  A count of zero means the point was never
executed.  The check fails (exit status 1) when either global percentage is
below its minimum.

Usage::

    python3 tools/coverage_report.py build/verilator-cov/coverage.info
    python3 tools/coverage_report.py --min 90 --min-branch 95 build/verilator-cov/coverage.info
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
# The demo suite reaches about 97 % of the BRDA toggle/branch points today.  The
# few uncovered points are structurally unreachable combinations (for example
# the reserved upper bits of the PUSHF flags byte) or resets after HLT, which
# the halt-based coverage run never performs.
MIN_BRANCH_PCT = 95.5

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


def parse_branches(text: str) -> tuple[int, int]:
    """Return ``(covered, total)`` BRDA toggle/branch counters."""
    total = 0
    covered = 0
    for line in text.splitlines():
        if not line.startswith("BRDA:"):
            continue
        count = line.rsplit(",", 1)[-1]
        total += 1
        if count != "-" and int(count) > 0:
            covered += 1
    return covered, total


def check(covered: int, total: int, minimum: float = MIN_LINE_PCT) -> list[str]:
    """Return the budget failures (empty when the coverage is good enough)."""
    pct = 100.0 * covered / total
    if pct + 1e-9 < minimum:
        return [f"{covered}/{total} lines ({pct:.1f} %) is below the {minimum:.0f} % minimum"]
    return []


def check_branches(covered: int, total: int, minimum: float = MIN_BRANCH_PCT) -> list[str]:
    """Return the BRDA budget failures (empty when it is good enough)."""
    if total == 0:
        return ["no BRDA: records found in the coverage report"]
    pct = 100.0 * covered / total
    if pct + 1e-9 < minimum:
        return [f"{covered}/{total} branches ({pct:.1f} %) is below the {minimum:.1f} % minimum"]
    return []


def _take_pct(args: list[str], name: str, default: float) -> tuple[float | None, int | None]:
    """Remove ``name VALUE`` from ``args``; return ``(value, error)``."""
    if name not in args:
        return default, None
    index = args.index(name)
    try:
        value = float(args[index + 1])
    except (IndexError, ValueError):
        print(
            "usage: coverage_report.py [--min PCT] [--min-branch PCT] <coverage.info>",
            file=sys.stderr,
        )
        return None, 2
    del args[index : index + 2]
    if not math.isfinite(value):
        print(f"coverage_report: {name} must be a finite number", file=sys.stderr)
        return None, 2
    return value, None


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    minimum, err = _take_pct(args, "--min", MIN_LINE_PCT)
    if err is not None:
        return err
    minimum_branch, err = _take_pct(args, "--min-branch", MIN_BRANCH_PCT)
    if err is not None:
        return err
    if len(args) != 1:
        print(
            "usage: coverage_report.py [--min PCT] [--min-branch PCT] <coverage.info>",
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

    branch_covered, branch_total = parse_branches(text)
    failures = check(covered, total, minimum) + check_branches(
        branch_covered, branch_total, minimum_branch
    )
    pct = 100.0 * covered / total
    print(f"COVERAGE: {covered}/{total} lines ({pct:.1f} %), minimum {minimum:.0f} %")
    if branch_total:
        branch_pct = 100.0 * branch_covered / branch_total
        print(
            f"COVERAGE: {branch_covered}/{branch_total} branches "
            f"({branch_pct:.1f} %), minimum {minimum_branch:.1f} %"
        )
    for failure in failures:
        print(f"coverage_report: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
