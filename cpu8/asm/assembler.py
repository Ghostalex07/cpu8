#!/usr/bin/env python3
"""Two-pass assembler for the educational 8-bit CPU (cpu8).

Translates an ``.asm`` source into a ``.hex`` file (one byte in hexadecimal per
line) ready for the testbench to load with ``$readmemh``.

Usage::

    python3 assembler.py programa.asm -o programa.hex
    python3 assembler.py programa.asm            # writes programa.hex
    python3 assembler.py programa.asm -l         # also shows the listing

Source syntax (see ``docs/ISA.md``):

* Comments with ``;`` until the end of the line.
* Labels ``name:`` at the start of a line, alone or before an instruction.
  E.g.: ``loop: OUT A``.
* Mnemonics and registers are **case-insensitive**; labels are **not**
  (they are case-sensitive).
* Registers: A, B, C, D.
* Numbers: decimal (``7``, ``255``), hexadecimal (``0x20`` or ``$20``) and
  binary (``0b1010``).  A sign is allowed: a negative literal is interpreted in
  two's complement over 8 bits (``-1`` -> ``0xFF``); the valid range is
  ``-128..255`` (negatives are a convenience for writing masks or signed
  immediates).
* Direct ``LD``/``ST`` accept the address with or without brackets:
  ``LD A, [0x20]`` or ``LD A, 0x20``.  The destination can be a label.
* **Indirect** ``LD``/``ST`` (by register): ``LD A, [B]`` = ``A <- RAM[B]``.
* **Indexed** ``LD``/``ST`` (base + displacement): ``LD A, [B+3]`` =
  ``A <- RAM[B+3]``.  The base must be ``B``, ``C`` or ``D`` (with ``A`` the
  absolute mode would be used).
* Immediates with the ALU: ``ADDI``, ``SUBI``, ``CMPI`` (e.g. ``ADDI A, 5``).
* Signed jumps (after ``CMP``/``SUB``): ``JLT``, ``JGE``, ``JLE``, ``JGT``;
  and status jumps: ``JVS``, ``JVC``, ``JMI``, ``JPL`` (see ``docs/ISA.md`` §4).
* **Directives** (start with ``.``, case-insensitive):
  ``.equ NAME, expr`` defines a constant; ``.org expr`` sets the current
  address (pads with ``00`` if it advances, error if it goes backwards);
  ``.db item, ...`` emits bytes (numbers, labels or strings ``"..."`` with
  escapes ``\\n``, ``\\t``, ``\\r``, ``\\0``, ``\\\\`` and ``\\"``);
  ``.dw item, ...`` emits 16-bit little-endian words (numbers, labels or
  constants, two bytes per item, strings not accepted).

It is a **two-pass** assembler: the first pass assigns an address to each label
(for which it uses the size of each instruction: 2 bytes for
``LDI``/``ADDI``/``SUBI``/``CMPI``/``LD``/``ST``/``JMP``/``CALL``/``Jcc``, 1 byte
for the rest) and the second pass emits the bytes and resolves the references,
already known even if the label is defined further down.

Encoding (``docs/ISA.md`` §2, §3)::

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

# --- Registers: name -> index in the rd/rs field -----------------------------
REGISTROS: Final[dict[str, int]] = {"A": 0b00, "B": 0b01, "C": 0b10, "D": 0b11}

# --- Jump conditions (Jcc opcode, `1101 ff cc`) ------------------------------
#     The `ff` field (the rd bits of the byte, reserved) selects the family:
#       ff=00 unsigned (backward compatible), ff=01 signed, ff=10 status.
#     The stored value is already (family<<2)|condition, that is, the low 4
#     bits of byte 1 of the Jcc.
#     The aliases JHS/JLO use the inverted-C convention of docs/ISA.md (§4):
#         JHS = JC  -> jumps if rd >= rs (no borrow)
#         JLO = JNC -> jumps if rd <  rs (borrow)
CONDICIONES: Final[dict[str, int]] = {
    # family 00: unsigned
    "JZ": 0b0000,
    "JNZ": 0b0001,
    "JC": 0b0010,
    "JNC": 0b0011,
    "JHS": 0b0010,
    "JLO": 0b0011,
    # family 01: signed (two's complement), using N and V
    "JLT": 0b0100,
    "JGE": 0b0101,
    "JLE": 0b0110,
    "JGT": 0b0111,
    # family 10: status (V / N)
    "JVS": 0b1000,
    "JVC": 0b1001,
    "JMI": 0b1010,
    "JPL": 0b1011,
}

# --- Opcodes (bits [7:4] of the first byte) ----------------------------------
OP_GRP0: Final = 0x0  # INC/DEC/PUSH/POP (sub-operation in rd, register in rs)
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
OP_HLT: Final = 0xF  # system/memory group (sub-code in rd/rs)
OP_IND_LD: Final = 0xF4  # LD rd,[rs]  (group 0xF)
OP_IND_ST: Final = 0xF5  # ST rd,[rs]  (group 0xF)

OPCODE_ALU: Final[dict[str, int]] = {  # rd,rs instructions with the same form
    "ADD": OP_ADD,
    "SUB": OP_SUB,
    "AND": OP_AND,
    "OR": OP_OR,
    "XOR": OP_XOR,
    "CMP": OP_CMP,
}

# Sub-operations of the immediate page (opcode 0x1), in the rs field.
#   rs=00 LDI  (backward compatible), 01 ADDI, 10 SUBI, 11 CMPI.
OPCODE_INMEDIATO: Final[dict[str, int]] = {
    "LDI": 0b00,
    "ADDI": 0b01,
    "SUBI": 0b10,
    "CMPI": 0b11,
}

# Extensions of group 0xF (2 bytes): the 2nd byte carries (rd<<2)|rs.
OP_MUL: Final = 0xF6  # MUL rd,rs
OP_DIV: Final = 0xF7  # DIV rd,rs
# Ported I/O (2 bytes): byte2 = (rd<<2)|port.
OP_OUTP: Final = 0xF8  # OUT n, rd
OP_INP: Final = 0xF9  # IN  n, rd

# --- Extended (prefixed) instructions (Phase 12, docs/ISA.md §10) ------------
# byte1 = 0xFA; byte2 = (xop << 4) | (rd << 2) | rs, where `xop` is the extended
# sub-operation.  Only LDW/STW carry a third byte (the displacement).
OP_EXT: Final = 0xFA
XOP_NEG: Final = 0x0  # NEG  rd          (1 register)
XOP_NOT: Final = 0x1  # NOT  rd          (1 register)
XOP_ADC: Final = 0x2  # ADC  rd, rs
XOP_SBC: Final = 0x3  # SBC  rd, rs
XOP_SWAP: Final = 0x4  # SWAP rd, rs (alias XCHG)
XOP_ROL: Final = 0x5  # ROL  rd          (1 register)
XOP_ROR: Final = 0x6  # ROR  rd          (1 register)
XOP_LDW: Final = 0x7  # LDW  rd, [rs+off]  (3 bytes)
XOP_STW: Final = 0x8  # STW  rd, [rs+off]  (3 bytes)
XOP_TEST: Final = 0x9  # TEST rd, rs        (flags only)
XOP_PUSHF: Final = 0xA  # PUSHF              (no operands)
XOP_POPF: Final = 0xB  # POPF               (no operands)
XOP_ADCW: Final = 0xC  # ADCW pr, ps        (16-bit pair, 2 EXEC cycles)
XOP_SUBW: Final = 0xD  # SUBW pr, ps        (16-bit pair, 2 EXEC cycles)

# Instructions that take a second byte (immediate or address).
DOS_BYTES: Final[set[str]] = {
    "LDI",
    "ADDI",
    "SUBI",
    "CMPI",
    "LD",
    "ST",
    "JMP",
    "CALL",
    "MUL",
    "DIV",
    "NEG",
    "NOT",
    "ADC",
    "SBC",
    "SWAP",
    "XCHG",
    "ROL",
    "ROR",
    "TEST",
    "PUSHF",
    "POPF",
    "ADCW",
    "SUBW",
} | set(CONDICIONES)

# Prefixed instructions that also take a third byte (indexed displacement).
TRES_BYTES: Final[set[str]] = {"LDW", "STW"}

# All valid mnemonics.
MNEMONICOS: Final[set[str]] = (
    {
        "NOP",
        "LDI",
        "ADDI",
        "SUBI",
        "CMPI",
        "MOV",
        "LD",
        "ST",
        "SHL",
        "SHR",
        "JMP",
        "CALL",
        "OUT",
        "HLT",
        "INC",
        "DEC",
        "PUSH",
        "POP",
        "RET",
        "EI",
        "DI",
        "MUL",
        "DIV",
        "IN",
        "NEG",
        "NOT",
        "ADC",
        "SBC",
        "SWAP",
        "XCHG",
        "ROL",
        "ROR",
        "LDW",
        "STW",
        "TEST",
        "PUSHF",
        "POPF",
        "ADCW",
        "SUBW",
    }
    | set(OPCODE_ALU)
    | set(CONDICIONES)
)

# --- Assembler directives ----------------------------------------------------
# The mnemonic is normalized to uppercase when the line is parsed.
DIRECTIVAS: Final[set[str]] = {".ORG", ".DB", ".DW", ".EQU"}

# --- Precompiled regular expressions -----------------------------------------
_RE_ETIQUETA: Final = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:(.*)$")
_RE_IDENTIFICADOR: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_RE_DECIMAL: Final = re.compile(r"[0-9]+")
# Indexed addressing: <register> <+|-> <displacement>.  The first token must be
# a register name (not a label) to be treated this way.  The displacement can
# be a number (with sign) or a label.
_RE_INDEXADO: Final = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*([+\-])\s*(\S.*)?$")

# Accepted range for literals: 0..255, plus -128..-1 in two's complement.
_VALOR_MIN: Final = -128
_VALOR_MAX: Final = 255


class AssemblerError(Exception):
    """Assembly error with a line number to give clear messages."""

    def __init__(self, num_linea: int, mensaje: str) -> None:
        self.num_linea = num_linea
        self.mensaje = mensaje
        super().__init__(f"line {num_linea}: {mensaje}")


@dataclass
class Sentencia:
    """An instruction already placed in memory (result of pass 1)."""

    linea: int  # line number in the source (1-based)
    mnem: str  # mnemonic in uppercase
    ops: list[str]  # already tokenized operands
    texto: str  # original text (for the listing)
    dir: int  # assigned memory address


# ============================================================================
#  Source text parsing
# ============================================================================


def parsear_numero(tok: str) -> int:
    """Converts a numeric literal (dec/hex/bin, optional sign) to an integer.

    Accepts ``$20``, ``0x20``, ``0b1010``, decimal and a leading ``+``/``-``
    sign.  Raises ``ValueError`` if the token is not a valid literal.  It does
    not check the 0..255 range (that is handled by :func:`ensamblar`).
    """
    t = tok.strip()
    signo = 1
    if t[:1] in ("+", "-"):
        if t[0] == "-":
            signo = -1
        t = t[1:]

    if not t:
        raise ValueError(f"invalid number: '{tok}'")
    if t[0] == "$":  # unified with the standard 0x prefix
        t = "0x" + t[1:]
    if t[:2].lower() in ("0x", "0b"):
        valor = int(t, 0)  # base 0 infers 16/2 from the prefix
    elif _RE_DECIMAL.fullmatch(t):
        valor = int(t)
    else:
        raise ValueError(f"invalid number: '{tok}'")
    return signo * valor


def parsear_linea(texto: str) -> tuple[str | None, str | None, list[str]]:
    """Parses a source line and returns ``(label, mnemonic, operands)``.

    * ``etiqueta``: str or ``None``.
    * ``mnemonico``: str in uppercase or ``None`` (empty line / label only).
    * ``operandos``: list of tokens (str), without commas or outer brackets.
    """
    # Comments (';') run to the end of the line (ISA §8).
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
    """Bytes an instruction takes (for pass 1).

    Most have a fixed size; ``OUT``/``IN`` take 1 byte in their register form
    and 2 in the ported form ``OUT n, rd`` / ``IN n, rd``.
    """
    if mnem in TRES_BYTES:
        return 3
    if mnem in ("OUT", "IN"):
        return 2 if len(operandos) == 2 else 1
    return 2 if mnem in DOS_BYTES else 1


# ============================================================================
#  Pass 2: encoding an instruction
# ============================================================================


def indice_registro(tok: str, num_linea: int) -> int:
    if tok.upper() not in REGISTROS:
        raise AssemblerError(num_linea, f"unknown register '{tok}' (use A, B, C or D)")
    return REGISTROS[tok.upper()]


def exigir_operandos(num_linea: int, mnem: str, operandos: Sequence[str], n: int) -> None:
    if len(operandos) != n:
        raise AssemblerError(num_linea, f"{mnem} expects {n} operand(s), found {len(operandos)}")


def resolver_valor(resolver: Callable[[str], int], tok: str, num_linea: int) -> int:
    """Resolves a number or label and annotates the line on any error."""
    try:
        return resolver(tok)
    except AssemblerError as e:
        if e.num_linea == 0:
            raise AssemblerError(num_linea, e.mensaje) from e
        raise
    except Exception as e:
        # Any failure (e.g. ValueError from parsear_numero) is repackaged
        # with the correct line number.
        raise AssemblerError(num_linea, f"invalid value '{tok}': {e}") from e


def es_indirecto(op: str, etiquetas: Mapping[str, int]) -> bool:
    """Indicates whether ``op`` is a pointer register (indirect mode ``LD/ST rd,[rs]``).

    Disambiguation rule: a **label name** (case-sensitive) takes priority over a
    register name (case-insensitive).  Thus, with a label ``b`` defined,
    ``LD A, [b]`` is a direct access to address ``b``; while ``LD A, [B]``
    (without a label ``B``) is still the indirect mode with register ``B``.
    Without a collision, ``[B]`` is indirect.
    """
    return op not in etiquetas and op.upper() in REGISTROS


def codificar(
    num_linea: int,
    mnem: str,
    operandos: Sequence[str],
    resolver: Callable[[str], int],
    etiquetas: Mapping[str, int],
) -> list[int]:
    """Returns the list of bytes of an instruction.

    ``resolver(tok)`` converts a label or a number into its value 0..255.
    """
    if mnem == "NOP":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0x20]  # NOP = MOV A,A

    if mnem in OPCODE_INMEDIATO:
        # Immediate page (opcode 0x1): the sub-operation goes in the rs field.
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
        # Indexed (base + displacement): LD/ST rd,[rs+off].  The base goes in
        # the rs field (B/C/D) and the displacement in the 2nd byte.  rs=00
        # (base A) cannot be used because that value encodes the absolute mode.
        m_idx = _RE_INDEXADO.fullmatch(op2)
        if m_idx and m_idx.group(1) not in etiquetas:
            base = m_idx.group(1).upper()
            if base not in REGISTROS:
                raise AssemblerError(
                    num_linea,
                    f"unknown base '{m_idx.group(1)}' in indexed addressing (use B, C or D)",
                )
            if base == "A":
                raise AssemblerError(
                    num_linea,
                    "indexed addressing uses base B, C or D "
                    "(with base A the absolute mode would be used)",
                )
            expr = (m_idx.group(3) or "").strip()
            if not expr:
                raise AssemblerError(num_linea, "missing indexed displacement")
            off = resolver_valor(resolver, expr, num_linea)
            if m_idx.group(2) == "-":
                off = (-off) & 0xFF  # negative displacement (two's complement)
            return [((OP_LD if mnem == "LD" else OP_ST) << 4) | (rd << 2) | REGISTROS[base], off]
        # If the 2nd operand is a register -> indirect: LD/ST rd,[rs].
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
        sel = 0b00 if mnem == "SHL" else 0b01  # rs field: 00=SHL, 01=SHR
        return [(OP_SHIFT << 4) | (rd << 2) | sel]

    if mnem in ("INC", "DEC"):
        # Group 0x0: the sub-operation goes in rd (00=INC, 01=DEC) and the
        # affected register in rs.  They are 1 byte.
        exigir_operandos(num_linea, mnem, operandos, 1)
        reg = indice_registro(operandos[0], num_linea)
        subop = 0b00 if mnem == "INC" else 0b01
        return [(OP_GRP0 << 4) | (subop << 2) | reg]

    if mnem in ("PUSH", "POP"):
        # Group 0x0: subop 10 = PUSH, 11 = POP; the register goes in rs.  1 byte.
        exigir_operandos(num_linea, mnem, operandos, 1)
        reg = indice_registro(operandos[0], num_linea)
        subop = 0b10 if mnem == "PUSH" else 0b11
        return [(OP_GRP0 << 4) | (subop << 2) | reg]

    if mnem in ("MUL", "DIV"):
        # Group 0xF, 2 bytes: byte1 = 0xF6/0xF7, byte2 = (rd<<2)|rs.
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        rs = indice_registro(operandos[1], num_linea)
        return [OP_MUL if mnem == "MUL" else OP_DIV, (rd << 2) | rs]

    if mnem in ("NEG", "NOT", "ROL", "ROR"):
        # Extended unary (2 bytes): 0xFA, (xop<<4)|(rd<<2).
        exigir_operandos(num_linea, mnem, operandos, 1)
        rd = indice_registro(operandos[0], num_linea)
        xop = {"NEG": XOP_NEG, "NOT": XOP_NOT, "ROL": XOP_ROL, "ROR": XOP_ROR}[mnem]
        return [OP_EXT, (xop << 4) | (rd << 2)]

    if mnem in ("ADC", "SBC", "SWAP", "XCHG"):
        # Extended binary (2 bytes): 0xFA, (xop<<4)|(rd<<2)|rs.
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        rs = indice_registro(operandos[1], num_linea)
        xop = {"ADC": XOP_ADC, "SBC": XOP_SBC, "SWAP": XOP_SWAP, "XCHG": XOP_SWAP}[mnem]
        return [OP_EXT, (xop << 4) | (rd << 2) | rs]

    if mnem == "TEST":
        # Extended TEST (2 bytes): AND that only writes the flags.
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        rs = indice_registro(operandos[1], num_linea)
        return [OP_EXT, (XOP_TEST << 4) | (rd << 2) | rs]

    if mnem in ("PUSHF", "POPF"):
        # Extended flag stack ops (2 bytes, without operands).
        exigir_operandos(num_linea, mnem, operandos, 0)
        xop = XOP_PUSHF if mnem == "PUSHF" else XOP_POPF
        return [OP_EXT, (xop << 4)]

    if mnem in ("ADCW", "SUBW"):
        # Extended 16-bit pair ops (2 bytes).  The pair is (low, low|1): A is
        # the pair A:B and C the pair C:D, so both operands must be A or C
        # (docs/ISA.md §10.10).  The hardware takes 2 EXEC cycles.
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        rs = indice_registro(operandos[1], num_linea)
        if rd & 1 or rs & 1:
            raise AssemblerError(
                num_linea,
                f"{mnem} takes pairs: operands must be A (=A:B) or C (=C:D)",
            )
        xop = XOP_ADCW if mnem == "ADCW" else XOP_SUBW
        return [OP_EXT, (xop << 4) | (rd << 2) | rs]

    if mnem in ("LDW", "STW"):
        # Extended indexed (3 bytes): 0xFA, (xop<<4)|(rd<<2)|rs, off.
        # EA = rs + off (9 bits): RAM[EA[7:0]] and C <- EA[8] (16-bit pointer,
        # docs/ISA.md §10).  The base can be any register A-D.
        exigir_operandos(num_linea, mnem, operandos, 2)
        rd = indice_registro(operandos[0], num_linea)
        op2 = operandos[1]
        m_idx = _RE_INDEXADO.fullmatch(op2)
        if m_idx and m_idx.group(1) not in etiquetas:
            rs = indice_registro(m_idx.group(1), num_linea)
            expr = (m_idx.group(3) or "").strip()
            if not expr:
                raise AssemblerError(num_linea, "missing indexed displacement")
            off = resolver_valor(resolver, expr, num_linea)
            if m_idx.group(2) == "-":
                off = (-off) & 0xFF  # negative displacement
        elif not m_idx and _RE_IDENTIFICADOR.fullmatch(op2) and op2 not in etiquetas:
            rs = indice_registro(op2, num_linea)  # plain [rs]: off = 0
            off = 0
        else:
            raise AssemblerError(num_linea, f"{mnem} expects [rs+off] (base A, B, C or D)")
        xop = XOP_LDW if mnem == "LDW" else XOP_STW
        return [OP_EXT, (xop << 4) | (rd << 2) | rs, off]

    if mnem in ("OUT", "IN"):
        # Register form (1 byte): OUT rd = 0xE0|(rd<<2); IN rd = the same |01.
        if len(operandos) == 1:
            rd = indice_registro(operandos[0], num_linea)
            sub = 0b01 if mnem == "IN" else 0b00
            return [(OP_OUT << 4) | (rd << 2) | sub]
        # Ported form (2 bytes): byte2 = (rd<<2)|port.
        if len(operandos) == 2:
            puerto = resolver_valor(resolver, operandos[0], num_linea)
            if puerto > 3:
                raise AssemblerError(num_linea, f"port {puerto} out of range 0..3")
            rd = indice_registro(operandos[1], num_linea)
            op = OP_INP if mnem == "IN" else OP_OUTP
            return [op, (rd << 2) | puerto]
        raise AssemblerError(
            num_linea, f"{mnem} expects 1 or 2 operands ((rd) or (n, rd)), found {len(operandos)}"
        )

    if mnem == "HLT":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0xF0]

    if mnem == "RET":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0xF1]

    if mnem == "EI":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0xF2]  # enables interrupts (flag I <= 1)

    if mnem == "DI":
        exigir_operandos(num_linea, mnem, operandos, 0)
        return [0xF3]  # disables interrupts (flag I <= 0)

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

    raise AssemblerError(num_linea, f"unknown mnemonic '{mnem}'")


# ============================================================================
#  Directives (.org, .db, .dw, .equ)
# ============================================================================

# Escapes allowed inside .db strings.
_ESCAPES: Final[dict[str, int]] = {
    "n": 0x0A,
    "t": 0x09,
    "r": 0x0D,
    "0": 0x00,
    "\\": 0x5C,
    '"': 0x22,
}


def _resto_operandos(texto: str) -> str:
    """Returns the text after the mnemonic, without comment or label."""
    sin_com = texto.split(";", 1)[0]
    m = _RE_ETIQUETA.match(sin_com)
    if m:
        sin_com = m.group(2)
    sin_com = sin_com.strip()
    partes = sin_com.split(None, 1)
    return partes[1] if len(partes) > 1 else ""


def _dividir_db(texto: str) -> list[str]:
    """Splits ``.db`` operands by commas, respecting the strings."""
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
    """Converts the content of a string to ASCII bytes."""
    out: list[int] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\":
            if i + 1 >= len(s) or s[i + 1] not in _ESCAPES:
                esc = s[i + 1] if i + 1 < len(s) else ""
                raise AssemblerError(num_linea, f"invalid escape '\\{esc}'")
            out.append(_ESCAPES[s[i + 1]])
            i += 2
            continue
        if ord(ch) > 0xFF:
            raise AssemblerError(num_linea, f"non-ASCII character (0x{ord(ch):X}) in string")
        out.append(ord(ch))
        i += 1
    return out


def _comprobar_rango(bruto: int, num_linea: int) -> int:
    """Validates 0..255 (or -128..-1 in two's complement) and returns the byte 0..255."""
    valor = bruto + 256 if bruto < 0 else bruto
    if not (_VALOR_MIN <= bruto <= _VALOR_MAX) or not (0 <= valor <= 255):
        raise AssemblerError(num_linea, f"value {bruto} out of range 0..255 (or -128..-1)")
    return valor


# ============================================================================
#  Main process (two passes + constants)
# ============================================================================


def ensamblar(
    texto_fuente: str,
) -> tuple[list[int], dict[str, int], list[tuple[int, list[int], str]]]:
    """Assembles the text and returns ``(bytes, labels, listing)``.

    ``listado``: list of ``(address, [bytes], original_text)`` per
    instruction or directive.  Raises :class:`AssemblerError` on any problem.
    """
    # A UTF-8 BOM (e.g. if the source was saved with a BOM) is not part of the
    # code: it is discarded so as not to corrupt the first mnemonic.
    texto_fuente = texto_fuente.removeprefix("\ufeff")

    lineas = texto_fuente.splitlines()
    crudas: list[tuple[int, str | None, str | None, list[str], str]] = []
    for i, linea in enumerate(lineas, start=1):
        etiqueta, mnem, operandos = parsear_linea(linea)
        crudas.append((i, etiqueta, mnem, operandos, linea.rstrip()))

    # ---- Pass 0: constants (.equ) ------------------------------------------
    constantes: dict[str, int] = {}

    def resolver_const(tok: str, num_linea: int) -> int:
        if tok in constantes:
            return constantes[tok]
        try:
            bruto = parsear_numero(tok)
        except ValueError:
            if _RE_IDENTIFICADOR.fullmatch(tok):
                raise AssemblerError(num_linea, f"undefined constant '{tok}'") from None
            raise AssemblerError(num_linea, f"invalid value '{tok}'") from None
        return _comprobar_rango(bruto, num_linea)

    for i, _etq, mnem, ops, _texto in crudas:
        if mnem != ".EQU":
            continue
        if len(ops) != 2:
            raise AssemblerError(i, ".equ expects NAME, value")
        nombre = ops[0]
        if not _RE_IDENTIFICADOR.fullmatch(nombre):
            raise AssemblerError(i, f"invalid constant name '{nombre}'")
        if nombre in constantes:
            raise AssemblerError(i, f"duplicated constant '{nombre}'")
        constantes[nombre] = resolver_const(ops[1], i)

    # ---- Pass 1: label addresses and program size --------------------------
    etiquetas: dict[str, int] = {}  # name -> address
    plan: list[tuple] = []
    pc = 0
    linea_overflow: int | None = None

    for i, etiqueta, mnem, ops, texto in crudas:
        if etiqueta is not None:
            if etiqueta in etiquetas:
                raise AssemblerError(i, f"duplicated label '{etiqueta}'")
            etiquetas[etiqueta] = pc

        if mnem is None or mnem == ".EQU":
            continue

        if mnem == ".ORG":
            if len(ops) != 1:
                raise AssemblerError(i, ".org expects an address")
            destino = resolver_const(ops[0], i)
            if destino < pc:
                raise AssemblerError(
                    i, f".org 0x{destino:02X} goes backwards (PC is already 0x{pc:02X})"
                )
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

        if mnem == ".DW":
            campos_w: list[str] = []
            for campo in _dividir_db(_resto_operandos(texto)):
                if not campo:
                    continue
                if campo.startswith('"'):
                    raise AssemblerError(i, "strings are not allowed in .dw")
                campos_w.append(campo)
            plan.append(("dw", campos_w, i, texto))
            pc += 2 * len(campos_w)
            if pc > 256 and linea_overflow is None:
                linea_overflow = i
            continue

        if mnem not in MNEMONICOS:
            raise AssemblerError(i, f"unknown mnemonic '{mnem}'")

        plan.append(("instr", Sentencia(i, mnem, ops, texto, pc)))
        pc += tamano_instruccion(mnem, ops)
        if pc > 256 and linea_overflow is None:
            linea_overflow = i

    if linea_overflow is not None:
        # The line where the program exceeds 256 bytes is reported, not the
        # total number of lines of the file (which includes comments/blank ones).
        raise AssemblerError(linea_overflow, f"program is {pc} bytes; the maximum is 256")

    # ---- Pass 2: encode, resolve labels and emit ---------------------------
    def resolver(tok: str) -> int:
        if tok in etiquetas:
            return etiquetas[tok]
        if tok in constantes:
            return constantes[tok]
        try:
            bruto = parsear_numero(tok)
        except ValueError:
            if _RE_IDENTIFICADOR.fullmatch(tok):
                raise AssemblerError(0, f"undefined label '{tok}'") from None
            raise AssemblerError(0, f"invalid value '{tok}'") from None
        # Negative literals are accepted in two's complement (byte).
        return _comprobar_rango(bruto, 0)

    def resolver_dw(tok: str) -> int:
        """Like ``resolver`` but with the 16-bit range needed by ``.dw``."""
        if tok in etiquetas:
            return etiquetas[tok]
        if tok in constantes:
            return constantes[tok]
        try:
            bruto = parsear_numero(tok)
        except ValueError:
            if _RE_IDENTIFICADOR.fullmatch(tok):
                raise AssemblerError(0, f"undefined label '{tok}'") from None
            raise AssemblerError(0, f"invalid value '{tok}'") from None
        if not (-0x8000 <= bruto <= 0xFFFF):
            raise AssemblerError(0, f"value {bruto} out of range 0..65535 (or -32768..-1)")
        return bruto & 0xFFFF

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
                    bs.extend(valor)  # type: ignore[arg-type]
                else:
                    bs.append(resolver_valor(resolver, valor, i))  # type: ignore[arg-type]
            dir_ = len(salida)
            salida.extend(bs)
            listado.append((dir_, bs, texto))
        elif entrada[0] == "dw":
            _dw_campos, _linea, texto_dw = entrada[1], entrada[2], entrada[3]
            bs_w: list[int] = []
            for campo in _dw_campos:  # type: ignore[union-attr]
                v = resolver_valor(resolver_dw, campo, _linea)  # type: ignore[arg-type]
                bs_w.append(v & 0xFF)
                bs_w.append(v >> 8)
            dir_dw = len(salida)
            salida.extend(bs_w)
            listado.append((dir_dw, bs_w, texto_dw))
        else:
            st = entrada[1]
            bs = codificar(st.linea, st.mnem, st.ops, resolver, etiquetas)
            salida.extend(bs)
            listado.append((st.dir, bs, st.texto))

    return salida, etiquetas, listado


# ============================================================================
#  Command-line interface
# ============================================================================


def formatear_listado(listado: Sequence[tuple[int, Sequence[int], str]]) -> str:
    lineas = []
    for dir_, bs, texto in listado:
        hexs = " ".join(f"{b:02X}" for b in bs)
        lineas.append(f"  {dir_:02X}:  {hexs:<6}  {texto}")
    return "\n".join(lineas)


def _fichero_salida_por_defecto(fuente: str) -> str:
    """``prog.asm`` -> ``prog.hex`` (or ``prog.hex`` if there is no .asm extension)."""
    raiz, ext = os.path.splitext(fuente)
    if ext.lower() == ".asm":
        return raiz + ".hex"
    return fuente + ".hex"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Assembler for the 8-bit CPU (cpu8)")
    ap.add_argument("fuente", help="input .asm file")
    ap.add_argument(
        "-o", "--salida", help="output .hex file (by default, the same name with a .hex extension)"
    )
    ap.add_argument(
        "-l",
        "--listado",
        action="store_true",
        help="show the address, bytes and source of each line",
    )
    args = ap.parse_args(argv)

    fichero_salida = args.salida or _fichero_salida_por_defecto(args.fuente)

    try:
        with open(args.fuente, encoding="utf-8-sig") as f:
            texto = f.read()
    except OSError as e:
        print(f"Error: cannot open '{args.fuente}': {e}", file=sys.stderr)
        return 1

    try:
        salida, etiquetas, listado = ensamblar(texto)
    except AssemblerError as e:
        print(f"Assembly error in {args.fuente}, {e}", file=sys.stderr)
        return 1

    if not salida:
        print(
            f"Warning: '{args.fuente}' contains no instruction; an empty .hex is generated.",
            file=sys.stderr,
        )

    try:
        with open(fichero_salida, "w", encoding="utf-8") as f:
            f.writelines(f"{b:02X}\n" for b in salida)
    except OSError as e:
        print(f"Error: cannot write '{fichero_salida}': {e}", file=sys.stderr)
        return 1

    if args.listado:
        print(formatear_listado(listado))
        if etiquetas:
            print("\nLabels:")
            for nombre, dir_ in sorted(etiquetas.items(), key=lambda kv: kv[1]):
                print(f"  {nombre:<12} = 0x{dir_:02X}")

    print(f"Assembled: {len(salida)} bytes -> {fichero_salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
