#!/usr/bin/env python3
"""Tests del desensamblador (tools/disasm.py).

Comprueba la decodificacion de cada grupo de instrucciones y, sobre todo, la
propiedad **round-trip**: ensamblar un programa, desensamblarlo y volver a
ensamblarlo debe dar exactamente los mismos bytes.
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
    """Desensambla una unica instruccion y devuelve su texto."""
    texto, _ = disasm.decodificar(bs, 0)
    return texto


# ---------------------------------------------------------------------------
#  Decodificacion por grupos
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
    # Desplazamiento negativo mostrado con signo.
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
    # Instrucciones de 1 byte consumen 1; las de 2 bytes, 2.
    for bs, ln in [([0xE0], 1), ([0xF8, 0x07], 2), ([0xC0, 0x04], 2),
                   ([0x20], 1), ([0xF0], 1)]:
        assert disasm.decodificar(bs, 0)[1] == ln


# ---------------------------------------------------------------------------
#  Round-trip: asm -> hex -> (desensamblar) -> asm -> hex  (bytes identicos)
# ---------------------------------------------------------------------------

PROGRAMAS = sorted((RAIZ / "programs").glob("*.asm"))


@pytest.mark.parametrize("asm_path", PROGRAMAS, ids=lambda p: p.stem)
def test_round_trip_programas(asm_path: Path) -> None:
    original = assembler.ensamblar(asm_path.read_text())[0]
    fuente = "\n".join(disasm.desensamblar_crudo(original)) + "\n"
    reensamblado = assembler.ensamblar(fuente)[0]
    assert reensamblado == original, (
        f"{asm_path.name}: el reensamblado difiere del original\n{fuente}")


# ---------------------------------------------------------------------------
#  Fuzz: programas aleatorios validos -> asm -> hex -> desasm -> asm -> hex
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("semilla", range(40))
def test_fuzz_round_trip(semilla: int) -> None:
    import random
    rng = random.Random(semilla)
    fuente = fuzz.generar_fuente(rng, rng.randrange(1, 40))
    original = assembler.ensamblar(fuente)[0]
    reensamblado = assembler.ensamblar(
        "\n".join(disasm.desensamblar_crudo(original)) + "\n")[0]
    assert reensamblado == original, f"semilla {semilla}:\n{fuente}"
