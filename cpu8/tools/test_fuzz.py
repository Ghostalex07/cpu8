#!/usr/bin/env python3
"""Tests for the random program generator ``tools/fuzz.py``.

The important property is that the length used to place jump targets matches the
assembler exactly; otherwise a generated jump can land in the middle of a
multi-byte instruction.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "asm"))
sys.path.insert(0, str(RAIZ / "tools"))

import assembler  # noqa: E402
import disasm  # noqa: E402
import fuzz  # noqa: E402


def _longitud_esperada(linea: str) -> int:
    partes = linea.split(None, 1)
    ops = [op.strip() for op in partes[1].split(",")] if len(partes) > 1 else []
    return assembler.tamano_instruccion(partes[0], ops)


def test_longitud_delega_en_el_ensamblador() -> None:
    # RETI and the JHS/JLO aliases are 2 bytes; the old table said 1.
    for linea in ("RETI", "JHS 0x10", "JLO 0x10", "OUT A", "OUT 1, A", "IN B", "IN 2, B"):
        assert fuzz._longitud(linea) == _longitud_esperada(linea)


def test_longitud_de_ldw_y_stw_es_tres() -> None:
    assert fuzz._longitud("LDW A, [B+1]") == 3
    assert fuzz._longitud("STW C, [D-1]") == 3


def test_los_saltos_generados_caen_en_inicios_de_instruccion() -> None:
    for semilla in range(5):
        rng = random.Random(semilla)
        fuente = fuzz.generar_fuente(rng, 40)
        bytes_prog, etiquetas, _ = assembler.ensamblar(fuente)
        # Every jump target is the address of some instruction, so decoding the
        # whole image must consume it without errors and round-trip.
        lineas = disasm.desensamblar_crudo(bytes_prog)
        assert assembler.ensamblar("\n".join(lineas) + "\n")[0] == bytes_prog
