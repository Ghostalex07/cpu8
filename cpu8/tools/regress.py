#!/usr/bin/env python3
"""Regression harness for cpu8 (Fase 10).

Checks that the CPU and the tools do not change behaviour:

1. **Bytes**: assembling each ``programs/*.asm`` yields exactly the same bytes
   as the golden reference (``tools/golden/hex.sha256``).  Detects any regression
   in the encoder or in the label analysis.
2. **Trace**: running each program produces the same trace (register/flag state
   after each instruction) as the golden one
   (``tools/golden/traces/<name>.trace``).  Detects changes in the RTL even if
   the final output does not change.
3. **Fuzz**: valid random programs are assembled, disassembled and assembled
   again; the bytes must match (assembler/disassembler round-trip).

Usage::

    python3 tools/regress.py             # checks against the golden reference
    python3 tools/regress.py --update    # (re)generates the golden reference
    python3 tools/regress.py --fuzz 500  # number of random programs (0 = none)

The harness returns exit code 0 if everything passes and 1 if there are
failures, so it can be used in CI (``make regress``).
"""

from __future__ import annotations

import hashlib
import random
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "asm"))
sys.path.insert(0, str(RAIZ / "tools"))

import assembler  # noqa: E402
import disasm  # noqa: E402
import fuzz  # noqa: E402

GOLDEN = RAIZ / "tools" / "golden"
TRACES = GOLDEN / "traces"
# irq.asm needs the irq signal (covered by `make irqtest`); with irq=0 its trace
# adds nothing, so it is excluded from the trace check (not from the bytes one).
TRACE_EXCLUIDOS = {"irq"}


def _programas() -> list[Path]:
    return sorted((RAIZ / "programs").glob("*.asm"))


def _sha(bs: list[int]) -> str:
    return hashlib.sha256(bytes(bs)).hexdigest()


def _hex_actuales() -> dict[str, str]:
    return {p.stem: _sha(assembler.ensamblar(p.read_text())[0]) for p in _programas()}


def _compilar_traza() -> Path:
    vvp = RAIZ / "build" / "regress_trace.vvp"
    vvp.parent.mkdir(parents=True, exist_ok=True)
    rtl = sorted((RAIZ / "rtl").glob("*.v"))
    subprocess.run(
        ["iverilog", "-g2012", "-Wall", "-s", "cpu_trace_tb", "-o", str(vvp),
         str(RAIZ / "tb" / "cpu_trace_tb.v"), *map(str, rtl)],
        check=True)
    return vvp


def _traza(vvp: Path, stem: str) -> str:
    r = subprocess.run(
        ["vvp", str(vvp), f"+hex=programs/{stem}.hex"],
        cwd=RAIZ, capture_output=True, text=True, check=True)
    # The iverilog runtime prints environment-dependent diagnostics to stdout
    # and they must NOT be part of the golden trace:
    #   - 11.0: the $readmemh warning ("Not enough words ...") with the ABSOLUTE
    #     path of the testbench.
    #   - 12.0: "<path>:<line>: $finish called at <time> (1ps)".
    # Both carry paths/times that change between machines and versions.
    ruido = ("WARNING:", "$finish called at", "ERROR:", "$fatal")
    lineas = [ln for ln in r.stdout.splitlines()
              if not any(m in ln for m in ruido)]
    return "\n".join(lineas) + ("\n" if lineas else "")


def actualizar() -> int:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    TRACES.mkdir(parents=True, exist_ok=True)
    (GOLDEN / "hex.sha256").write_text(
        "".join(f"{n} {h}\n" for n, h in sorted(_hex_actuales().items())))
    vvp = _compilar_traza()
    for p in _programas():
        if p.stem not in TRACE_EXCLUIDOS:
            (TRACES / f"{p.stem}.trace").write_text(_traza(vvp, p.stem))
    print(f"Golden reference updated in {GOLDEN.relative_to(RAIZ)}/")
    return 0


