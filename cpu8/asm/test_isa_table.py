"""Tests for the ISA table (``asm/isa_table.py``).

They check that the table —the single machine-readable source of truth for the
ISA— does not **drift** from the real implementations:

* **Encoding**: for each entry its representative instruction (``muestra``) is
  assembled with ``asm/assembler.py`` and compared with the bytes declared by
  the table (``bytes_codificados()``). It fails if the assembler or the table
  change.
* **Decoding / round trip**: those bytes are disassembled with
  ``tools/disasm.py`` and the expected text is checked (mnemonic and operands).
* **Coverage**: the set of mnemonics of the table must be EXACTLY
  ``assembler.MNEMONICOS``, and there must be at least one instruction per
  opcode page (0x0..0xF).
* **Documentation**: ``docs/OPCODES.md`` must match what ``tools/gen_docs.py``
  generates (and ``--check`` must exit with 0).

They are run with ``pytest`` from the project root or from ``asm/``::

    python3 -m pytest asm/test_isa_table.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allows ``import assembler`` (asm/) and ``import disasm``/``gen_docs`` (tools/).
_ASM_DIR = Path(__file__).resolve().parent
_RAIZ = _ASM_DIR.parent
for _d in (str(_ASM_DIR), str(_RAIZ / "tools")):
    if _d not in sys.path:
        sys.path.insert(0, _d)

import assembler  # noqa: E402
import disasm  # noqa: E402
import gen_docs  # noqa: E402
import isa_table  # noqa: E402

INSTRUCCIONES = isa_table.INSTRUCCIONES


def asm(src: str) -> list[int]:
    """Assembles and returns the list of bytes (raises AssemblerError on failure)."""
    salida, _etiquetas, _listado = assembler.ensamblar(src)
    return salida


def _id(instr: isa_table.Instruccion) -> str:
    forma = instr.forma.replace(", ", "_").replace("[", "").replace("]", "")
    forma = forma.replace(" ", "").replace("+", "p") or "no_operands"
    return f"{instr.mnemonico}-{forma}"


# ---------------------------------------------------------------------------
#  The table is not empty and covers all opcode pages
# ---------------------------------------------------------------------------

def test_hay_instrucciones() -> None:
    assert len(INSTRUCCIONES) > 0


def test_cubre_todas_las_paginas_de_opcode() -> None:
    paginas = {instr.pagina for instr in INSTRUCCIONES}
    assert paginas == set(range(0x10)), (
        f"pages covered: {sorted(paginas)}; missing "
        f"{sorted(set(range(0x10)) - paginas)}")


def test_mnemonicos_iguales_al_ensamblador() -> None:
    # If a mnemonic is added/renamed in assembler.py and not in the table (or
    # the other way around), this test detects it.
    assert isa_table.MNEMONICOS == assembler.MNEMONICOS


# ---------------------------------------------------------------------------
#  Encoding: table vs. real assembler
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("instr", INSTRUCCIONES, ids=_id)
def test_la_codificacion_de_la_tabla_coincide_con_el_ensamblador(
        instr: isa_table.Instruccion) -> None:
    esperado = list(instr.bytes_codificados())
    assert len(esperado) == instr.longitud, (
        f"{instr.mnemonico}: the table declares {instr.longitud} byte(s) but "
        f"encodes {len(esperado)}")
    obtenido = asm(instr.muestra)
    assert obtenido == esperado, (
        f"{instr.mnemonico} ({instr.forma}): '{instr.muestra}' -> {obtenido}; "
        f"the table says {esperado}")


# ---------------------------------------------------------------------------
#  Decoding / round trip: table vs. real disassembler
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("instr", INSTRUCCIONES, ids=_id)
def test_el_desensamblado_coincide_con_la_tabla(
        instr: isa_table.Instruccion) -> None:
    bytes_ = list(instr.bytes_codificados())
    texto, longitud = disasm.decodificar(bytes_, 0)
    assert texto == instr.desensamblado, (
        f"{instr.mnemonico}: disassembling {bytes_} gives '{texto}'; the table "
        f"says '{instr.desensamblado}'")
    assert longitud == instr.longitud


@pytest.mark.parametrize("instr", INSTRUCCIONES, ids=_id)
def test_ida_y_vuelta_por_texto(instr: isa_table.Instruccion) -> None:
    # Reassembling the disassembled text must give the same bytes. It is skipped
    # for jumps/calls, whose text references labels (L_xxxx) that are not
    # defined here; those are already covered by ``test_el_desensamblado...``.
    if "L_" in instr.desensamblado:
        return
    assert asm(instr.desensamblado) == list(instr.bytes_codificados())


@pytest.mark.parametrize("instr", INSTRUCCIONES, ids=_id)
def test_ida_y_vuelta_con_desensamblar_crudo(
        instr: isa_table.Instruccion) -> None:
    # asm -> bytes -> desensamblar_crudo -> asm: same bytes (for the forms
    # without labels). Covers the full path through tools/disasm.py.
    if "L_" in instr.desensamblado:
        return
    bytes_ = list(instr.bytes_codificados())
    fuente = "\n".join(disasm.desensamblar_crudo(bytes_, etiquetas=False)) + "\n"
    assert asm(fuente) == bytes_


# ---------------------------------------------------------------------------
#  Generated documentation (docs/OPCODES.md)
# ---------------------------------------------------------------------------

def test_docs_opcodes_esta_actualizado() -> None:
    assert gen_docs.RUTA_DOCS.exists(), (
        "missing docs/OPCODES.md; run 'python3 tools/gen_docs.py'")
    actual = gen_docs.RUTA_DOCS.read_text(encoding="utf-8")
    assert actual == gen_docs.generar_markdown(), (
        "docs/OPCODES.md is out of date with respect to asm/isa_table.py; "
        "regenerate it with 'python3 tools/gen_docs.py'")


def test_gen_docs_check_devuelve_cero() -> None:
    assert gen_docs.main(["--check"]) == 0
