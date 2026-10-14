#!/usr/bin/env python3
"""Generator of *valid* random programs for cpu8.

Used in the regression harness (`tools/regress.py`) and in the tests for the
assembler/disassembler round-trip fuzz: the generated source is assembled,
disassembled and assembled again, and the bytes must match.

The generator only produces instructions with valid syntax and, for jumps,
addresses that fall at the start of *some* instruction of the program itself
(so that the disassembler can label them and the reassembly can resolve them).
"""

from __future__ import annotations

import random

REGISTROS = ("A", "B", "C", "D")
BASES_INDEXADO = ("B", "C", "D")   # A (rs=00) encodes absolute mode
_ALU = ("ADD", "SUB", "AND", "OR", "XOR", "CMP")
_INMEDIATOS = ("LDI", "ADDI", "SUBI", "CMPI")
_DESPLAZAMIENTOS = ("SHL", "SHR")
_SALTOS = ("JMP", "CALL", "JZ", "JNZ", "JC", "JNC", "JLT", "JGE", "JLE",
           "JGT", "JVS", "JVC", "JMI", "JPL")
_SIN_OPERANDO = ("EI", "DI", "RET", "HLT")


def _longitud(linea: str) -> int:
    """Bytes that the line will occupy (same rule as the assembler)."""
    mnem = linea.split()[0].upper()
    if mnem in ("LDI", "ADDI", "SUBI", "CMPI", "LD", "ST", "JMP", "CALL",
                "MUL", "DIV") or mnem in _SALTOS:
        return 2
    if mnem in ("OUT", "IN"):
        return 2 if "," in linea[3:] else 1
    return 1


def generar_fuente(rng: random.Random, n: int) -> str:
    """Returns the text of a random program with ``n`` instructions."""
    lineas: list[str] = []
    direccion = 0
    inicios: list[int] = []
    for _ in range(n):
        inicios.append(direccion)
        lineas.append(_linea_aleatoria(rng))
        direccion += _longitud(lineas[-1])
    # Replaces the jump placeholders with valid addresses (start of an
    # instruction).  Done in a 2nd pass because the lengths do not depend on
    # the jump target.
    if inicios:
        for k, ln in enumerate(lineas):
            if "{T}" in ln:
                lineas[k] = ln.replace("{T}", f"0x{rng.choice(inicios):02X}")
    return "\n".join(lineas) + "\n"


def _linea_aleatoria(rng: random.Random) -> str:
    r, s = rng.choice(REGISTROS), rng.choice(REGISTROS)
    imm = rng.randrange(256)
    k = rng.randrange(13)

    if k == 0:
        return f"{rng.choice(('INC', 'DEC'))} {r}"
    if k == 1:
        return f"{rng.choice(_INMEDIATOS)} {r}, 0x{imm:02X}"
    if k == 2:
        return f"MOV {r}, {s}"
    if k == 3:
        return f"{rng.choice(_ALU)} {r}, {s}"
    if k == 4:
        return f"{rng.choice(('PUSH', 'POP'))} {r}"
    if k == 5:
        return f"{rng.choice(_DESPLAZAMIENTOS)} {r}"
    if k == 6:
        # LD/ST in its three forms: absolute, indexed and indirect.
        m = rng.choice(("LD", "ST"))
        forma = rng.randrange(3)
        if forma == 0:
            return f"{m} {r}, [0x{imm:02X}]"
        if forma == 1:
            base = rng.choice(BASES_INDEXADO)
            off = rng.randrange(-128, 128)
            return f"{m} {r}, [{base}{off:+d}]"
        return f"{m} {r}, [{s}]"
    if k == 7:
        return f"{rng.choice(('MUL', 'DIV'))} {r}, {s}"
    if k == 8:
        if rng.random() < 0.5:
            return f"OUT {r}"
        return f"OUT {rng.randrange(4)}, {r}"
    if k == 9:
        if rng.random() < 0.5:
            return f"IN {r}"
        return f"IN {rng.randrange(4)}, {r}"
    if k == 10:
        return f"{rng.choice(_SIN_OPERANDO)}"
    if k == 11:
        return f"{rng.choice(_SALTOS)} {{T}}"   # target resolved in 2nd pass
    # NOP (encoded as MOV A, A) for variety.
    return "NOP"