def _comprobar_bytes() -> int:
    man = GOLDEN / "hex.sha256"
    if not man.exists():
        print(f"MISSING {man.relative_to(RAIZ)} (run `make regress-update`)")
        return 1
    esperado = dict(ln.split() for ln in man.read_text().splitlines() if ln.strip())
    actual = _hex_actuales()
    fallos = 0
    for n in sorted(set(esperado) | set(actual)):
        if esperado.get(n) != actual.get(n):
            print(f"  BYTES FAIL {n}: {esperado.get(n)} != {actual.get(n)}")
            fallos += 1
    print(f"  bytes: {len(actual)} programs, {fallos} failures")
    return fallos


def _primera_diferencia(esperado: str, actual: str) -> str:
    """Description of the first line that differs, with repr (shows spaces)."""
    ea, aa = esperado.splitlines(), actual.splitlines()
    for i in range(max(len(ea), len(aa))):
        le = ea[i] if i < len(ea) else "<missing>"
        la = aa[i] if i < len(aa) else "<missing>"
        if le != la:
            return (f"    line {i + 1}:\n"
                    f"      expected: {le!r}\n"
                    f"      actual  : {la!r}")
    return "    (no line-by-line differences)"


def _comprobar_trazas() -> int:
    vvp = _compilar_traza()
    dump = RAIZ / "build" / "regress"
    fallos = 0
    n = 0
    for p in _programas():
        if p.stem in TRACE_EXCLUIDOS:
            continue
        g = TRACES / f"{p.stem}.trace"
        if not g.exists():
            print(f"  MISSING golden trace {g.relative_to(RAIZ)}")
            fallos += 1
            continue
        n += 1
        esperado = g.read_text()
        actual = _traza(vvp, p.stem)
        if actual != esperado:
            print(f"  TRACE FAIL {p.stem} "
                  f"(`make trace PROG=programs/{p.stem}` to inspect)")
            print(_primera_diferencia(esperado, actual))
            dump.mkdir(parents=True, exist_ok=True)
            (dump / f"{p.stem}.expected.trace").write_text(esperado)
            (dump / f"{p.stem}.actual.trace").write_text(actual)
            fallos += 1
    if fallos:
        print(f"  traces dumped in {dump.relative_to(RAIZ)}/ (expected/actual)")
    print(f"  traces: {n} programs, {fallos} failures")
    return fallos


def _comprobar_fuzz(cuenta: int) -> int:
    rng = random.Random(0xC0FFEE)
    fallos = 0
    for i in range(cuenta):
        src = fuzz.generar_fuente(rng, rng.randrange(1, 40))
        try:
            b1 = assembler.ensamblar(src)[0]
            b2 = assembler.ensamblar(
                "\n".join(disasm.desensamblar_crudo(b1)) + "\n")[0]
        except Exception as e:  # noqa: BLE001 (we want to see any failure)
            print(f"  FAIL fuzz #{i}: {e}\n{src}")
            fallos += 1
            continue
        if b1 != b2:
            print(f"  FAIL fuzz #{i}: the bytes do not match\n{src}")
            fallos += 1
    print(f"  fuzz round-trip: {cuenta} programs, {fallos} failures")
    return fallos


def main(argv: list[str]) -> int:
    args = argv[1:]
    if "--update" in args:
        return actualizar()
    fuzz_n = 200
    if "--fuzz" in args:
        k = args.index("--fuzz")
        if k + 1 >= len(args):
            print("regress: --fuzz expects a number", file=sys.stderr)
            return 2
        try:
            fuzz_n = int(args[k + 1])
        except ValueError:
            print(f"regress: invalid --fuzz value '{args[k + 1]}'", file=sys.stderr)
            return 2
    print("=== cpu8 regression ===")
    fallos = _comprobar_bytes() + _comprobar_trazas()
    if fuzz_n:
        fallos += _comprobar_fuzz(fuzz_n)
    if fallos:
        print(f"REGRESSION: {fallos} failures")
        return 1
    print("REGRESSION: ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
