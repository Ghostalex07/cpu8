#!/usr/bin/env python3
"""Differential fuzz: RTL (``tb/cpu_dump_tb.v``) against the ``tools/iss.py`` model.

For each program (the ``programs/*.asm`` and random programs from
``tools/fuzz.py``) it runs the RTL and the ISS and compares, instruction by
instruction, registers A-D, flags Z/C/N/V, SP, PC and (at the end) the contents
of RAM and the OUT sequence.  The first disagreement is reported with context
and the offending program is saved so it can be reproduced.

Usage::

    python3 tools/difftest.py                 # 100 random + the demo programs (max 4096)
    python3 tools/difftest.py --count 500 --seed 1234
    python3 tools/difftest.py --progs         # only the programs/*.asm
    make difftest
"""

from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(RAIZ / "asm"))

import assembler  # noqa: E402
import disasm  # noqa: E402
import fuzz  # noqa: E402
import iss  # noqa: E402

RTL_DIR = RAIZ / "rtl"
TB_DIR = RAIZ / "tb"
BUILD = RAIZ / "build"
PROG_DIR = RAIZ / "programs"
IRQ_VECTOR = 0x08  # must match cpu_dump_tb.v


def _tool(nombre: str, alt: str) -> str:
    return shutil.which(nombre) or alt


IVERILOG = _tool("iverilog", "iverilog")
VVP = _tool("vvp", "vvp")


def compilar_tb() -> Path:
    BUILD.mkdir(exist_ok=True)
    salida = BUILD / "cpu_dump.vvp"
    fuentes = [str(TB_DIR / "cpu_dump_tb.v")] + sorted(str(p) for p in RTL_DIR.glob("*.v"))
    subprocess.run(
        [IVERILOG, "-g2012", "-Wall", "-s", "cpu_dump_tb", "-o", str(salida), *fuentes],
        check=True)
    return salida


def run_rtl(vvp: Path, hexfile: Path, max_steps: int,
            irq_at: int | None = None) -> list[str]:
    nivel = 10 ** 9 if irq_at is None else irq_at
    res = subprocess.run(
        [VVP, str(vvp), f"+hex={hexfile}", f"+max={max_steps}", f"+irq={nivel}"],
        check=True, capture_output=True, text=True)
    return [ln for ln in res.stdout.splitlines()
            if ln[:2] in ("I ", "M ", "END") or ln.startswith("END")]


def run_iss(mem: list[int], max_steps: int,
            irq_at: int | None = None) -> list[str]:
    modelo = iss.ISS(mem, irq_vector=IRQ_VECTOR, irq_at=irq_at)
    modelo.run(max_steps)
    return modelo.dump()


def _norm(lineas: list[str]) -> list[str]:
    return [ln.upper() for ln in lineas]


def comparar(rtl: list[str], modelo: list[str]) -> tuple[bool, int, str]:
    a, b = _norm(rtl), _norm(modelo)
    for k in range(min(len(a), len(b))):
        if a[k] != b[k]:
            return False, k, f"RTL : {a[k]}\n   ISS : {b[k]}"
    if len(a) != len(b):
        return False, min(len(a), len(b)), f"different lengths: RTL {len(a)}, ISS {len(b)}"
    return True, len(a), ""


def _guardar_fallo(destino: Path, fuente: str, hexfile: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "fallo.asm").write_text(fuente)
    shutil.copy(hexfile, destino / "fallo.hex")


def probar(nombre: str, fuente: str, bytes_prog: list[int], vvp: Path,
           max_steps: int, dir_fallos: Path,
           irq_at: int | None = None) -> bool:
    with tempfile.TemporaryDirectory() as td:
        hexfile = Path(td) / "prog.hex"
        hexfile.write_text("\n".join(f"{b:02X}" for b in bytes_prog) + "\n")
        rtl = run_rtl(vvp, hexfile, max_steps, irq_at)
        modelo = run_iss(bytes_prog, max_steps, irq_at)
        ok, k, detalle = comparar(rtl, modelo)
        if ok:
            etiqueta = "" if irq_at is None else f" [irq>={irq_at}]"
            print(f"  ok   {nombre}{etiqueta} ({len(_norm(rtl)) - 2} instructions)")
            return True
        print(f"  FAIL {nombre} at instruction #{k}"
              + ("" if irq_at is None else f" [irq>={irq_at}]"))
        print(f"   {detalle}")
        print("   --- program ---")
        for ln in disasm.desensamblar(bytes_prog):
            print(f"   {ln}")
        _guardar_fallo(dir_fallos / nombre, fuente, hexfile)
        print(f"   saved to {dir_fallos / nombre}/")
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=100, help="random programs")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max", type=int, default=4096, help="instruction cap")
    ap.add_argument("--progs", action="store_true", help="only programs/*.asm")
    ap.add_argument("--instr", type=int, default=40, help="instructions per random program")
    ap.add_argument("--irq-prob", type=float, default=0.5,
                    help="prob. of running a random program with irq active")
    args = ap.parse_args()

    vvp = compilar_tb()
    dir_fallos = BUILD / "difftest-fallos"
    if dir_fallos.exists():
        shutil.rmtree(dir_fallos)
    fallos = 0
    probados = 0

    print("=== programs/*.asm ===")
    for p in sorted(PROG_DIR.glob("*.asm")):
        # pmod.asm is an endless hardware demo; top_pmod_tb covers it.
        if p.stem == "pmod":
            continue
        src = p.read_text()
        try:
            b, _, _ = assembler.ensamblar(src)
        except assembler.AssemblerError as e:
            print(f"  FAIL {p.name}: does not assemble: {e}")
            fallos += 1
            continue
        probados += 1
        if not probar(p.stem, src, b, vvp, args.max, dir_fallos):
            fallos += 1

    if not args.progs:
        print(f"=== {args.count} random programs (seed {args.seed}) ===")
        for i in range(args.count):
            rng = random.Random(args.seed * 1000003 + i)
            src = fuzz.generar_fuente(rng, args.instr)
            try:
                b, _, _ = assembler.ensamblar(src)
            except assembler.AssemblerError as e:
                print(f"  FAIL fuzz_{args.seed}_{i}: generated program does not "
                      f"assemble: {e}")
                fallos += 1
                continue
            probados += 1
            # About half of the programs are also run with irq active to cover
            # the interrupt path (previously only covered by irqtest).
            irq_at = None
            if rng.random() < args.irq_prob:
                irq_at = rng.randrange(0, max(2, args.max // 8 + 2))
            if not probar(f"fuzz_{args.seed}_{i}", src, b, vvp, args.max,
                          dir_fallos, irq_at):
                fallos += 1

    if fallos:
        print(f"\nDIFFERENTIAL: {fallos} FAILURES")
        return 1
    if probados == 0:
        print("\nDIFFERENTIAL: no programs were tested")
        return 1
    print("\nDIFFERENTIAL: ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
