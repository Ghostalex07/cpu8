#!/usr/bin/env python3
"""Harness de regresion de cpu8 (Fase 10).

Comprueba que la CPU y las herramientas no cambian de comportamiento:

1. **Bytes**: al ensamblar cada ``programs/*.asm`` se obtienen exactamente los
   mismos bytes que la referencia dorada (``tools/golden/hex.sha256``).  Detecta
   cualquier regresion en el codificador o en el analisis de etiquetas.
2. **Traza**: la ejecucion de cada programa produce la misma traza (estado de
   registros/flags despues de cada instruccion) que la dorada
   (``tools/golden/traces/<nombre>.trace``).  Detecta cambios en el RTL aunque la
   salida final no cambie.
3. **Fuzz**: programas aleatorios validos se ensamblan, se desensamblan y se
   vuelven a ensamblar; los bytes deben coincidir (ida y vuelta del
   ensamblador/desensamblador).

Uso::

    python3 tools/regress.py             # comprueba contra la referencia dorada
    python3 tools/regress.py --update    # (re)genera la referencia dorada
    python3 tools/regress.py --fuzz 500  # n.o de programas aleatorios (0 = ninguno)

El harness devuelve codigo de salida 0 si todo pasa y 1 si hay fallos, de modo
que se puede usar en CI (``make regress``).
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
# irq.asm necesita la senal irq (la cubre `make irqtest`); con irq=0 su traza no
# aporta, asi que se excluye de la comprobacion de traza (no de la de bytes).
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
    # El runtime de iverilog imprime diagnosticos dependientes del entorno en
    # stdout y NO deben formar parte de la traza dorada:
    #   - 11.0: el aviso de $readmemh ("Not enough words ...") con la RUTA
    #     ABSOLUTA del testbench.
    #   - 12.0: "<ruta>:<linea>: $finish called at <tiempo> (1ps)".
    # Ambos llevan rutas/tiempos que cambian entre maquinas y versiones.
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
    print(f"Referencia dorada actualizada en {GOLDEN.relative_to(RAIZ)}/")
    return 0


def _comprobar_bytes() -> int:
    man = GOLDEN / "hex.sha256"
    if not man.exists():
        print(f"FALTA {man.relative_to(RAIZ)} (ejecuta `make regress-update`)")
        return 1
    esperado = dict(ln.split() for ln in man.read_text().splitlines() if ln.strip())
    actual = _hex_actuales()
    fallos = 0
    for n in sorted(set(esperado) | set(actual)):
        if esperado.get(n) != actual.get(n):
            print(f"  FALLO bytes {n}: {esperado.get(n)} != {actual.get(n)}")
            fallos += 1
    print(f"  bytes: {len(actual)} programas, {fallos} fallos")
    return fallos


def _primera_diferencia(esperado: str, actual: str) -> str:
    """Descripcion de la primera linea que difiere, con repr (ve espacios)."""
    ea, aa = esperado.splitlines(), actual.splitlines()
    for i in range(max(len(ea), len(aa))):
        le = ea[i] if i < len(ea) else "<falta>"
        la = aa[i] if i < len(aa) else "<falta>"
        if le != la:
            return (f"    linea {i + 1}:\n"
                    f"      esperado: {le!r}\n"
                    f"      actual  : {la!r}")
    return "    (sin diferencias linea a linea)"


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
            print(f"  FALTA traza dorada {g.relative_to(RAIZ)}")
            fallos += 1
            continue
        n += 1
        esperado = g.read_text()
        actual = _traza(vvp, p.stem)
        if actual != esperado:
            print(f"  FALLO traza {p.stem} "
                  f"(`make trace PROG=programs/{p.stem}` para inspeccionar)")
            print(_primera_diferencia(esperado, actual))
            dump.mkdir(parents=True, exist_ok=True)
            (dump / f"{p.stem}.expected.trace").write_text(esperado)
            (dump / f"{p.stem}.actual.trace").write_text(actual)
            fallos += 1
    if fallos:
        print(f"  trazas volcadas en {dump.relative_to(RAIZ)}/ (expected/actual)")
    print(f"  trazas: {n} programas, {fallos} fallos")
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
        except Exception as e:  # noqa: BLE001 (queremos ver cualquier fallo)
            print(f"  FALLO fuzz #{i}: {e}\n{src}")
            fallos += 1
            continue
        if b1 != b2:
            print(f"  FALLO fuzz #{i}: los bytes no coinciden\n{src}")
            fallos += 1
    print(f"  fuzz ida/vuelta: {cuenta} programas, {fallos} fallos")
    return fallos


def main(argv: list[str]) -> int:
    args = argv[1:]
    if "--update" in args:
        return actualizar()
    fuzz_n = 200
    if "--fuzz" in args:
        fuzz_n = int(args[args.index("--fuzz") + 1])
    print("=== regresion de cpu8 ===")
    fallos = _comprobar_bytes() + _comprobar_trazas()
    if fuzz_n:
        fallos += _comprobar_fuzz(fuzz_n)
    if fallos:
        print(f"REGRESION: {fallos} fallos")
        return 1
    print("REGRESION: TODO OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
