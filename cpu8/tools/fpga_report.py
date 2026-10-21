#!/usr/bin/env python3
"""Check the FPGA synthesis report against the area/timing budget.

Parses the ``nextpnr-ice40`` output produced by ``make fpga`` for the
iCEstick (iCE40HX1K) and fails if the design no longer fits comfortably or
misses the 12 MHz timing target.  CI runs it after every synthesis.

Usage::

    make fpga 2>&1 | tee build/fpga.log
    python3 tools/fpga_report.py build/fpga.log

Budgets (iCE40HX1K, tq144, 1280 logic cells and 16 block RAMs):

- logic cells ``<= MAX_LC`` (80 % of the device),
- ``Fmax >= MIN_FMAX_MHZ`` (the design clock target),
- exactly ``EXPECTED_RAM`` block RAM, so the program RAM keeps inferring BRAM
  instead of silently expanding into hundreds of logic cells.
"""

from __future__ import annotations

import re
import sys

DEVICE_LC = 1280
MAX_LC = 1024  # 80 % of the device, a hard area budget with headroom
MIN_FMAX_MHZ = 12.0  # design clock target
DEVICE_RAM = 16
EXPECTED_RAM = 1  # ram.v must keep inferring one block RAM

LC_RE = re.compile(r"ICESTORM_LC:\s+(\d+)/\s+(\d+)")
RAM_RE = re.compile(r"ICESTORM_RAM:\s+(\d+)/\s+(\d+)")
FMAX_RE = re.compile(r"Max frequency for clock '[^']*':\s+([0-9.]+)\s*MHz")

# A constraint that nextpnr did not understand (for example a mistyped pin
# attribute) leaves the design silently unconstrained or without the attribute.
CRITICAL_WARNINGS = ("Ignoring PCF setting", "unmatched constraint")


def parse(text: str) -> tuple[int, float, int]:
    """Extract logic cells, worst Fmax and block RAMs from a nextpnr report.

    A PCF constraint that nextpnr ignored or could not match is a hard error:
    otherwise the build can pass with the pin unconstrained or the attribute
    (for example a pull-up) silently disabled.
    """
    for warning in CRITICAL_WARNINGS:
        if warning in text:
            raise ValueError(f"nextpnr reported '{warning}': fix the PCF constraints")
    lc = LC_RE.search(text)
    ram = RAM_RE.search(text)
    fmax = [float(value) for value in FMAX_RE.findall(text)]
    if lc is None:
        raise ValueError("logic-cell utilisation not found in the report")
    if ram is None:
        raise ValueError("block RAM utilisation not found in the report")
    if not fmax:
        raise ValueError("max frequency not found in the report")
    return int(lc.group(1)), min(fmax), int(ram.group(1))


def check(lc: int, fmax: float, ram: int) -> list[str]:
    """Return the list of budget failures (empty when the design fits)."""
    errors: list[str] = []
    if lc > MAX_LC:
        pct = 100.0 * lc / DEVICE_LC
        errors.append(f"{lc} logic cells exceed the {MAX_LC}-LC budget ({pct:.0f} %)")
    if fmax < MIN_FMAX_MHZ:
        errors.append(f"Fmax {fmax:.2f} MHz is below the {MIN_FMAX_MHZ:.0f} MHz target")
    if ram != EXPECTED_RAM:
        errors.append(
            f"{ram} block RAMs used; expected exactly {EXPECTED_RAM} "
            "(the program RAM must infer one BRAM)"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: fpga_report.py <nextpnr-log>", file=sys.stderr)
        return 2
    try:
        with open(args[0], encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError as exc:
        print(f"FPGA: cannot read {args[0]}: {exc}", file=sys.stderr)
        return 2

    try:
        lc, fmax, ram = parse(text)
    except ValueError as exc:
        print(f"FPGA: {exc}", file=sys.stderr)
        return 1

    pct = 100.0 * lc / DEVICE_LC
    print(f"FPGA: {lc}/{DEVICE_LC} LCs ({pct:.0f} %), Fmax {fmax:.2f} MHz, RAM {ram}/{DEVICE_RAM}")

    errors = check(lc, fmax, ram)
    for message in errors:
        print(f"FPGA: ERROR: {message}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
