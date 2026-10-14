#!/usr/bin/env python3
"""Tests del modelo de referencia ``tools/iss.py``.

Dos niveles:

1. **Micro-tests dirigidos** de la semantica exacta (flags de la ALU, V en
   INC/DEC, C en MUL/DIV, pila, indexado, familias de Jcc, puertos).
2. **Contraste con los dorados**: para cada ``programs/*.asm`` (menos ``irq``,
   que necesita la senal irq) se ejecuta el ISS y se compara la secuencia de OUT
   con su ``programs/*.ref``.  Como esos ``.ref`` estan verificados contra el RTL
   (``make test``), que el ISS los reproduzca demuestra que el modelo es fiel.

Se ejecuta con ``make pytools`` o ``python3 -m pytest tools/test_iss.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(RAIZ / "asm"))

import assembler  # noqa: E402
import iss  # noqa: E402

PROG_DIR = RAIZ / "programs"


def ensambla_hexa(texto: str) -> list[int]:
    return assembler.ensamblar(texto)[0]


def ejecutar(texto: str, max_steps: int = 5000) -> iss.ISS:
    m = iss.ISS(ensambla_hexa(texto))
    m.run(max_steps)
    return m


# ---------------------------------------------------------------------------
#  ALU: flags
# ---------------------------------------------------------------------------

def test_alu_suma_acarreo_y_v() -> None:
    y, c, v, z, n = iss.alu(iss.ADD, 0, 0xFF, 0x01)
    assert (y, c, v, z, n) == (0x00, 1, 0, 1, 0)      # 0xFF+1 -> C=1, Z=1
    y, c, v, z, n = iss.alu(iss.ADD, 0, 0x7F, 0x01)
    assert (y, c, v, z, n) == (0x80, 0, 1, 0, 1)      # desbordamiento con signo


def test_alu_resta_c_es_no_borrow() -> None:
    assert iss.alu(iss.SUB, 0, 0x05, 0x03)[1] == 1    # 5-3: sin borrow -> C=1
    assert iss.alu(iss.SUB, 0, 0x03, 0x05)[1] == 0    # 3-5: borrow -> C=0
    assert iss.alu(iss.SUB, 0, 0x80, 0x01)[2] == 1    # -128-1 -> V=1


def test_alu_logica_pone_c_y_v_a_cero() -> None:
    for op in (iss.AND, iss.OR, iss.XOR):
        _, c, v, _, _ = iss.alu(op, 0, 0xF0, 0x0F)
        assert (c, v) == (0, 0)


def test_alu_shift() -> None:
    assert iss.alu(iss.SHIFT, 0, 0x81, 0) == (0x02, 1, 0, 0, 0)  # SHL: sale bit7
    assert iss.alu(iss.SHIFT, 1, 0x81, 0) == (0x40, 1, 0, 0, 0)  # SHR: sale bit0


def test_alu_mul_div() -> None:
    assert iss.alu(iss.MUL, 0, 7, 6)[:2] == (42, 0)      # 7*6 = 42, sin desbordar
    assert iss.alu(iss.MUL, 0, 0x14, 0x14)[:2] == (0x90, 1)   # 20*20=400 -> C=1
    assert iss.alu(iss.DIV, 0, 200, 7)[:2] == (28, 0)    # 200/7 = 28
    assert iss.alu(iss.DIV, 0, 5, 0)[:2] == (0, 1)       # /0 -> 0 y error C=1


# ---------------------------------------------------------------------------
#  Semantica a nivel de instruccion
# ---------------------------------------------------------------------------

def test_inc_no_toca_c_pero_si_v() -> None:
    m = ejecutar("""
        LDI A, 0x05        ; A = 5
        ST  A, [0xF0]      ; guarda 5 en una celda libre
        CMP A, A           ; C=1 (5-5, sin borrow) y Z=1
        LDI B, 0x00
        CMP B, B           ; C=1
        LDI A, 0x00
        CMP A, A           ; C=1
        LDI A, 0x7F
        CMP A, A           ; C=1
        LDI A, 0x7F
        INC A              ; A=0x80 -> Z=0,N=1,V=1 ; C se queda como estaba (=1)
        HLT
    """)
    assert m.regs[0] == 0x80
    assert (m.fz, m.fn, m.fv) == (0, 1, 1)
    assert m.fc == 1      # INC no toca C (sigue el 1 del ultimo CMP)


def test_add_si_toca_c() -> None:
    m = ejecutar("LDI A, 0xFF\nLDI B, 0x01\nADD A, B\nHLT")
    assert m.regs[0] == 0x00 and m.fc == 1 and m.fz == 1


def test_mul_div_flags_y_registro() -> None:
    m = ejecutar("LDI A, 20\nLDI B, 20\nMUL A, B\nHLT")
    assert m.regs[0] == 0x90 and m.fc == 1
    m = ejecutar("LDI A, 200\nLDI B, 7\nDIV A, B\nHLT")
    assert m.regs[0] == 28 and m.fc == 0
    m = ejecutar("LDI A, 5\nLDI B, 0\nDIV A, B\nHLT")
    assert m.regs[0] == 0 and m.fc == 1


def test_pila_push_pop() -> None:
    m = ejecutar("LDI A, 0x11\nLDI B, 0x22\nPUSH A\nPUSH B\nPOP C\nPOP D\nHLT")
    assert (m.regs[2], m.regs[3]) == (0x22, 0x11)


def test_call_ret() -> None:
    m = ejecutar("""
        LDI A, 0x00
        CALL sub
        OUT A
        HLT
    sub:
        LDI A, 0x42
        RET
    """)
    assert m.regs[0] == 0x42
    assert [v for v, _ in m.outs] == [0x42]


def test_ld_st_indexado() -> None:
    m = ejecutar("""
        LDI A, 0xAB
        ST  A, [D+3]      ; RAM[D+3] = 0xAB
        LD  B, [D+3]      ; B = 0xAB
        LD  C, [0x20]     ; C = RAM[0x20]
        HLT
    """)
    assert m.regs[1] == 0xAB
    assert m.mem[(m.regs[3] + 3) & 0xFF] == 0xAB


def test_jcc_familias() -> None:
    # JLT con signo: -1 < 0
    m = ejecutar("LDI A, 0xFF\nLDI B, 0x00\nCMP A, B\nJLT si\nLDI C, 0x00\nHLT\nsi:\nLDI C, 0x01\nHLT")
    assert m.regs[2] == 0x01
    # JGE no salta
    m = ejecutar("LDI A, 0xFF\nLDI B, 0x00\nCMP A, B\nJGE si\nLDI C, 0x00\nHLT\nsi:\nLDI C, 0x01\nHLT")
    assert m.regs[2] == 0x00


def test_puertos_in_out() -> None:
    m = ejecutar("IN A\nOUT A\nIN 3, B\nOUT 3, B\nHLT")
    # Convenio del entorno: puerto n -> 0x10 + n.
    assert [v for v, _ in m.outs] == [0x10, 0x13]
    assert [p for _, p in m.outs] == [0, 3]


def test_branch_cond_y_needs_operand() -> None:
    assert iss.needs_operand(0x10) is True     # LDI
    assert iss.needs_operand(0xC0) is True     # JMP
    assert iss.needs_operand(0xF6) is True     # MUL
    assert iss.needs_operand(0xE0) is False    # OUT rd
    assert iss.needs_operand(0xF0) is False    # HLT


def _prog_irq() -> list[int]:
    """LDI A,0 ; EI ; [0x03] JMP 0x03 (bucle) ; [0x08] LDI A,0x42 ; RET."""
    return [0x10, 0x00, 0xF2, 0xC0, 0x03, 0x00, 0x00, 0x00,
            0x10, 0x42, 0xF1]


def test_irq_se_atiende_en_el_vector() -> None:
    m = iss.ISS(_prog_irq(), irq_at=3)
    m.run(20)
    assert 0x08 in [r[0] for r in m.rows]   # se ejecuto el manejador (vector 0x08)
    assert m.regs[0] == 0x42                 # ...que puso A=0x42


def test_irq_no_se_atiende_sin_ei() -> None:
    # Sin EI el flag I es 0: aunque irq este pedida desde el principio, no se atiende.
    prog = [0x10, 0x00, 0xC0, 0x02]          # LDI A,0 ; JMP 0x02 (bucle)
    m = iss.ISS(prog, irq_at=0)
    m.run(10)
    assert 0x08 not in [r[0] for r in m.rows]
    assert m.regs[0] == 0x00


# ---------------------------------------------------------------------------
#  Contraste con los dorados (programs/*.asm vs programs/*.ref)
# ---------------------------------------------------------------------------

PROGRAMAS = sorted(p for p in PROG_DIR.glob("*.asm") if p.stem != "irq")


@pytest.mark.parametrize("asm_path", PROGRAMAS, ids=lambda p: p.stem)
def test_iss_reproduce_los_ref(asm_path: Path) -> None:
    ref_path = asm_path.with_suffix(".ref")
    esperado = [int(t, 16) for t in ref_path.read_text().split()]
    m = ejecutar(asm_path.read_text())
    obtenido = [v for v, _ in m.outs]
    assert obtenido == esperado
