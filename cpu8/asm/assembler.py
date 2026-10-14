#!/usr/bin/env python3
"""Ensamblador de dos pasadas para la CPU educativa de 8 bits (cpu8).

Traduce un fuente ``.asm`` a un fichero ``.hex`` (un byte en hexadecimal por
linea) listo para que el testbench lo cargue con ``$readmemh``.

Uso::

    python3 assembler.py programa.asm -o programa.hex
    python3 assembler.py programa.asm            # escribe programa.hex
    python3 assembler.py programa.asm -l         # ademas muestra el listado

Sintaxis del fuente (ver ``docs/ISA.md``):

* Comentarios con ``;`` hasta el final de la linea.
* Etiquetas ``nombre:`` al principio de una linea, solas o antes de una
  instruccion.  Ej: ``bucle: OUT A``.
* Mnemonicos y registros **insensibles** a mayusculas; las etiquetas **no**
  (son sensibles a mayusculas).
* Registros: A, B, C, D.
* Numeros: decimal (``7``, ``255``), hexadecimal (``0x20`` o ``$20``) y binario
  (``0b1010``).  Se admite signo: un literal negativo se interpreta en
  complemento a dos sobre 8 bits (``-1`` -> ``0xFF``); el rango valido es
  ``-128..255`` (los negativos son una comodidad para escribir mascaras o
  inmediatos con signo).
* ``LD``/``ST`` directos admiten la direccion con o sin corchetes:
  ``LD A, [0x20]`` o ``LD A, 0x20``.  El destino puede ser una etiqueta.
* ``LD``/``ST`` **indirectos** (por registro): ``LD A, [B]`` = ``A <- RAM[B]``.
* ``LD``/``ST`` **indexados** (base + desplazamiento): ``LD A, [B+3]`` =
  ``A <- RAM[B+3]``.  La base debe ser ``B``, ``C`` o ``D`` (con ``A`` se
  usaria el modo absoluto).
* Inmediatos con la ALU: ``ADDI``, ``SUBI``, ``CMPI`` (p. ej. ``ADDI A, 5``).
* Saltos con signo (tras ``CMP``/``SUB``): ``JLT``, ``JGE``, ``JLE``, ``JGT``;
  y de estado: ``JVS``, ``JVC``, ``JMI``, ``JPL`` (ver ``docs/ISA.md`` §4).
* **Directivas** (empiezan por ``.``, insensibles a mayusculas):
  ``.equ NOMBRE, expr`` define una constante; ``.org expr`` fija la direccion
  actual (rellena con ``00`` si avanza, error si retrocede); ``.db item, ...``
  emite bytes (numeros, etiquetas o cadenas ``"..."`` con escapes ``\\n``,
  ``\\t``, ``\\r``, ``\\0``, ``\\\\`` y ``\\"``).

Es un ensamblador de **dos pasadas**: la primera asigna una direccion a cada
etiqueta (para lo que usa el tamano de cada instruccion: 2 bytes para
``LDI``/``ADDI``/``SUBI``/``CMPI``/``LD``/``ST``/``JMP``/``CALL``/``Jcc``, 1 byte
para el resto) y la segunda emite los bytes y resuelve las referencias, ya
conocidas aunque la etiqueta se defina mas abajo.

Codificacion (``docs/ISA.md`` §2, §3)::

    byte1 = (opcode << 4) | (rd << 2) | rs
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

# --- Registros: nombre -> indice en el campo rd/rs ---------------------------
REGISTROS: Final[dict[str, int]] = {"A": 0b00, "B": 0b01, "C": 0b10, "D": 0b11}

# --- Condiciones de salto (opcode Jcc, `1101 ff cc`) -------------------------
#     El campo `ff` (los bits rd del byte, reservados) selecciona la familia:
#       ff=00 sin signo (retrocompatible), ff=01 con signo, ff=10 estado.
#     El valor guardado ya es (familia<<2)|condicion, es decir, los 4 bits bajos
#     del byte 1 del Jcc.
#     Los alias JHS/JLO usan el convenio de C invertido de docs/ISA.md (§4):
#         JHS = JC  -> salta si rd >= rs (no hubo borrow)
#         JLO = JNC -> salta si rd <  rs (hubo borrow)
CONDICIONES: Final[dict[str, int]] = {
    # familia 00: sin signo
    "JZ": 0b0000, "JNZ": 0b0001, "JC": 0b0010, "JNC": 0b0011,
    "JHS": 0b0010, "JLO": 0b0011,
    # familia 01: con signo (Ca2), usando N y V
    "JLT": 0b0100, "JGE": 0b0101, "JLE": 0b0110, "JGT": 0b0111,
    # familia 10: estado (V / N)
    "JVS": 0b1000, "JVC": 0b1001, "JMI": 0b1010, "JPL": 0b1011,
}

# --- Opcodes (bits [7:4] del primer byte) ------------------------------------
OP_GRP0: Final = 0x0   # INC/DEC/PUSH/POP (suboperacion en rd, registro en rs)
OP_LDI: Final = 0x1
OP_MOV: Final = 0x2
OP_LD: Final = 0x3
OP_ST: Final = 0x4
OP_ADD: Final = 0x5
OP_SUB: Final = 0x6
OP_AND: Final = 0x7
OP_OR: Final = 0x8
OP_XOR: Final = 0x9
OP_CMP: Final = 0xA
OP_SHIFT: Final = 0xB
OP_JMP: Final = 0xC
OP_JCC: Final = 0xD
OP_OUT: Final = 0xE
OP_HLT: Final = 0xF   # grupo sistema/memoria (subcodigo en rd/rs)
OP_IND_LD: Final = 0xF4   # LD rd,[rs]  (grupo 0xF)
OP_IND_ST: Final = 0xF5   # ST rd,[rs]  (grupo 0xF)

OPCODE_ALU: Final[dict[str, int]] = {  # instrucciones rd,rs con misma forma
    "ADD": OP_ADD, "SUB": OP_SUB, "AND": OP_AND,
    "OR": OP_OR, "XOR": OP_XOR, "CMP": OP_CMP,
}

# Suboperaciones de la pagina de inmediatos (opcode 0x1), en el campo rs.
#   rs=00 LDI  (retrocompatible), 01 ADDI, 10 SUBI, 11 CMPI.
OPCODE_INMEDIATO: Final[dict[str, int]] = {
    "LDI": 0b00, "ADDI": 0b01, "SUBI": 0b10, "CMPI": 0b11,
}

# Extensiones del grupo 0xF (2 bytes): el 2o byte lleva (rd<<2)|rs.
OP_MUL: Final = 0xF6   # MUL rd,rs
OP_DIV: Final = 0xF7   # DIV rd,rs
# E/S portada (2 bytes): byte2 = (rd<<2)|puerto.
OP_OUTP: Final = 0xF8  # OUT n, rd
OP_INP: Final = 0xF9   # IN  n, rd

# Instrucciones que ocupan un segundo byte (inmediato o direccion).
DOS_BYTES: Final[set[str]] = (
    {"LDI", "ADDI", "SUBI", "CMPI", "LD", "ST", "JMP", "CALL", "MUL", "DIV"}
    | set(CONDICIONES)
)

# Todos los mnemonicos validos.
MNEMONICOS: Final[set[str]] = (
    {"NOP", "LDI", "ADDI", "SUBI", "CMPI", "MOV", "LD", "ST", "SHL", "SHR",
     "JMP", "CALL", "OUT", "HLT", "INC", "DEC", "PUSH", "POP", "RET", "EI", "DI",
     "MUL", "DIV", "IN"}
    | set(OPCODE_ALU) | set(CONDICIONES)
)

# --- Directivas del ensamblador ---------------------------------------------
# El mnemonico se normaliza a mayusculas al analizar la linea.
DIRECTIVAS: Final[set[str]] = {".ORG", ".DB", ".EQU"}

# --- Expresiones regulares precompiladas -------------------------------------
_RE_ETIQUETA: Final = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:(.*)$")
_RE_IDENTIFICADOR: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_RE_DECIMAL: Final = re.compile(r"[0-9]+")
# Direccionamiento indexado: <registro> <+|-> <desplazamiento>.  El primer token
# debe ser un nombre de registro (no una etiqueta) para tratarse asi.  El
# desplazamiento puede ser un numero (con signo) o una etiqueta.
_RE_INDEXADO: Final = re.compile(
    r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*([+\-])\s*(\S.*)?$")

# Rango admitido para literales: 0..255, mas -128..-1 en complemento a dos.
_VALOR_MIN: Final = -128
_VALOR_MAX: Final = 255


class AssemblerError(Exception):
    """Error de ensamblado con numero de linea para dar mensajes claros."""

    def __init__(self, num_linea: int, mensaje: str) -> None:
        self.num_linea = num_linea
        self.mensaje = mensaje
        super().__init__(f"linea {num_linea}: {mensaje}")


@dataclass
class Sentencia:
    """Una instruccion ya situada en memoria (resultado del pase 1)."""

    linea: int          # numero de linea en el fuente (1-based)
    mnem: str           # mnemonico en mayusculas
    ops: list[str]      # operandos ya tokenizados
    texto: str          # texto original (para el listado)
    dir: int            # direccion de memoria asignada


# ============================================================================
#  Analisis del texto fuente
# ============================================================================

def parsear_numero(tok: str) -> int:
    """Convierte un literal numerico (dec/hex/bin, con signo opcional) a entero.

    Admite ``$20``, ``0x20``, ``0b1010``, decimal y un signo ``+``/``-``
    delante.  Lanza ``ValueError`` si el token no es un literal valido.  No
    comprueba el rango 0..255 (de eso se encarga :func:`ensamblar`).
    """
    t = tok.strip()
    signo = 1
    if t[:1] in ("+", "-"):
        if t[0] == "-":
            signo = -1
        t = t[1:]

    if not t:
        raise ValueError(f"numero no valido: '{tok}'")
    if t[0] == "$":              # se unifica con el prefijo estandar 0x
        t = "0x" + t[1:]
    if t[:2].lower() in ("0x", "0b"):
        valor = int(t, 0)        # base 0 deduce 16/2 del prefijo
    elif _RE_DECIMAL.fullmatch(t):
        valor = int(t)
    else:
        raise ValueError(f"numero no valido: '{tok}'")
    return signo * valor


def parsear_linea(texto: str) -> tuple[str | None, str | None, list[str]]:
    """Analiza una linea de fuente y devuelve ``(etiqueta, mnemonico, operandos)``.

    * ``etiqueta``:  str o ``None``.
    * ``mnemonico``: str en mayusculas o ``None`` (linea vacia / solo etiqueta).
    * ``operandos``: lista de tokens (str), sin comas ni corchetes exteriores.
    """
    # Los comentarios (';') llegan hasta el final de la linea (ISA §8).
    if ";" in texto:
        texto = texto.split(";", 1)[0]

    etiqueta = None
    m = _RE_ETIQUETA.match(texto)
    if m:
        etiqueta = m.group(1)
        texto = m.group(2)

    texto = texto.strip()
    if not texto:
        return etiqueta, None, []

    partes = texto.split(None, 1)
    mnemonico = partes[0].upper()
    operandos: list[str] = []
    if len(partes) > 1:
        for op in partes[1].split(","):
            op = op.strip()
            if not op:
                continue
            if op.startswith("[") and op.endswith("]"):
                op = op[1:-1].strip()
            operandos.append(op)

    return etiqueta, mnemonico, operandos


def tamano_instruccion(mnem: str, operandos: Sequence[str] = ()) -> int:
    """Bytes que ocupa una instruccion (para el pase 1).

    La mayoria tiene tamano fijo; ``OUT``/``IN`` ocupan 1 byte en su forma de
    registro y 2 en la forma portada ``OUT n, rd`` / ``IN n, rd``.
    """
    if mnem in ("OUT", "IN"):
        return 2 if len(operandos) == 2 else 1
    return 2 if mnem in DOS_BYTES else 1


# ============================================================================
#  Pase 2: codificacion de una instruccion
# ============================================================================

def indice_registro(tok: str, num_linea: int) -> int:
    if tok.upper() not in REGISTROS:
        raise AssemblerError(
            num_linea, f"registro desconocido '{tok}' (usa A, B, C o D)")
    return REGISTROS[tok.upper()]


def exigir_operandos(num_linea: int, mnem: str, operandos: Sequence[str],
                     n: int) -> None:
    if len(operandos) != n:
        raise AssemblerError(
            num_linea, f"{mnem} espera {n} operando(s), se encontraron "
                       f"{len(operandos)}")


def resolver_valor(resolver: Callable[[str], int], tok: str,
                   num_linea: int) -> int:
    """Resuelve numero o etiqueta y anota la linea en cualquier error."""
    try:
        return resolver(tok)
    except AssemblerError as e:
        if e.num_linea == 0:
            raise AssemblerError(num_linea, e.mensaje) from e
        raise
    except Exception as e:
        # Se reempaqueta cualquier fallo (p. ej. ValueError de parsear_numero)
        # con el numero de linea correcto.
        raise AssemblerError(num_linea, f"valor no valido '{tok}': {e}") from e


def es_indirecto(op: str, etiquetas: Mapping[str, int]) -> bool:
    """Indica si ``op`` es un registro puntero (modo indirecto ``LD/ST rd,[rs]``).

    Regla de desambiguacion: un **nombre de etiqueta** (sensible a mayusculas)
    tiene prioridad sobre un nombre de registro (insensible a mayusculas).  Asi,
    con una etiqueta ``b`` definida, ``LD A, [b]`` es un acceso directo a la
    direccion ``b``; mientras que ``LD A, [B]`` (sin etiqueta ``B``) sigue siendo
    el modo indirecto con el registro ``B``.  Sin colision, ``[B]`` es indirecto.
    """
    return op not in etiquetas and op.upper() in REGISTROS


def codificar(num_linea: int, mnem: str, operandos: Sequence[str],
              resolver: Callable[[str], int],
              etiquetas: Mapping[str, int]) -> list[int]:
    """Devuelve la lista de bytes de una instruccion.

    ``resolver(tok)`` convierte una etiqueta o un numero en su valor 0..255.
    """
    if mnem == "NOP":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0x20]  # NOP = MOV A,A

    if mnem in OPCODE_INMEDIATO:
        # Pagina de inmediatos (opcode 0x1): la suboperacion va en el campo rs.
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        imm = resolver_valor(resolver, operandos[1], num_linea)
        return [(OP_LDI << 4) | (rd << 2) | OPCODE_INMEDIATO[mnem], imm]

    if mnem == "MOV":
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        rs = indice_registro(operandos[1], num_linea)
        return [(OP_MOV << 4) | (rd << 2) | rs]

    if mnem in ("LD", "ST"):
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        op2 = operandos[1]
        # Indexado (base + desplazamiento): LD/ST rd,[rs+off].  La base va en el
        # campo rs (B/C/D) y el desplazamiento en el 2o byte.  rs=00 (base A) no
        # se puede usar porque ese valor codifica el modo absoluto.
        m_idx = _RE_INDEXADO.fullmatch(op2)
        if m_idx and m_idx.group(1) not in etiquetas:
            base = m_idx.group(1).upper()
            if base not in REGISTROS:
                raise AssemblerError(
                    num_linea, f"base desconocida '{m_idx.group(1)}' en "
                               f"direccionamiento indexado (usa B, C o D)")
            if base == "A":
                raise AssemblerError(
                    num_linea, "el direccionamiento indexado usa base B, C o D "
                               "(con base A usaria el modo absoluto)")
            expr = (m_idx.group(3) or "").strip()
            if not expr:
                raise AssemblerError(num_linea,
                                     "falta el desplazamiento del indexado")
            off = resolver_valor(resolver, expr, num_linea)
            if m_idx.group(2) == "-":
                off = (-off) & 0xFF          # desplazamiento negativo (Ca2)
            return [((OP_LD if mnem == "LD" else OP_ST) << 4) | (rd << 2)
                    | REGISTROS[base], off]
        # Si el 2o operando es un registro -> indirecto: LD/ST rd,[rs].
        if es_indirecto(op2, etiquetas):
            rs = REGISTROS[op2.upper()]
            byte1 = OP_IND_LD if mnem == "LD" else OP_IND_ST
            return [byte1, (rd << 2) | rs]
        addr = resolver_valor(resolver, op2, num_linea)
        return [((OP_LD if mnem == "LD" else OP_ST) << 4) | (rd << 2), addr]

    if mnem in OPCODE_ALU:
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        rs = indice_registro(operandos[1], num_linea)
        return [(OPCODE_ALU[mnem] << 4) | (rd << 2) | rs]

    if mnem in ("SHL", "SHR"):
        exigir_operandos(num_linea, mnem, operandos, 1)
        rd = indice_registro(operandos[0], num_linea)
        sel = 0b00 if mnem == "SHL" else 0b01  # campo rs: 00=SHL, 01=SHR
        return [(OP_SHIFT << 4) | (rd << 2) | sel]

    if mnem in ("INC", "DEC"):
        # Grupo 0x0: la suboperacion va en rd (00=INC, 01=DEC) y el registro
        # afectado en rs.  Son de 1 byte.
        exigir_operandos(num_linea, mnem, operandos, 1)
        reg = indice_registro(operandos[0], num_linea)
        subop = 0b00 if mnem == "INC" else 0b01
        return [(OP_GRP0 << 4) | (subop << 2) | reg]

    if mnem in ("PUSH", "POP"):
        # Grupo 0x0: subop 10 = PUSH, 11 = POP; el registro va en rs.  1 byte.
        exigir_operandos(num_linea, mnem, operandos, 1)
        reg = indice_registro(operandos[0], num_linea)
        subop = 0b10 if mnem == "PUSH" else 0b11
        return [(OP_GRP0 << 4) | (subop << 2) | reg]

    if mnem in ("MUL", "DIV"):
        # Grupo 0xF, 2 bytes: byte1 = 0xF6/0xF7, byte2 = (rd<<2)|rs.
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        rs = indice_registro(operandos[1], num_linea)
        return [OP_MUL if mnem == "MUL" else OP_DIV, (rd << 2) | rs]

    if mnem in ("OUT", "IN"):
        # Forma de registro (1 byte): OUT rd = 0xE0|(rd<<2); IN rd = lo mismo |01.
        if len(operandos) == 1:
            rd = indice_registro(operandos[0], num_linea)
            sub = 0b01 if mnem == "IN" else 0b00
            return [(OP_OUT << 4) | (rd << 2) | sub]
        # Forma portada (2 bytes): byte2 = (rd<<2)|puerto.
        if len(operandos) == 2:
            puerto = resolver_valor(resolver, operandos[0], num_linea)
            if puerto > 3:
                raise AssemblerError(
                    num_linea, f"puerto {puerto} fuera de rango 0..3")
            rd = indice_registro(operandos[1], num_linea)
            op = OP_INP if mnem == "IN" else OP_OUTP
            return [op, (rd << 2) | puerto]
        raise AssemblerError(
            num_linea, f"{mnem} espera 1 o 2 operandos ((rd) o (n, rd)), "
                       f"se encontraron {len(operandos)}")

    if mnem == "HLT":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0xF0]

    if mnem == "RET":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0xF1]

    if mnem == "EI":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0xF2]   # habilita interrupciones (flag I <= 1)

    if mnem == "DI":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0xF3]   # inhabilita interrupciones (flag I <= 0)

    if mnem == "JMP":
        exigir_operandos(num_linea, mnem, operandos, 1)
        addr = resolver_valor(resolver, operandos[0], num_linea)
        return [(OP_JMP << 4), addr]

    if mnem == "CALL":
        exigir_operandos(num_linea, mnem, operandos, 1)
        addr = resolver_valor(resolver, operandos[0], num_linea)
        return [(OP_JMP << 4) | 0x01, addr]  # 0xC1

    if mnem in CONDICIONES:
        exigir_operandos(num_linea, mnem, operandos, 1)
        addr = resolver_valor(resolver, operandos[0], num_linea)
        return [(OP_JCC << 4) | CONDICIONES[mnem], addr]

    raise AssemblerError(num_linea, f"mnemonico desconocido '{mnem}'")


# ============================================================================
#  Directivas (.org, .db, .equ)
# ============================================================================

# Escapes admitidos dentro de las cadenas de .db.
_ESCAPES: Final[dict[str, int]] = {
    "n": 0x0A, "t": 0x09, "r": 0x0D, "0": 0x00, "\\": 0x5C, '"': 0x22,
}


def _resto_operandos(texto: str) -> str:
    """Devuelve el texto tras el mnemonico, sin comentario ni etiqueta."""
    sin_com = texto.split(";", 1)[0]
    m = _RE_ETIQUETA.match(sin_com)
    if m:
        sin_com = m.group(2)
    sin_com = sin_com.strip()
    partes = sin_com.split(None, 1)
    return partes[1] if len(partes) > 1 else ""


def _dividir_db(texto: str) -> list[str]:
    """Divide los operandos de ``.db`` por comas respetando las cadenas."""
    items: list[str] = []
    actual: list[str] = []
    en_cadena = False
    esc = False
    for ch in texto:
        if en_cadena:
            actual.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                en_cadena = False
        elif ch == '"':
            en_cadena = True
            actual.append(ch)
        elif ch == ",":
            items.append("".join(actual).strip())
            actual = []
        else:
            actual.append(ch)
    resto = "".join(actual).strip()
    if resto:
        items.append(resto)
    return items


def _desescapar_cadena(s: str, num_linea: int) -> list[int]:
    """Convierte el contenido de una cadena a bytes ASCII."""
    out: list[int] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\":
            if i + 1 >= len(s) or s[i + 1] not in _ESCAPES:
                esc = s[i + 1] if i + 1 < len(s) else ""
                raise AssemblerError(num_linea, f"escape no valido '\\{esc}'")
            out.append(_ESCAPES[s[i + 1]])
            i += 2
            continue
        if ord(ch) > 0xFF:
            raise AssemblerError(
                num_linea, f"caracter no ASCII (0x{ord(ch):X}) en cadena")
        out.append(ord(ch))
        i += 1
    return out


def _comprobar_rango(bruto: int, num_linea: int) -> int:
    """Valida 0..255 (o -128..-1 en Ca2) y devuelve el byte 0..255."""
    valor = bruto + 256 if bruto < 0 else bruto
    if not (_VALOR_MIN <= bruto <= _VALOR_MAX) or not (0 <= valor <= 255):
        raise AssemblerError(
            num_linea, f"valor {bruto} fuera de rango 0..255 (o -128..-1)")
    return valor


# ============================================================================
#  Proceso principal (dos pasadas + constantes)
# ============================================================================

def ensamblar(texto_fuente: str) -> tuple[list[int], dict[str, int],
                                          list[tuple[int, list[int], str]]]:
    """Ensambla el texto y devuelve ``(bytes, etiquetas, listado)``.

    ``listado``: lista de ``(direccion, [bytes], texto_original)`` por
    instruccion o directiva.  Lanza :class:`AssemblerError` ante cualquier
    problema.
    """
    # Un BOM UTF-8 (p. ej. si el fuente se guardo con BOM) no es parte del
    # codigo: se descarta para no corromper el primer mnemonico.
    texto_fuente = texto_fuente.removeprefix("\ufeff")

    lineas = texto_fuente.splitlines()
    crudas: list[tuple[int, str | None, str | None, list[str], str]] = []
    for i, linea in enumerate(lineas, start=1):
        etiqueta, mnem, operandos = parsear_linea(linea)
        crudas.append((i, etiqueta, mnem, operandos, linea.rstrip()))

    # ---- Pase 0: constantes (.equ) -----------------------------------------
    constantes: dict[str, int] = {}

    def resolver_const(tok: str, num_linea: int) -> int:
        if tok in constantes:
            return constantes[tok]
        try:
            bruto = parsear_numero(tok)
        except ValueError:
            if _RE_IDENTIFICADOR.fullmatch(tok):
                raise AssemblerError(
                    num_linea, f"constante no definida '{tok}'") from None
            raise AssemblerError(num_linea, f"valor no valido '{tok}'") from None
        return _comprobar_rango(bruto, num_linea)

    for i, _etq, mnem, ops, _texto in crudas:
        if mnem != ".EQU":
            continue
        if len(ops) != 2:
            raise AssemblerError(i, ".equ espera NOMBRE, valor")
        nombre = ops[0]
        if not _RE_IDENTIFICADOR.fullmatch(nombre):
            raise AssemblerError(i, f"nombre de constante no valido '{nombre}'")
        if nombre in constantes:
            raise AssemblerError(i, f"constante duplicada '{nombre}'")
        constantes[nombre] = resolver_const(ops[1], i)

    # ---- Pase 1: direcciones de etiquetas y tamano del programa ------------
    etiquetas: dict[str, int] = {}   # nombre -> direccion
    plan: list[tuple] = []
    pc = 0
    linea_overflow: int | None = None

    for i, etiqueta, mnem, ops, texto in crudas:
        if etiqueta is not None:
            if etiqueta in etiquetas:
                raise AssemblerError(i, f"etiqueta duplicada '{etiqueta}'")
            etiquetas[etiqueta] = pc

        if mnem is None or mnem == ".EQU":
            continue

        if mnem == ".ORG":
            if len(ops) != 1:
                raise AssemblerError(i, ".org espera una direccion")
            destino = resolver_const(ops[0], i)
            if destino < pc:
                raise AssemblerError(
                    i, f".org 0x{destino:02X} retrocede (el PC ya es 0x{pc:02X})")
            plan.append(("org", destino, i, texto))
            pc = destino
            continue

        if mnem == ".DB":
            campos: list[tuple[str, object]] = []
            for campo in _dividir_db(_resto_operandos(texto)):
                if campo.startswith('"') and campo.endswith('"') and len(campo) >= 2:
                    campos.append(("str", _desescapar_cadena(campo[1:-1], i)))
                elif campo:
                    campos.append(("expr", campo))
            plan.append(("db", campos, i, texto))
            pc += sum(len(v) if t == "str" else 1 for t, v in campos)
            if pc > 256 and linea_overflow is None:
                linea_overflow = i
            continue

        if mnem not in MNEMONICOS:
            raise AssemblerError(i, f"mnemonico desconocido '{mnem}'")

        plan.append(("instr", Sentencia(i, mnem, ops, texto, pc)))
        pc += tamano_instruccion(mnem, ops)
        if pc > 256 and linea_overflow is None:
            linea_overflow = i

    if linea_overflow is not None:
        # Se informa de la linea donde el programa rebasa los 256 bytes, no
        # del total de lineas del fichero (que incluye comentarios/vacias).
        raise AssemblerError(
            linea_overflow,
            f"el programa ocupa {pc} bytes; el maximo es 256")

    # ---- Pase 2: codificar, resolver etiquetas y emitir --------------------
    def resolver(tok: str) -> int:
        if tok in etiquetas:
            return etiquetas[tok]
        if tok in constantes:
            return constantes[tok]
        try:
            bruto = parsear_numero(tok)
        except ValueError:
            if _RE_IDENTIFICADOR.fullmatch(tok):
                raise AssemblerError(0, f"etiqueta no definida '{tok}'") from None
            raise AssemblerError(0, f"valor no valido '{tok}'") from None
        # Los literales negativos se aceptan en complemento a dos (byte).
        return _comprobar_rango(bruto, 0)

    salida: list[int] = []
    listado: list[tuple[int, list[int], str]] = []
    for entrada in plan:
        if entrada[0] == "org":
            _, destino, _i, texto = entrada
            while len(salida) < destino:
                salida.append(0x00)
            listado.append((destino, [], texto))
        elif entrada[0] == "db":
            _, campos, i, texto = entrada
            bs: list[int] = []
            for tipo, valor in campos:
                if tipo == "str":
                    bs.extend(valor)               # type: ignore[arg-type]
                else:
                    bs.append(resolver_valor(resolver, valor, i))  # type: ignore[arg-type]
            dir_ = len(salida)
            salida.extend(bs)
            listado.append((dir_, bs, texto))
        else:
            st = entrada[1]
            bs = codificar(st.linea, st.mnem, st.ops, resolver, etiquetas)
            salida.extend(bs)
            listado.append((st.dir, bs, st.texto))

    return salida, etiquetas, listado


# ============================================================================
#  Interfaz de linea de comandos
# ============================================================================

def formatear_listado(listado: Sequence[tuple[int, Sequence[int], str]]) -> str:
    lineas = []
    for dir_, bs, texto in listado:
        hexs = " ".join(f"{b:02X}" for b in bs)
        lineas.append(f"  {dir_:02X}:  {hexs:<6}  {texto}")
    return "\n".join(lineas)


def _fichero_salida_por_defecto(fuente: str) -> str:
    """``prog.asm`` -> ``prog.hex`` (o ``prog.hex`` si no hay extension .asm)."""
    raiz, ext = os.path.splitext(fuente)
    if ext.lower() == ".asm":
        return raiz + ".hex"
    return fuente + ".hex"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Ensamblador de la CPU de 8 bits (cpu8)")
    ap.add_argument("fuente", help="fichero .asm de entrada")
    ap.add_argument("-o", "--salida",
                    help="fichero .hex de salida (por defecto, mismo nombre "
                         "con extension .hex)")
    ap.add_argument("-l", "--listado", action="store_true",
                    help="mostrar direccion, bytes y fuente de cada linea")
    args = ap.parse_args(argv)

    fichero_salida = args.salida or _fichero_salida_por_defecto(args.fuente)

    try:
        with open(args.fuente, encoding="utf-8-sig") as f:
            texto = f.read()
    except OSError as e:
        print(f"Error: no se puede abrir '{args.fuente}': {e}", file=sys.stderr)
        return 1

    try:
        salida, etiquetas, listado = ensamblar(texto)
    except AssemblerError as e:
        print(f"Error de ensamblado en {args.fuente}, {e}", file=sys.stderr)
        return 1

    if not salida:
        print(f"Aviso: '{args.fuente}' no contiene ninguna instruccion; "
              f"se genera un .hex vacio.", file=sys.stderr)

    try:
        with open(fichero_salida, "w", encoding="utf-8") as f:
            f.writelines(f"{b:02X}\n" for b in salida)
    except OSError as e:
        print(f"Error: no se puede escribir '{fichero_salida}': {e}",
              file=sys.stderr)
        return 1

    if args.listado:
        print(formatear_listado(listado))
        if etiquetas:
            print("\nEtiquetas:")
            for nombre, dir_ in sorted(etiquetas.items(), key=lambda kv: kv[1]):
                print(f"  {nombre:<12} = 0x{dir_:02X}")

    print(f"Ensamblado: {len(salida)} bytes -> {fichero_salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
