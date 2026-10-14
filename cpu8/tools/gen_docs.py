#!/usr/bin/env python3
"""Generates ``docs/OPCODES.md`` from ``asm/isa_table.py``.

``asm/isa_table.py`` is the single machine-readable source of truth for the
ISA; this script turns it into a Markdown table (grouped by opcode page).

Usage (from ``cpu8/`` or from the repo root)::

    python3 tools/gen_docs.py            # (re)generates docs/OPCODES.md
    python3 tools/gen_docs.py --check    # does not write; exits with 1 if out of date

``--check`` is meant for CI: it fails if ``docs/OPCODES.md`` does not match
what the table would produce (that is, if someone touched the ISA and did not
regenerate the documentation, or the other way around).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

# Project root (cpu8/): this file lives in cpu8/tools/gen_docs.py.
RAIZ: Final[Path] = Path(__file__).resolve().parent.parent
if str(RAIZ / "asm") not in sys.path:
    sys.path.insert(0, str(RAIZ / "asm"))

import isa_table  # noqa: E402

RUTA_DOCS: Final[Path] = RAIZ / "docs" / "OPCODES.md"


def _escapar_celda(texto: str) -> str:
    """Escapes the Markdown table column separator character."""
    return texto.replace("|", "\\|")


def _celda_codificacion(instr: isa_table.Instruccion) -> str:
    """Hex of the representative bytes + the rule declared in the table."""
    hexs = " ".join(f"0x{b:02X}" for b in instr.bytes_codificados())
    return f"`{hexs}` — `{instr.regla}`"


def generar_markdown() -> str:
    """Returns the full content of ``docs/OPCODES.md``."""
    lineas: list[str] = []
    lineas.append("# ISA Opcodes (cpu8)")
    lineas.append("")
    lineas.append(
        "> **Automatically generated file** by `tools/gen_docs.py` from "
        "`asm/isa_table.py`,")
    lineas.append(
        "> the single machine-readable source of truth for the ISA. **Do not "
        "edit it by hand**:")
    lineas.append(
        "> regenerate it with `python3 tools/gen_docs.py` and check it with "
        "`python3 tools/gen_docs.py --check`.")
    lineas.append("")
    lineas.append(
        "The encoding of the first byte is `(opcode<<4) + (rd<<2) + rs` "
        "(see `docs/ISA.md` §2).")
    lineas.append(
        "Under *Encoding* the bytes of a representative instruction of each "
        "form are shown and, next, the rule.")
    lineas.append(
        "The flags appearing in the *Flags* column are those that the "
        "instruction **modifies**")
    lineas.append(
        "(`—` = does not change any); see `docs/ISA.md` §5 for the convention "
        "of C, Z, N, V (and `I`).")
    lineas.append("")

    grupos = isa_table.por_pagina()
    for pagina in sorted(grupos):
        instrs = grupos[pagina]
        if not instrs:
            continue
        titulo = isa_table.PAGINAS.get(pagina, "Page")
        lineas.append(f"## Page `0x{pagina:X}` — {titulo}")
        lineas.append("")
        lineas.append(
            "| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |")
        lineas.append(
            "|----------|----------------|-------|----------|-------|-------------|")
        for instr in instrs:
            mnem = f"`{instr.mnemonico}`"
            if instr.alias_de is not None:
                mnem += f" (alias of `{instr.alias_de}`)"
            operandos = instr.forma if instr.forma else "—"
            lineas.append(
                f"| {mnem} | {_celda_codificacion(instr)} | {instr.longitud} | "
                f"{_escapar_celda(operandos)} | {instr.banderas} | "
                f"{_escapar_celda(instr.descripcion)} |")
        lineas.append("")

    return "\n".join(lineas)


def comprobar() -> int:
    """Returns 0 if ``docs/OPCODES.md`` is up to date; 1 if not (or missing)."""
    generado = generar_markdown()
    if not RUTA_DOCS.exists():
        print(f"Error: missing {RUTA_DOCS}; run 'python3 tools/gen_docs.py'.",
              file=sys.stderr)
        return 1
    actual = RUTA_DOCS.read_text(encoding="utf-8")
    if actual != generado:
        print(
            "Error: docs/OPCODES.md is out of date with respect to "
            "asm/isa_table.py.\n"
            "Run 'python3 tools/gen_docs.py' to regenerate it.",
            file=sys.stderr)
        return 1
    print("docs/OPCODES.md is up to date.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generates docs/OPCODES.md from asm/isa_table.py")
    ap.add_argument(
        "--check", action="store_true",
        help="does not write; exits with code 1 if docs/OPCODES.md is out of date")
    args = ap.parse_args(argv)

    if args.check:
        return comprobar()

    RUTA_DOCS.parent.mkdir(parents=True, exist_ok=True)
    RUTA_DOCS.write_text(generar_markdown(), encoding="utf-8")
    print(f"Wrote {RUTA_DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
