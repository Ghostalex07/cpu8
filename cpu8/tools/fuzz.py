#!/usr/bin/env python3
"""Generador de programas aleatorios *validos* para cpu8.

Se usa en el harness de regresion (`tools/regress.py`) y en los tests para el
fuzz de ida y vuelta del ensamblador/desensamblador: la fuente generada se
ensambla, se desensambla y se vuelve a ensamblar, y los bytes deben coincidir.

El generador solo produce instrucciones con sintaxis valida y, en los saltos,
direcciones que caen en el inicio de *alguna* instruccion del propio programa
(para que el desensamblador pueda etiquetarlas y el reensamblado resuelva).
"""

from __future__ import annotations

import random

REGISTROS = ("A", "B", "C", "D")
BASES_INDEXADO = ("B", "C", "D")   # A (rs=00) codifica el modo absoluto
_ALU = ("ADD", "SUB", "AND", "OR", "XOR", "CMP")
_INMEDIATOS = ("LDI", "ADDI", "SUBI", "CMPI")
_DESPLAZAMIENTOS = ("SHL", "SHR")
_SALTOS = ("JMP", "CALL", "JZ", "JNZ", "JC", "JNC", "JLT", "JGE", "JLE",
           "JGT", "JVS", "JVC", "JMI", "JPL")
_SIN_OPERANDO = ("EI", "DI", "RET", "HLT")


def _longitud(linea: str) -> int:
    """Bytes que ocupara la linea (misma regla que el ensamblador)."""
    mnem = linea.split()[0].upper()
    if mnem in ("LDI", "ADDI", "SUBI", "CMPI", "LD", "ST", "JMP", "CALL",
                "MUL", "DIV") or mnem in _SALTOS:
        return 2
    if mnem in ("OUT", "IN"):
        return 2 if "," in linea[3:] else 1
    return 1


def generar_fuente(rng: random.Random, n: int) -> str:
    """Devuelve el texto de un programa aleatorio de ``n`` instrucciones."""
    lineas: list[str] = []
    direccion = 0
    inicios: list[int] = []
    for _ in range(n):
        inicios.append(direccion)
        lineas.append(_linea_aleatoria(rng))
        direccion += _longitud(lineas[-1])
    # Sustituye los marcadores de salto por direcciones validas (inicio de
    # instruccion).  Se hace en una 2a pasada porque las longitudes no dependen
    # del destino del salto.
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
        # LD/ST en sus tres formas: absoluta, indexada e indirecta.
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
        return f"{rng.choice(_SALTOS)} {{T}}"   # destino resuelto en 2a pasada
    # NOP (se codifica como MOV A, A) para variar.
    return "NOP"
