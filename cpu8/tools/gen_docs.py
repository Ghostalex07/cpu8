#!/usr/bin/env python3
"""Genera ``docs/OPCODES.md`` a partir de ``asm/isa_table.py``.

``asm/isa_table.py`` es la fuente única de verdad machine-readable de la ISA;
este script la convierte en una tabla Markdown en español (agrupada por página
de opcode).

Uso (desde ``cpu8/`` o desde la raíz del repo)::

    python3 tools/gen_docs.py            # (re)genera docs/OPCODES.md
    python3 tools/gen_docs.py --check    # no escribe; sale con 1 si está obsoleto

``--check`` está pensado para CI: falla si ``docs/OPCODES.md`` no coincide con
lo que produciría la tabla (es decir, si alguien tocó la ISA y no regeneró la
documentación, o al revés).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

# Raíz del proyecto (cpu8/): este fichero vive en cpu8/tools/gen_docs.py.
RAIZ: Final[Path] = Path(__file__).resolve().parent.parent
if str(RAIZ / "asm") not in sys.path:
    sys.path.insert(0, str(RAIZ / "asm"))

import isa_table  # noqa: E402

RUTA_DOCS: Final[Path] = RAIZ / "docs" / "OPCODES.md"


def _escapar_celda(texto: str) -> str:
    """Escapa el carácter de separación de columnas de las tablas Markdown."""
    return texto.replace("|", "\\|")


def _celda_codificacion(instr: isa_table.Instruccion) -> str:
    """Hex de los bytes representativos + la regla declarada en la tabla."""
    hexs = " ".join(f"0x{b:02X}" for b in instr.bytes_codificados())
    return f"`{hexs}` — `{instr.regla}`"


def generar_markdown() -> str:
    """Devuelve el contenido completo de ``docs/OPCODES.md``."""
    lineas: list[str] = []
    lineas.append("# Opcodes de la ISA (cpu8)")
    lineas.append("")
    lineas.append(
        "> **Fichero generado automáticamente** por `tools/gen_docs.py` a partir "
        "de `asm/isa_table.py`,")
    lineas.append(
        "> la fuente única de verdad machine-readable de la ISA. **No lo edites "
        "a mano**:")
    lineas.append(
        "> regenéralo con `python3 tools/gen_docs.py` y compruébalo con "
        "`python3 tools/gen_docs.py --check`.")
    lineas.append("")
    lineas.append(
        "La codificación del primer byte es `(opcode<<4) + (rd<<2) + rs` "
        "(ver `docs/ISA.md` §2).")
    lineas.append(
        "En *Codificación* se muestran los bytes de una instrucción "
        "representativa de cada forma y, a continuación, la regla.")
    lineas.append(
        "Las banderas que aparecen en la columna *Banderas* son las que la "
        "instrucción **modifica**")
    lineas.append(
        "(`—` = no altera ninguna); ver `docs/ISA.md` §5 para el convenio de "
        "C, Z, N, V (y `I`).")
    lineas.append("")

    grupos = isa_table.por_pagina()
    for pagina in sorted(grupos):
        instrs = grupos[pagina]
        if not instrs:
            continue
        titulo = isa_table.PAGINAS.get(pagina, "Página")
        lineas.append(f"## Página `0x{pagina:X}` — {titulo}")
        lineas.append("")
        lineas.append(
            "| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |")
        lineas.append(
            "|-----------|--------------------|-------|-----------|----------|-------------|")
        for instr in instrs:
            mnem = f"`{instr.mnemonico}`"
            if instr.alias_de is not None:
                mnem += f" (alias de `{instr.alias_de}`)"
            operandos = instr.forma if instr.forma else "—"
            lineas.append(
                f"| {mnem} | {_celda_codificacion(instr)} | {instr.longitud} | "
                f"{_escapar_celda(operandos)} | {instr.banderas} | "
                f"{_escapar_celda(instr.descripcion)} |")
        lineas.append("")

    return "\n".join(lineas)


def comprobar() -> int:
    """Devuelve 0 si ``docs/OPCODES.md`` está al día; 1 si no (o no existe)."""
    generado = generar_markdown()
    if not RUTA_DOCS.exists():
        print(f"Error: falta {RUTA_DOCS}; ejecuta 'python3 tools/gen_docs.py'.",
              file=sys.stderr)
        return 1
    actual = RUTA_DOCS.read_text(encoding="utf-8")
    if actual != generado:
        print(
            "Error: docs/OPCODES.md está desactualizado respecto a "
            "asm/isa_table.py.\n"
            "Ejecuta 'python3 tools/gen_docs.py' para regenerarlo.",
            file=sys.stderr)
        return 1
    print("docs/OPCODES.md está al día.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Genera docs/OPCODES.md a partir de asm/isa_table.py")
    ap.add_argument(
        "--check", action="store_true",
        help="no escribe; sale con código 1 si docs/OPCODES.md está obsoleto")
    args = ap.parse_args(argv)

    if args.check:
        return comprobar()

    RUTA_DOCS.parent.mkdir(parents=True, exist_ok=True)
    RUTA_DOCS.write_text(generar_markdown(), encoding="utf-8")
    print(f"Escrito {RUTA_DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
