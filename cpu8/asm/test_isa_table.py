"""Tests de la tabla de la ISA (``asm/isa_table.py``).

Comprueban que la tabla —fuente única de verdad machine-readable de la ISA— no
**deriva** de las implementaciones reales:

* **Codificación**: para cada entrada se ensambla su instrucción representativa
  (``muestra``) con ``asm/assembler.py`` y se compara con los bytes que declara
  la tabla (``bytes_codificados()``). Falla si el ensamblador o la tabla cambian.
* **Decodificación / ida y vuelta**: se desensamblan esos bytes con
  ``tools/disasm.py`` y se comprueba el texto esperado (mnemónico y operandos).
* **Cobertura**: el conjunto de mnemónicos de la tabla debe ser EXACTAMENTE
  ``assembler.MNEMONICOS``, y debe haber al menos una instrucción por página de
  opcode (0x0..0xF).
* **Documentación**: ``docs/OPCODES.md`` debe coincidir con lo que genera
  ``tools/gen_docs.py`` (y ``--check`` debe salir con 0).

Se ejecutan con ``pytest`` desde la raíz del proyecto o desde ``asm/``::

    python3 -m pytest asm/test_isa_table.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Permite ``import assembler`` (asm/) e ``import disasm``/``gen_docs`` (tools/).
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
    """Ensambla y devuelve la lista de bytes (lanza AssemblerError si falla)."""
    salida, _etiquetas, _listado = assembler.ensamblar(src)
    return salida


def _id(instr: isa_table.Instruccion) -> str:
    forma = instr.forma.replace(", ", "_").replace("[", "").replace("]", "")
    forma = forma.replace(" ", "").replace("+", "p") or "sin_operandos"
    return f"{instr.mnemonico}-{forma}"


# ---------------------------------------------------------------------------
#  La tabla no está vacía y cubre todas las páginas de opcode
# ---------------------------------------------------------------------------

def test_hay_instrucciones() -> None:
    assert len(INSTRUCCIONES) > 0


def test_cubre_todas_las_paginas_de_opcode() -> None:
    paginas = {instr.pagina for instr in INSTRUCCIONES}
    assert paginas == set(range(0x10)), (
        f"páginas cubiertas: {sorted(paginas)}; faltan "
        f"{sorted(set(range(0x10)) - paginas)}")


def test_mnemonicos_iguales_al_ensamblador() -> None:
    # Si se añade/renombra un mnemónico en assembler.py y no en la tabla (o al
    # revés), este test lo detecta.
    assert isa_table.MNEMONICOS == assembler.MNEMONICOS


# ---------------------------------------------------------------------------
#  Codificación: tabla vs. ensamblador real
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("instr", INSTRUCCIONES, ids=_id)
def test_la_codificacion_de_la_tabla_coincide_con_el_ensamblador(
        instr: isa_table.Instruccion) -> None:
    esperado = list(instr.bytes_codificados())
    assert len(esperado) == instr.longitud, (
        f"{instr.mnemonico}: la tabla declara {instr.longitud} byte(s) pero "
        f"codifica {len(esperado)}")
    obtenido = asm(instr.muestra)
    assert obtenido == esperado, (
        f"{instr.mnemonico} ({instr.forma}): '{instr.muestra}' -> {obtenido}; "
        f"la tabla dice {esperado}")


# ---------------------------------------------------------------------------
#  Decodificación / ida y vuelta: tabla vs. desensamblador real
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("instr", INSTRUCCIONES, ids=_id)
def test_el_desensamblado_coincide_con_la_tabla(
        instr: isa_table.Instruccion) -> None:
    bytes_ = list(instr.bytes_codificados())
    texto, longitud = disasm.decodificar(bytes_, 0)
    assert texto == instr.desensamblado, (
        f"{instr.mnemonico}: desensamblar {bytes_} da '{texto}'; la tabla dice "
        f"'{instr.desensamblado}'")
    assert longitud == instr.longitud


@pytest.mark.parametrize("instr", INSTRUCCIONES, ids=_id)
def test_ida_y_vuelta_por_texto(instr: isa_table.Instruccion) -> None:
    # Reensamblar el texto desensamblado debe dar los mismos bytes. Se omite en
    # los saltos/llamadas, cuyo texto referencia etiquetas (L_xxxx) que aquí no
    # se definen; esos ya quedan cubiertos por ``test_el_desensamblado...``.
    if "L_" in instr.desensamblado:
        return
    assert asm(instr.desensamblado) == list(instr.bytes_codificados())


@pytest.mark.parametrize("instr", INSTRUCCIONES, ids=_id)
def test_ida_y_vuelta_con_desensamblar_crudo(
        instr: isa_table.Instruccion) -> None:
    # asm -> bytes -> desensamblar_crudo -> asm: mismos bytes (para las formas
    # sin etiquetas). Cubre el recorrido completo por tools/disasm.py.
    if "L_" in instr.desensamblado:
        return
    bytes_ = list(instr.bytes_codificados())
    fuente = "\n".join(disasm.desensamblar_crudo(bytes_, etiquetas=False)) + "\n"
    assert asm(fuente) == bytes_


# ---------------------------------------------------------------------------
#  Documentación generada (docs/OPCODES.md)
# ---------------------------------------------------------------------------

def test_docs_opcodes_esta_actualizado() -> None:
    assert gen_docs.RUTA_DOCS.exists(), (
        "falta docs/OPCODES.md; ejecuta 'python3 tools/gen_docs.py'")
    actual = gen_docs.RUTA_DOCS.read_text(encoding="utf-8")
    assert actual == gen_docs.generar_markdown(), (
        "docs/OPCODES.md está desactualizado respecto a asm/isa_table.py; "
        "regéneralo con 'python3 tools/gen_docs.py'")


def test_gen_docs_check_devuelve_cero() -> None:
    assert gen_docs.main(["--check"]) == 0
