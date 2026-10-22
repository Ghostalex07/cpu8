#!/usr/bin/env python3
"""Tests for the disassembler (tools/disasm.py).

Checks the decoding of each instruction group and, above all, the **round-trip**
property: assembling a program, disassembling it and assembling it again must
yield exactly the same bytes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "asm"))
sys.path.insert(0, str(RAIZ / "tools"))

import assembler  # noqa: E402
import disasm  # noqa: E402
import fuzz  # noqa: E402


def d(bs: list[int]) -> str:
    """Disassembles a single instruction and returns its text."""
    texto, _ = disasm.decodificar(bs, 0)
    return texto


def _id_bytes(bs: list[int]) -> str:
    """Readable pytest id for a byte sequence."""
    return " ".join(f"{b:02X}" for b in bs)


def _crudo(bs: list[int], etiquetas: bool = True) -> str:
    """Reassemblable source for a byte sequence."""
    return "\n".join(disasm.desensamblar_crudo(bs, etiquetas)) + "\n"


def test_reti() -> None:
    assert d([0xFA, 0xE0]) == "RETI"


# ---------------------------------------------------------------------------
#  Decoding by groups
# ---------------------------------------------------------------------------


def test_grupo0_inc_dec_push_pop() -> None:
    assert d([0x00]) == "INC A"
    assert d([0x05]) == "DEC B"
    assert d([0x0A]) == "PUSH C"
    assert d([0x0F]) == "POP D"


def test_inmediatos() -> None:
    assert d([0x10, 0x05]) == "LDI A, 0x05"
    assert d([0x15, 0x07]) == "ADDI B, 0x07"
    assert d([0x1A, 0x03]) == "SUBI C, 0x03"
    assert d([0x1F, 0x09]) == "CMPI D, 0x09"


def test_mov_alu() -> None:
    assert d([0x20]) == "MOV A, A"
    assert d([0x51]) == "ADD A, B"
    assert d([0x6B]) == "SUB C, D"
    assert d([0xA6]) == "CMP B, C"


def test_ld_st_directo_e_indexado() -> None:
    assert d([0x30, 0x20]) == "LD A, [0x20]"
    assert d([0x44, 0x20]) == "ST B, [0x20]"
    assert d([0x31, 0x03]) == "LD A, [B+3]"
    # Negative displacement shown with sign.
    assert d([0x36, 0xFF]) == "LD B, [C-1]"


def test_shift() -> None:
    assert d([0xB0]) == "SHL A"
    assert d([0xB5]) == "SHR B"


def test_jmp_call_jcc() -> None:
    assert d([0xC0, 0x04]) == "JMP L_0004"
    assert d([0xC1, 0x0A]) == "CALL L_000A"
    assert d([0xD0, 0x08]) == "JZ L_0008"
    assert d([0xD1, 0x08]) == "JNZ L_0008"
    assert d([0xD2, 0x08]) == "JC L_0008"
    assert d([0xD3, 0x08]) == "JNC L_0008"
    assert d([0xD4, 0x08]) == "JLT L_0008"
    assert d([0xD5, 0x08]) == "JGE L_0008"
    assert d([0xD6, 0x08]) == "JLE L_0008"
    assert d([0xD7, 0x08]) == "JGT L_0008"
    assert d([0xD8, 0x08]) == "JVS L_0008"
    assert d([0xDB, 0x08]) == "JPL L_0008"


def test_io_registro() -> None:
    assert d([0xE0]) == "OUT A"
    assert d([0xED]) == "IN D"


def test_grupo_f() -> None:
    assert d([0xF0]) == "HLT"
    assert d([0xF1]) == "RET"
    assert d([0xF2]) == "EI"
    assert d([0xF3]) == "DI"
    assert d([0xF4, 0x06]) == "LD B, [C]"
    assert d([0xF5, 0x0E]) == "ST D, [C]"
    assert d([0xF6, 0x01]) == "MUL A, B"
    assert d([0xF7, 0x0E]) == "DIV D, C"
    assert d([0xF8, 0x07]) == "OUT 3, B"
    assert d([0xF9, 0x0F]) == "IN 3, D"


def test_multibyte_longitudes() -> None:
    # 1-byte instructions consume 1; 2-byte ones, 2.
    for bs, ln in [([0xE0], 1), ([0xF8, 0x07], 2), ([0xC0, 0x04], 2), ([0x20], 1), ([0xF0], 1)]:
        assert disasm.decodificar(bs, 0)[1] == ln


# ---------------------------------------------------------------------------
#  Round-trip: asm -> hex -> (disassemble) -> asm -> hex  (identical bytes)
# ---------------------------------------------------------------------------

PROGRAMAS = sorted((RAIZ / "programs").glob("*.asm"))


@pytest.mark.parametrize("asm_path", PROGRAMAS, ids=lambda p: p.stem)
def test_round_trip_programas(asm_path: Path) -> None:
    original = assembler.ensamblar(asm_path.read_text())[0]
    fuente = "\n".join(disasm.desensamblar_crudo(original)) + "\n"
    # The raw listing has no directives; a round-trip must not be blocked by
    # the stack guard when the original program deliberately used .nostack.
    reensamblado = assembler.ensamblar(".nostack\n" + fuente)[0]
    assert reensamblado == original, (
        f"{asm_path.name}: the reassembly differs from the original\n{fuente}"
    )


# ---------------------------------------------------------------------------
#  Fuzz: valid random programs -> asm -> hex -> disasm -> asm -> hex
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("semilla", range(40))
def test_fuzz_round_trip(semilla: int) -> None:
    import random

    rng = random.Random(semilla)
    fuente = fuzz.generar_fuente(rng, rng.randrange(1, 40))
    original = assembler.ensamblar(fuente)[0]
    reensamblado = assembler.ensamblar("\n".join(disasm.desensamblar_crudo(original)) + "\n")[0]
    assert reensamblado == original, f"seed {semilla}:\n{fuente}"


# ---------------------------------------------------------------------------
#  Reserved/aliased encodings: emitted as .db so that the bytes are preserved
# ---------------------------------------------------------------------------

# rs[1] is ignored by the RTL (alu_sh = rs[0]): SHL/SHR only use rs[0].
ALIAS_SHIFT = (0xB2, 0xB3, 0xB6, 0xB7, 0xBA, 0xBB, 0xBE, 0xBF)
# JMP/CALL ignore the rd bits: only rd=00 is canonical.
ALIAS_SALTO = (0xC4, 0xC5, 0xC8, 0xC9, 0xCC, 0xCD)
# Jcc family 11 is an alias of family 10.
ALIAS_JCC = (0xDC, 0xDD, 0xDE, 0xDF)
ALIAS_RESERVADOS = [[b] for b in ALIAS_SHIFT] + [[b, 0x20] for b in ALIAS_SALTO + ALIAS_JCC]


@pytest.mark.parametrize("bs", ALIAS_RESERVADOS, ids=_id_bytes)
def test_alias_reservados_ida_y_vuelta(bs: list[int]) -> None:
    esperado = ".db " + ", ".join(f"0x{b:02X}" for b in bs)
    texto, longitud = disasm.decodificar(bs, 0)
    assert (texto, longitud) == (esperado, len(bs))
    assert assembler.ensamblar(_crudo(bs))[0] == bs
    # The listing shows the same .db text.
    assert any(".db" in linea for linea in disasm.desensamblar(bs))


# Second bytes with bits the RTL ignores: high nibble of the 0xF4-0xF9 forms
# and unused fields of the 0xFA extended operations.
ALIAS_OPERANDOS = [
    [0xF4, 0x10],
    [0xF5, 0x10],
    [0xF6, 0x10],
    [0xF7, 0x10],
    [0xF8, 0x10],
    [0xF9, 0x10],
    [0xFA, 0x01],  # NEG with rs != 0
    [0xFA, 0x17],  # NOT with rs != 0
    [0xFA, 0xA1],  # PUSHF with rd/rs != 0
    [0xFA, 0xB3],  # POPF with rd/rs != 0
    [0xFA, 0xE5],  # RETI with rd/rs != 0
    [0xFA, 0xC1],  # ADCW with a non-pair register
    [0xFA, 0xDD],  # SUBW with a non-pair register
]


@pytest.mark.parametrize("bs", ALIAS_OPERANDOS, ids=_id_bytes)
def test_operando_con_bits_ignorados_ida_y_vuelta(bs: list[int]) -> None:
    texto, longitud = disasm.decodificar(bs, 0)
    assert texto == ".db " + ", ".join(f"0x{b:02X}" for b in bs)
    assert longitud == len(bs)
    assert assembler.ensamblar(_crudo(bs))[0] == bs


# ---------------------------------------------------------------------------
#  Truncated jumps and jump targets that are not instruction starts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("b", [0xC0, 0xC1, 0xD0, 0xD1, 0xD7, 0xDB, 0xDC, 0xDF])
def test_salto_sin_operando_al_final(b: int) -> None:
    assert disasm._destinos([b]) == set()
    mem = [0x00, b]  # INC A followed by a jump without its target byte
    fuente = _crudo(mem)
    assert ".db" in fuente
    assert assembler.ensamblar(fuente)[0] == mem


@pytest.mark.parametrize(
    "mem",
    [
        [0xC0, 0x01, 0x20],  # JMP into its own operand (mid-instruction)
        [0xC1, 0x01, 0x20],  # CALL into its own operand
        [0xD0, 0x01, 0x20],  # JZ into the JMP operand
        [0xC0, 0x04, 0x20, 0xF0],  # JMP past the end
        [0xD7, 0x08, 0x20],  # JGT past the end
    ],
    ids=_id_bytes,
)
def test_salto_a_direccion_que_no_es_instruccion(mem: list[int]) -> None:
    fuente = _crudo(mem)
    assert "L_" not in fuente
    assert assembler.ensamblar(fuente)[0] == mem


def test_salto_a_inicio_valido_conserva_etiqueta() -> None:
    mem = [0xC0, 0x02, 0xF0]  # JMP to HLT
    fuente = _crudo(mem)
    assert "L_0002:" in fuente
    assert "JMP L_0002" in fuente
    assert assembler.ensamblar(fuente)[0] == mem


@pytest.mark.parametrize("b", range(256))
def test_byte_suelto_ida_y_vuelta(b: int) -> None:
    # A lone byte may be a truncated instruction: it must still reassemble
    # to exactly the same byte (as .db), without inventing operand bytes.
    assert assembler.ensamblar(_crudo([b]))[0] == [b]


# ---------------------------------------------------------------------------
#  Command line: usage and input errors return 2 without a traceback
# ---------------------------------------------------------------------------


def test_main_fichero_inexistente(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = disasm.main(["disasm.py", str(tmp_path / "no-existe.hex")])
    err = capsys.readouterr().err
    assert codigo == 2
    assert len(err.strip().splitlines()) == 1


def test_main_o_sin_valor(capsys: pytest.CaptureFixture[str]) -> None:
    codigo = disasm.main(["disasm.py", "programs/countdown.hex", "-o"])
    err = capsys.readouterr().err
    assert codigo == 2
    assert len(err.strip().splitlines()) == 1


def test_main_salida_no_escribible(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    entrada = tmp_path / "ok.hex"
    entrada.write_text("F0\n")
    salida = tmp_path / "no-existe" / "salida.lst"
    codigo = disasm.main(["disasm.py", str(entrada), "-o", str(salida)])
    err = capsys.readouterr().err
    assert codigo == 2
    assert len(err.strip().splitlines()) == 1


def test_main_asm_invalido(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fuente = tmp_path / "roto.asm"
    fuente.write_text("NO_EXISTE A\n")
    codigo = disasm.main(["disasm.py", str(fuente)])
    err = capsys.readouterr().err
    assert codigo == 2
    assert "Traceback" not in err
    assert len(err.strip().splitlines()) == 1


def test_main_camino_correcto(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    entrada = tmp_path / "ok.hex"
    entrada.write_text("F0\n")
    salida = tmp_path / "salida.lst"
    assert disasm.main(["disasm.py", str(entrada), "-o", str(salida)]) == 0
    assert "HLT" in salida.read_text()
    assert "Listing written to" in capsys.readouterr().out
