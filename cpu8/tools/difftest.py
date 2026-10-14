#!/usr/bin/env python3
"""Fuzz diferencial: RTL (``tb/cpu_dump_tb.v``) contra el modelo ``tools/iss.py``.

Para cada programa (los ``programs/*.asm`` y programas aleatorios de
``tools/fuzz.py``) ejecuta el RTL y el ISS y compara, instruccion a instruccion,
registros A-D, flags Z/C/N/V, SP, PC y (al final) el contenido de la RAM y la
secuencia de OUT.  El primer desacuerdo se reporta con contexto y el programa
culpable se guarda para reproducirlo.

Uso::

    python3 tools/difftest.py                 # 100 aleatorios + los programas demo
    python3 tools/difftest.py --count 500 --seed 1234
    python3 tools/difftest.py --progs         # solo los programs/*.asm
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
IRQ_VECTOR = 0x08  # debe coincidir con cpu_dump_tb.v


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


def run_rtl(vvp: Path, hexfile: Path, max_steps: int) -> list[str]:
    res = subprocess.run(
        [VVP, str(vvp), f"+hex={hexfile}", f"+max={max_steps}"],
        check=True, capture_output=True, text=True)
    return [ln for ln in res.stdout.splitlines()
            if ln[:2] in ("I ", "M ", "END") or ln.startswith("END")]


def run_iss(mem: list[int], max_steps: int) -> list[str]:
    modelo = iss.ISS(mem, irq_vector=IRQ_VECTOR)
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
        return False, min(len(a), len(b)), f"longitudes distintas: RTL {len(a)}, ISS {len(b)}"
    return True, len(a), ""


def _guardar_fallo(destino: Path, fuente: str, hexfile: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "fallo.asm").write_text(fuente)
    shutil.copy(hexfile, destino / "fallo.hex")


def probar(nombre: str, fuente: str, bytes_prog: list[int], vvp: Path,
           max_steps: int, dir_fallos: Path) -> bool:
    with tempfile.TemporaryDirectory() as td:
        hexfile = Path(td) / "prog.hex"
        hexfile.write_text("\n".join(f"{b:02X}" for b in bytes_prog) + "\n")
        rtl = run_rtl(vvp, hexfile, max_steps)
        modelo = run_iss(bytes_prog, max_steps)
        ok, k, detalle = comparar(rtl, modelo)
        if ok:
            print(f"  ok   {nombre} ({len(_norm(rtl)) - 2} instrucciones)")
            return True
        print(f"  FALLO {nombre} en la instruccion #{k}")
        print(f"   {detalle}")
        print("   --- programa ---")
        for ln in disasm.desensamblar(bytes_prog):
            print(f"   {ln}")
        _guardar_fallo(dir_fallos / nombre, fuente, hexfile)
        print(f"   guardado en {dir_fallos / nombre}/")
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=100, help="programas aleatorios")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max", type=int, default=2000, help="tope de instrucciones")
    ap.add_argument("--progs", action="store_true", help="solo programs/*.asm")
    ap.add_argument("--instr", type=int, default=40, help="instrucciones por programa aleatorio")
    args = ap.parse_args()

    vvp = compilar_tb()
    dir_fallos = BUILD / "difftest-fallos"
    fallos = 0

    print("=== programs/*.asm ===")
    for p in sorted(PROG_DIR.glob("*.asm")):
        src = p.read_text()
        try:
            b, _, _ = assembler.ensamblar(src)
        except assembler.AssemblerError as e:
            print(f"  SKIP {p.name}: {e}")
            continue
        if not probar(p.stem, src, b, vvp, args.max, dir_fallos):
            fallos += 1

    if not args.progs:
        print(f"=== {args.count} programas aleatorios (semilla {args.seed}) ===")
        for i in range(args.count):
            rng = random.Random(args.seed * 1000003 + i)
            src = fuzz.generar_fuente(rng, args.instr)
            b, _, _ = assembler.ensamblar(src)
            if not probar(f"fuzz_{args.seed}_{i}", src, b, vvp, args.max, dir_fallos):
                fallos += 1

    if fallos:
        print(f"\nDIFERENCIAL: {fallos} FALLOS")
        return 1
    print("\nDIFERENCIAL: TODO OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
