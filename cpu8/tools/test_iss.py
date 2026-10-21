#!/usr/bin/env python3
"""Tests for the reference model ``tools/iss.py``.

Two levels:

1. **Directed micro-tests** of the exact semantics (ALU flags, V in INC/DEC, C
   in MUL/DIV, stack, indexing, Jcc families, ports).
2. **Contrast with the golden values**: for each ``programs/*.asm`` (except
   ``irq``, which needs the irq signal) the ISS is run and its OUT sequence is
   compared with its ``programs/*.ref``.  Since those ``.ref`` are verified
   against the RTL (``make test``), the fact that the ISS reproduces them proves
   that the model is faithful.
3. **Interrupt-enable flag I**: ``EI``/``DI``, the flags byte handled by
   ``PUSHF``/``POPF``, ``RETI`` restoring only ``C,Z,N,V``, and the gating of a
   level-high IRQ by ``I``.

Run with ``make pytools`` or ``python3 -m pytest tools/test_iss.py``.
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
    assert (y, c, v, z, n) == (0x00, 1, 0, 1, 0)  # 0xFF+1 -> C=1, Z=1
    y, c, v, z, n = iss.alu(iss.ADD, 0, 0x7F, 0x01)
    assert (y, c, v, z, n) == (0x80, 0, 1, 0, 1)  # signed overflow


def test_alu_resta_c_es_no_borrow() -> None:
    assert iss.alu(iss.SUB, 0, 0x05, 0x03)[1] == 1  # 5-3: no borrow -> C=1
    assert iss.alu(iss.SUB, 0, 0x03, 0x05)[1] == 0  # 3-5: borrow -> C=0
    assert iss.alu(iss.SUB, 0, 0x80, 0x01)[2] == 1  # -128-1 -> V=1


def test_alu_logica_pone_c_y_v_a_cero() -> None:
    for op in (iss.AND, iss.OR, iss.XOR):
        _, c, v, _, _ = iss.alu(op, 0, 0xF0, 0x0F)
        assert (c, v) == (0, 0)


def test_alu_shift() -> None:
    assert iss.alu(iss.SHIFT, 0, 0x81, 0) == (0x02, 1, 0, 0, 0)  # SHL: bit7 out
    assert iss.alu(iss.SHIFT, 1, 0x81, 0) == (0x40, 1, 0, 0, 0)  # SHR: bit0 out


def test_alu_mul_div() -> None:
    assert iss.alu(iss.MUL, 0, 7, 6)[:2] == (42, 0)  # 7*6 = 42, no overflow
    assert iss.alu(iss.MUL, 0, 0x14, 0x14)[:2] == (0x90, 1)  # 20*20=400 -> C=1
    assert iss.alu(iss.DIV, 0, 200, 7)[:2] == (28, 0)  # 200/7 = 28
    assert iss.alu(iss.DIV, 0, 5, 0)[:2] == (0, 1)  # /0 -> 0 and error C=1


# ---------------------------------------------------------------------------
#  Instruction-level semantics
# ---------------------------------------------------------------------------


def test_inc_no_toca_c_pero_si_v() -> None:
    m = ejecutar("""
        LDI A, 0x05        ; A = 5
        ST  A, [0xF0]      ; save 5 in a free cell
        CMP A, A           ; C=1 (5-5, no borrow) and Z=1
        LDI B, 0x00
        CMP B, B           ; C=1
        LDI A, 0x00
        CMP A, A           ; C=1
        LDI A, 0x7F
        CMP A, A           ; C=1
        LDI A, 0x7F
        INC A              ; A=0x80 -> Z=0,N=1,V=1 ; C stays as it was (=1)
        HLT
    """)
    assert m.regs[0] == 0x80
    assert (m.fz, m.fn, m.fv) == (0, 1, 1)
    assert m.fc == 1  # INC does not touch C (still the 1 from the last CMP)


def test_add_si_toca_c() -> None:
    m = ejecutar("LDI A, 0xFF\nLDI B, 0x01\nADD A, B\nHLT")
    assert m.regs[0] == 0x00 and m.fc == 1 and m.fz == 1


def test_sbc_resta_el_carry_y_marca_el_borrow() -> None:
    # C is the no-borrow flag: SBC subtracts 1 when C=1 (no borrow) and 0 when
    # C=0 (borrow), as documented in docs/ISA.md sections 5 and 10.10.
    m = ejecutar("LDI A, 5\nLDI B, 3\nCMP A, A\nSBC A, B\nHLT")  # C=1
    assert m.regs[0] == 1 and m.fc == 1

    m = ejecutar("LDI A, 5\nLDI B, 3\nTEST A, A\nSBC A, B\nHLT")  # C=0
    assert m.regs[0] == 2 and m.fc == 1

    # 3 - 5 - 0 = 0xFE with borrow: C=0, N=1.
    m = ejecutar("LDI A, 3\nLDI B, 5\nTEST A, A\nSBC A, B\nHLT")
    assert m.regs[0] == 0xFE and m.fc == 0 and m.fn == 1


def test_sbc_no_encadena_el_borrow_por_si_solo() -> None:
    # Documented limitation (docs/ISA.md section 5): SBC subtracts the
    # no-borrow flag, so chaining two SBCs does not propagate the borrow.
    # This locks the current RTL/ISS behaviour; SUBW is the 16-bit form that
    # does propagate it.
    m = ejecutar("""
        LDI A, 0x00
        LDI B, 0x01
        LDI C, 0x01
        LDI D, 0x00
        TEST A, A
        SBC A, C
        SBC B, D
        HLT
    """)  # 0x0100 - 0x0001 -> 0x01FF, not 0x00FF
    assert (m.regs[0], m.regs[1]) == (0xFF, 0x01)


def test_adcw_subw_encadenan_acarreo_y_borrow() -> None:
    # Pair A:B has A as the low byte and B as the high byte.  0x00FF + 1 with
    # C=1 gives 0x0100 (low byte carries into the high byte).
    m = ejecutar("""
        LDI A, 0xFF
        LDI B, 0x00
        LDI C, 0x00
        LDI D, 0x00
        CMP A, A
        ADCW A, C
        HLT
    """)
    assert (m.regs[0], m.regs[1]) == (0x00, 0x01)
    assert (m.fc, m.fz, m.fn) == (0, 0, 0)

    # 0x0100 - 0x0001 with C=0 (borrow in) gives 0x00FF: the low byte borrows
    # and SUBW propagates it by inverting C for the high byte.
    m = ejecutar("""
        LDI A, 0x00
        LDI B, 0x01
        LDI C, 0x01
        LDI D, 0x00
        TEST A, A
        SUBW A, C
        HLT
    """)
    assert (m.regs[0], m.regs[1]) == (0xFF, 0x00)
    assert (m.fc, m.fz, m.fn) == (1, 0, 0)  # the incoming borrow was consumed

    # 16-bit zero: 0x0001 - 0x0001 = 0, so Z=1 (both bytes zero).
    m = ejecutar("""
        LDI A, 0x01
        LDI B, 0x00
        LDI C, 0x01
        LDI D, 0x00
        TEST A, A
        SUBW A, C
        HLT
    """)
    assert (m.regs[0], m.regs[1]) == (0x00, 0x00)
    assert m.fz == 1


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
    # Signed JLT: -1 < 0
    m = ejecutar(
        "LDI A, 0xFF\nLDI B, 0x00\nCMP A, B\nJLT si\nLDI C, 0x00\nHLT\nsi:\nLDI C, 0x01\nHLT"
    )
    assert m.regs[2] == 0x01
    # JGE does not jump
    m = ejecutar(
        "LDI A, 0xFF\nLDI B, 0x00\nCMP A, B\nJGE si\nLDI C, 0x00\nHLT\nsi:\nLDI C, 0x01\nHLT"
    )
    assert m.regs[2] == 0x00


def test_puertos_in_out() -> None:
    m = ejecutar("IN A\nOUT A\nIN 3, B\nOUT 3, B\nHLT")
    # Environment convention: port n -> 0x10 + n.
    assert [v for v, _ in m.outs] == [0x10, 0x13]
    assert [p for _, p in m.outs] == [0, 3]


def test_branch_cond_y_needs_operand() -> None:
    assert iss.needs_operand(0x10) is True  # LDI
    assert iss.needs_operand(0xC0) is True  # JMP
    assert iss.needs_operand(0xF6) is True  # MUL
    assert iss.needs_operand(0xE0) is False  # OUT rd
    assert iss.needs_operand(0xF0) is False  # HLT


def _prog_irq() -> list[int]:
    """LDI A,0 ; EI ; [0x03] JMP 0x03 (loop) ; [0x08] LDI A,0x42 ; RET."""
    return [0x10, 0x00, 0xF2, 0xC0, 0x03, 0x00, 0x00, 0x00, 0x10, 0x42, 0xF1]


def test_irq_se_atiende_en_el_vector() -> None:
    m = iss.ISS(_prog_irq(), irq_at=3)
    m.run(20)
    assert 0x08 in [r[0] for r in m.rows]  # the handler ran (vector 0x08)
    assert m.regs[0] == 0x42  # ...which set A=0x42


def test_irq_no_se_atiende_sin_ei() -> None:
    # Without EI the I flag is 0: even if irq is requested from the start, it is
    # not serviced.
    prog = [0x10, 0x00, 0xC0, 0x02]  # LDI A,0 ; JMP 0x02 (loop)
    m = iss.ISS(prog, irq_at=0)
    m.run(10)
    assert 0x08 not in [r[0] for r in m.rows]
    assert m.regs[0] == 0x00


def test_reti_restaura_banderas_y_no_reactiva_irq() -> None:
    # CMP A,A sets C=1; the handler clobbers the flags and returns with RETI,
    # so the ADC right after the return still sees C=1 (0 -> 2).  I stays 0
    # after RETI, so the level-high irq is not taken a second time.
    programa = ensambla_hexa(
        """
        LDI A, 0
        LDI B, 1
        LDI D, 3
        CMP A, A
        EI
    loop: OUT A
        ADC A, B
        DEC D
        JNZ loop
        HLT
        NOP
        ADD C, B
        OUT C
        RETI
        """
    )
    m = iss.ISS(programa, irq_at=0, irq_vector=0x10)
    m.run(200)
    assert [v for v, _ in m.outs] == [1, 0, 2, 3]


# ---------------------------------------------------------------------------
#  Interrupt-enable flag I (EI / DI / POPF / RETI / IRQ)
#
#  Semantics (docs/ISA.md §10.6 and §10.10):
#  * I is 0 after reset.  EI sets it and DI clears it; neither changes C/Z/N/V.
#  * PUSHF packs the flags byte as {0,0,0,I,V,N,Z,C} without changing the
#    flags; POPF loads C,Z,N,V,I from bits 4..0 (bits 5..7 are ignored).
#  * An IRQ is serviced only if I=1 at the start of an instruction: the PC is
#    pushed, C/Z/N/V are saved, I is cleared and the PC jumps to the vector.
#    RETI restores C/Z/N/V but does not touch I, so after the canonical entry
#    (I=0) it stays 0 and a still-high level IRQ is not re-taken.
# ---------------------------------------------------------------------------


def test_reset_deja_i_a_cero() -> None:
    assert iss.ISS().fi == 0


def test_ei_activa_i_y_di_lo_desactiva() -> None:
    assert ejecutar("EI\nHLT").fi == 1
    assert ejecutar("EI\nDI\nHLT").fi == 0


def test_ei_di_no_modifican_banderas() -> None:
    m = ejecutar("LDI A, 0x00\nCMP A, A\nEI\nDI\nHLT")
    # CMP A,A: Z=1, C=1 (no borrow), N=0, V=0.
    assert (m.fc, m.fz, m.fn, m.fv) == (1, 1, 0, 0)
    assert m.fi == 0


def test_popf_carga_banderas_desde_los_bits_0_a_4() -> None:
    # Bit 4 is I; LDI does not touch the flags, so only POPF can set them here.
    m = ejecutar("LDI A, 0x10\nPUSH A\nPOPF\nHLT")
    assert m.fi == 1
    assert (m.fc, m.fz, m.fn, m.fv) == (0, 0, 0, 0)

    # Bits 0..3 are C,Z,N,V.
    m = ejecutar("LDI A, 0x0F\nPUSH A\nPOPF\nHLT")
    assert m.fi == 0
    assert (m.fc, m.fz, m.fn, m.fv) == (1, 1, 1, 1)


def test_popf_limpia_i_e_ignora_los_bits_altos() -> None:
    m = ejecutar("EI\nLDI A, 0x00\nPUSH A\nPOPF\nHLT")
    assert m.fi == 0

    # Bits 5..7 are not part of the flags byte: they must be ignored.
    m = ejecutar("LDI A, 0xE0\nPUSH A\nPOPF\nHLT")
    assert (m.fc, m.fz, m.fn, m.fv, m.fi) == (0, 0, 0, 0, 0)


def test_pushf_empaqueta_i_sin_modificar_banderas() -> None:
    m = ejecutar("LDI A, 0x00\nCMP A, A\nEI\nPUSHF\nPOP B\nHLT")
    assert m.regs[1] == 0x13  # {0,0,0,I=1,V=0,N=0,Z=1,C=1}
    assert (m.fc, m.fz, m.fn, m.fv, m.fi) == (1, 1, 0, 0, 1)


def test_reti_restaura_c_z_n_v_y_deja_i_a_cero() -> None:
    # The interrupted code leaves C=0,Z=0,N=1,V=1 (0x7F+1=0x80); the handler
    # clobbers them (C=1,Z=1,N=0,V=0) and RETI must bring the original ones
    # back.  The level IRQ stays high, so a re-entry would be visible too.
    programa = ensambla_hexa(
        """
        LDI A, 0x7F
        LDI B, 0x01
        ADD A, B
        EI
    loop: JMP loop
        NOP
        NOP
        LDI A, 0x00
        CMP A, A
        RETI
        """
    )
    m = iss.ISS(programa, irq_at=0, irq_vector=0x0A)  # handler at 0x0A
    m.run(20)
    assert (m.fc, m.fz, m.fn, m.fv) == (0, 0, 1, 1)
    assert m.fi == 0
    assert [r[0] for r in m.rows].count(0x0A) == 1


def test_irq_con_i_a_cero_queda_pendiente_y_se_atiende_tras_ei() -> None:
    # IRQ is high from the start, but I=0 while LDI/NOP/NOP retire.  EI sets
    # I; on the very next instruction the pending IRQ must be taken.
    programa = ensambla_hexa(
        """
        LDI A, 0x00
        NOP
        NOP
        EI
    loop: OUT A
        JMP loop
        NOP
        NOP
        LDI A, 0x42
        RETI
        """
    )
    m = iss.ISS(programa, irq_at=0, irq_vector=0x0A)  # handler at 0x0A
    m.run(10)
    pcs = [r[0] for r in m.rows]
    ei_idx = next(i for i, r in enumerate(m.rows) if r[1] == 0xF2)
    vector_idx = pcs.index(0x0A)
    assert 0x0A not in pcs[:ei_idx]  # not taken while I=0
    assert vector_idx == ei_idx + 1  # ...but still pending after EI
    assert m.regs[0] == 0x42
    assert m.fi == 0  # RETI leaves I=0


def test_irq_a_nivel_alto_no_se_retoma_tras_reti() -> None:
    # The handler runs once (irq_at=0 keeps the level high).  With I=0 after
    # RETI, the main loop must finish its 3 iterations without re-entering it:
    # output is 1 byte from the handler + 3 from the loop.
    programa = ensambla_hexa(
        """
        LDI D, 3
        EI
    loop: OUT A
        DEC D
        JNZ loop
        HLT
        NOP
        NOP
        LDI A, 0x42
        OUT A
        RETI
        """
    )
    m = iss.ISS(programa, irq_at=0, irq_vector=0x0A)  # handler at 0x0A
    m.run(50)
    assert [v for v, _ in m.outs] == [0x42] * 4
    assert [r[0] for r in m.rows].count(0x0A) == 1
    assert m.fi == 0


# ---------------------------------------------------------------------------
#  Contrast with the golden values (programs/*.asm vs programs/*.ref)
# ---------------------------------------------------------------------------

# pmod.asm is an endless hardware demo (no .ref); top_pmod_tb covers it.
PROGRAMAS = sorted(p for p in PROG_DIR.glob("*.asm") if p.stem not in {"irq", "pmod"})


@pytest.mark.parametrize("asm_path", PROGRAMAS, ids=lambda p: p.stem)
def test_iss_reproduce_los_ref(asm_path: Path) -> None:
    ref_path = asm_path.with_suffix(".ref")
    esperado = [int(t, 16) for t in ref_path.read_text().split()]
    m = ejecutar(asm_path.read_text())
    obtenido = [v for v, _ in m.outs]
    assert obtenido == esperado


# ---------------------------------------------------------------------------
#  Command line and .hex parsing
# ---------------------------------------------------------------------------
def test_leer_hex_ignora_comentarios(tmp_path) -> None:
    path = tmp_path / "x.hex"
    path.write_text("10 20 ; one\n30 // two\n")
    assert iss._leer_hex(path) == [0x10, 0x20, 0x30]


def test_main_devuelve_dos_si_falta_el_fichero(tmp_path, capsys) -> None:
    assert iss.main(["iss.py", str(tmp_path / "nope.hex")]) == 2
    assert "iss:" in capsys.readouterr().err


def test_main_devuelve_dos_con_un_max_invalido(tmp_path, capsys) -> None:
    path = tmp_path / "p.hex"
    path.write_text("F0\n")
    assert iss.main(["iss.py", "--max", "x", str(path)]) == 2
    assert "invalid --max" in capsys.readouterr().err
