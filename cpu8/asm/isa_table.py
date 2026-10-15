#!/usr/bin/env python3
"""Single source of truth (machine-readable) for the cpu8 CPU ISA.

This module describes, with one entry per instruction and operand form, the
WHOLE instruction set of the CPU: mnemonic, form, opcode page, length in bytes,
the exact encoding rule (page + ``rd``/``rs`` fields and, where applicable, the
second byte), the affected flags and a brief description.

**It is the REFERENCE.** ``tools/gen_docs.py`` generates ``docs/OPCODES.md``
from here and ``asm/test_isa_table.py`` guarantees that the table does **not
drift**:

* it assembles a representative instruction of each entry with
  ``asm/assembler.py`` and checks that the bytes match the ones declared by the
  table;
* it disassembles those bytes with ``tools/disasm.py`` and checks the expected
  text;
* it checks that the set of mnemonics of the table is exactly
  ``assembler.MNEMONICOS``.

If the encoder or the decoder is changed without updating this table (or the
other way around), the tests fail. The values follow ``docs/ISA.md`` (source of
truth in prose) and the RTL (``rtl/alu.v``, ``rtl/control.v``, ``rtl/cpu.v``).

Flags convention (``docs/ISA.md`` §5 and ``rtl/cpu.v``): ``flags_we`` updates
Z, N and V; ``flags_c_we`` also updates C. That is why INC/DEC touch ``Z N V``
(not C) and arithmetic/logic touch ``Z C N V``. ``EI``/``DI`` only touch the
``I`` flag. The rest does not change flags.

The general encoding of the first byte is ``(opcode<<4) | (rd<<2) | rs``
(``docs/ISA.md`` §2). In the fields:

* ``pagina``: opcode nibble ``[7:4]`` (0x0..0xF);
* ``bajo``: low nibble of the 4-bit page (``rd``/``rs``/sub-code);
* ``byte2``: second byte (immediate/address/indices) or ``None`` if it is 1 byte;
* ``byte3``: third byte (only for the prefixed LDW/STW) or ``None``.

The extended (prefixed) instructions (``docs/ISA.md`` §10) encode ``byte1 = 0xFA``
(``pagina`` 0xF, ``bajo`` 0xA) and ``byte2 = (xop << 4) | (rd << 2) | rs``, where
``xop`` is the extended sub-operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Instruccion:
    """An ISA instruction/mnemonic and its operand form.

    ``bytes_codificados()`` rebuilds the bytes from ``pagina``, ``bajo`` and
    ``byte2`` (the declarative rule); the tests contrast those bytes with what
    ``assembler.ensamblar`` produces for ``muestra``.
    """

    mnemonico: str          # e.g. "ADD"
    forma: str              # operand form, e.g. "rd, rs"
    pagina: int             # opcode nibble [7:4] (0x0..0xF)
    bajo: int               # low nibble of the 1st byte (rd/rs/sub-code)
    byte2: int | None       # exact 2nd byte, or None if the instruction is 1 byte
    regla: str              # human-readable encoding rule (for the docs)
    banderas: str           # flags it modifies, e.g. "Z C N V" or "—"
    descripcion: str        # brief description
    muestra: str            # example source (one line) that assembles this form
    desensamblado: str      # exact text produced by tools/disasm.decodificar
    alias_de: str | None = None  # canonical mnemonic if it is an alias
    byte3: int | None = None     # exact 3rd byte (prefixed LDW/STW), else None

    @property
    def longitud(self) -> int:
        """Bytes the instruction takes (1, 2 or 3)."""
        if self.byte3 is not None:
            return 3
        return 2 if self.byte2 is not None else 1

    def bytes_codificados(self) -> tuple[int, ...]:
        """Exact bytes according to the rule declared in the table."""
        b1 = (self.pagina << 4) | self.bajo
        if self.byte2 is None:
            return (b1,)
        if self.byte3 is None:
            return (b1, self.byte2)
        return (b1, self.byte2, self.byte3)

    @property
    def byte1(self) -> int:
        """First byte (to group by page in the documentation)."""
        return (self.pagina << 4) | self.bajo


# --- Opcode page names (for docs/OPCODES.md) ---------------------------------
PAGINAS: Final[dict[int, str]] = {
    0x0: "Group 0x0 — single-register operations (INC/DEC/PUSH/POP)",
    0x1: "Immediates (LDI/ADDI/SUBI/CMPI)",
    0x2: "MOV / NOP",
    0x3: "LD — load from RAM (absolute/indexed)",
    0x4: "ST — store to RAM (absolute/indexed)",
    0x5: "ADD",
    0x6: "SUB",
    0x7: "AND",
    0x8: "OR",
    0x9: "XOR",
    0xA: "CMP",
    0xB: "SHL / SHR",
    0xC: "JMP / CALL",
    0xD: "Conditional jumps (Jcc)",
    0xE: "OUT / IN — port 0 (register form)",
    0xF: "System/memory group (HLT, RET, EI, DI, indirect, MUL/DIV, ported I/O, 0xFA prefix)",
}


# ============================================================================
#  ISA table (one entry per instruction / operand form)
# ============================================================================
#  Covers the 16 opcode pages (0x0..0xF).  The bytes of the entry are those of
#  `muestra`, which is a valid instruction representative of that form.
INSTRUCCIONES: Final[tuple[Instruccion, ...]] = (
    # ---- Page 0x0: INC/DEC/PUSH/POP (subop in rd, register in rs) ----------
    Instruccion(
        mnemonico="INC", forma="rd", pagina=0x0, bajo=0b0000, byte2=None,
        regla="(0x0<<4) + (00<<2) + rs",
        banderas="Z N V",
        descripcion="Increment rd: rd <- rd + 1 (Z, N, V; not C).",
        muestra="INC A", desensamblado="INC A",
    ),
    Instruccion(
        mnemonico="DEC", forma="rd", pagina=0x0, bajo=0b0101, byte2=None,
        regla="(0x0<<4) + (01<<2) + rs",
        banderas="Z N V",
        descripcion="Decrement rd: rd <- rd - 1 (Z, N, V; not C).",
        muestra="DEC B", desensamblado="DEC B",
    ),
    Instruccion(
        mnemonico="PUSH", forma="rd", pagina=0x0, bajo=0b1010, byte2=None,
        regla="(0x0<<4) + (10<<2) + rs",
        banderas="—",
        descripcion="Push rd: RAM[SP] <- rd; SP <- SP - 1.",
        muestra="PUSH C", desensamblado="PUSH C",
    ),
    Instruccion(
        mnemonico="POP", forma="rd", pagina=0x0, bajo=0b1111, byte2=None,
        regla="(0x0<<4) + (11<<2) + rs",
        banderas="—",
        descripcion="Pop: SP <- SP + 1; rd <- RAM[SP].",
        muestra="POP D", desensamblado="POP D",
    ),

    # ---- Page 0x1: immediates (sub-operation in rs) -----------------------
    Instruccion(
        mnemonico="LDI", forma="rd, imm", pagina=0x1, bajo=0b0000, byte2=0x05,
        regla="(0x1<<4) + (rd<<2) + 00 ; byte2 = imm",
        banderas="—",
        descripcion="Load immediate: rd <- imm.",
        muestra="LDI A, 0x05", desensamblado="LDI A, 0x05",
    ),
    Instruccion(
        mnemonico="ADDI", forma="rd, imm", pagina=0x1, bajo=0b0101, byte2=0x03,
        regla="(0x1<<4) + (rd<<2) + 01 ; byte2 = imm",
        banderas="Z C N V",
        descripcion="Add immediate: rd <- rd + imm (Z, C, N, V).",
        muestra="ADDI B, 0x03", desensamblado="ADDI B, 0x03",
    ),
    Instruccion(
        mnemonico="SUBI", forma="rd, imm", pagina=0x1, bajo=0b1010, byte2=0x06,
        regla="(0x1<<4) + (rd<<2) + 10 ; byte2 = imm",
        banderas="Z C N V",
        descripcion="Subtract immediate: rd <- rd - imm (Z, C, N, V).",
        muestra="SUBI C, 0x06", desensamblado="SUBI C, 0x06",
    ),
    Instruccion(
        mnemonico="CMPI", forma="rd, imm", pagina=0x1, bajo=0b1111, byte2=0x07,
        regla="(0x1<<4) + (rd<<2) + 11 ; byte2 = imm",
        banderas="Z C N V",
        descripcion="Compare with immediate: computes rd - imm (flags), does not store.",
        muestra="CMPI D, 0x07", desensamblado="CMPI D, 0x07",
    ),

    # ---- Page 0x2: MOV / NOP ----------------------------------------------
    Instruccion(
        mnemonico="MOV", forma="rd, rs", pagina=0x2, bajo=0b0001, byte2=None,
        regla="(0x2<<4) + (rd<<2) + rs",
        banderas="—",
        descripcion="Copy register: rd <- rs.",
        muestra="MOV A, B", desensamblado="MOV A, B",
    ),
    Instruccion(
        mnemonico="NOP", forma="", pagina=0x2, bajo=0b0000, byte2=None,
        regla="0x20 (alias of MOV A, A)",
        banderas="—",
        descripcion="No operation; alias of MOV A,A (0x20).",
        muestra="NOP", desensamblado="MOV A, A", alias_de="MOV",
    ),

    # ---- Page 0x3: LD (absolute / indexed) --------------------------------
    Instruccion(
        mnemonico="LD", forma="rd, [a]", pagina=0x3, bajo=0b0000, byte2=0x20,
        regla="(0x3<<4) + (rd<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Absolute load: rd <- RAM[a].",
        muestra="LD A, [0x20]", desensamblado="LD A, [0x20]",
    ),
    Instruccion(
        mnemonico="LD", forma="rd, [rs+off]", pagina=0x3, bajo=0b1110, byte2=0x03,
        regla="(0x3<<4) + (rd<<2) + ss ; byte2 = off (ss=B/C/D)",
        banderas="—",
        descripcion="Indexed load: rd <- RAM[rs+off] (base B/C/D).",
        muestra="LD D, [C+3]", desensamblado="LD D, [C+3]",
    ),

    # ---- Page 0x4: ST (absolute / indexed) --------------------------------
    Instruccion(
        mnemonico="ST", forma="rd, [a]", pagina=0x4, bajo=0b0000, byte2=0x20,
        regla="(0x4<<4) + (rd<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Absolute store: RAM[a] <- rd.",
        muestra="ST A, [0x20]", desensamblado="ST A, [0x20]",
    ),
    Instruccion(
        mnemonico="ST", forma="rd, [rs+off]", pagina=0x4, bajo=0b0001, byte2=0x03,
        regla="(0x4<<4) + (rd<<2) + ss ; byte2 = off (ss=B/C/D)",
        banderas="—",
        descripcion="Indexed store: RAM[rs+off] <- rd (base B/C/D).",
        muestra="ST A, [B+3]", desensamblado="ST A, [B+3]",
    ),

    # ---- Pages 0x5..0xA: ALU rd,rs ----------------------------------------
    Instruccion(
        mnemonico="ADD", forma="rd, rs", pagina=0x5, bajo=0b0001, byte2=None,
        regla="(0x5<<4) + (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="rd <- rd + rs (Z, C, N, V).",
        muestra="ADD A, B", desensamblado="ADD A, B",
    ),
    Instruccion(
        mnemonico="SUB", forma="rd, rs", pagina=0x6, bajo=0b0001, byte2=None,
        regla="(0x6<<4) + (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="rd <- rd - rs (Z, C, N, V).",
        muestra="SUB A, B", desensamblado="SUB A, B",
    ),
    Instruccion(
        mnemonico="AND", forma="rd, rs", pagina=0x7, bajo=0b1011, byte2=None,
        regla="(0x7<<4) + (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="rd <- rd AND rs (Z, N; C=0, V=0).",
        muestra="AND C, D", desensamblado="AND C, D",
    ),
    Instruccion(
        mnemonico="OR", forma="rd, rs", pagina=0x8, bajo=0b1011, byte2=None,
        regla="(0x8<<4) + (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="rd <- rd OR rs (Z, N; C=0, V=0).",
        muestra="OR C, D", desensamblado="OR C, D",
    ),
    Instruccion(
        mnemonico="XOR", forma="rd, rs", pagina=0x9, bajo=0b1011, byte2=None,
        regla="(0x9<<4) + (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="rd <- rd XOR rs (Z, N; C=0, V=0).",
        muestra="XOR C, D", desensamblado="XOR C, D",
    ),
    Instruccion(
        mnemonico="CMP", forma="rd, rs", pagina=0xA, bajo=0b0011, byte2=None,
        regla="(0xA<<4) + (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="Computes rd - rs (flags), does not store (Z, C, N, V).",
        muestra="CMP A, D", desensamblado="CMP A, D",
    ),

    # ---- Page 0xB: SHL / SHR (sub-operation in rs) ------------------------
    Instruccion(
        mnemonico="SHL", forma="rd", pagina=0xB, bajo=0b0000, byte2=None,
        regla="(0xB<<4) + (rd<<2) + 00",
        banderas="Z C N V",
        descripcion="Shift rd 1 bit left (Z, C, N, V).",
        muestra="SHL A", desensamblado="SHL A",
    ),
    Instruccion(
        mnemonico="SHR", forma="rd", pagina=0xB, bajo=0b1101, byte2=None,
        regla="(0xB<<4) + (rd<<2) + 01",
        banderas="Z C N V",
        descripcion="Shift rd 1 bit right (Z, C, N, V).",
        muestra="SHR D", desensamblado="SHR D",
    ),

    # ---- Page 0xC: JMP / CALL (subtype in rs) -----------------------------
    Instruccion(
        mnemonico="JMP", forma="a", pagina=0xC, bajo=0b0000, byte2=0x10,
        regla="(0xC<<4) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Unconditional jump: PC <- a.",
        muestra="JMP 0x10", desensamblado="JMP L_0010",
    ),
    Instruccion(
        mnemonico="CALL", forma="a", pagina=0xC, bajo=0b0001, byte2=0x10,
        regla="(0xC<<4) + 01 ; byte2 = a",
        banderas="—",
        descripcion="Call subroutine: push(PC); PC <- a (does not change flags).",
        muestra="CALL 0x10", desensamblado="CALL L_0010",
    ),

    # ---- Page 0xD: Jcc (family in rd, condition in rs) --------------------
    Instruccion(
        mnemonico="JZ", forma="a", pagina=0xD, bajo=0b0000, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Jump if Z=1 (rd == rs).",
        muestra="JZ 0x10", desensamblado="JZ L_0010",
    ),
    Instruccion(
        mnemonico="JNZ", forma="a", pagina=0xD, bajo=0b0001, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 01 ; byte2 = a",
        banderas="—",
        descripcion="Jump if Z=0 (rd != rs).",
        muestra="JNZ 0x10", desensamblado="JNZ L_0010",
    ),
    Instruccion(
        mnemonico="JC", forma="a", pagina=0xD, bajo=0b0010, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 10 ; byte2 = a",
        banderas="—",
        descripcion="Jump if C=1 (rd >= rs, no borrow); alias JHS.",
        muestra="JC 0x10", desensamblado="JC L_0010",
    ),
    Instruccion(
        mnemonico="JNC", forma="a", pagina=0xD, bajo=0b0011, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 11 ; byte2 = a",
        banderas="—",
        descripcion="Jump if C=0 (rd < rs, borrow); alias JLO.",
        muestra="JNC 0x10", desensamblado="JNC L_0010",
    ),
    Instruccion(
        mnemonico="JHS", forma="a", pagina=0xD, bajo=0b0010, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 10 ; byte2 = a (alias of JC)",
        banderas="—",
        descripcion="Alias of JC: jumps if rd >= rs (no borrow).",
        muestra="JHS 0x10", desensamblado="JC L_0010", alias_de="JC",
    ),
    Instruccion(
        mnemonico="JLO", forma="a", pagina=0xD, bajo=0b0011, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 11 ; byte2 = a (alias of JNC)",
        banderas="—",
        descripcion="Alias of JNC: jumps if rd < rs (borrow).",
        muestra="JLO 0x10", desensamblado="JNC L_0010", alias_de="JNC",
    ),
    Instruccion(
        mnemonico="JLT", forma="a", pagina=0xD, bajo=0b0100, byte2=0x10,
        regla="(0xD<<4) + (01<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Jump if rd < rs signed (N xor V = 1).",
        muestra="JLT 0x10", desensamblado="JLT L_0010",
    ),
    Instruccion(
        mnemonico="JGE", forma="a", pagina=0xD, bajo=0b0101, byte2=0x10,
        regla="(0xD<<4) + (01<<2) + 01 ; byte2 = a",
        banderas="—",
        descripcion="Jump if rd >= rs signed (N xor V = 0).",
        muestra="JGE 0x10", desensamblado="JGE L_0010",
    ),
    Instruccion(
        mnemonico="JLE", forma="a", pagina=0xD, bajo=0b0110, byte2=0x10,
        regla="(0xD<<4) + (01<<2) + 10 ; byte2 = a",
        banderas="—",
        descripcion="Jump if rd <= rs signed (Z=1 or N xor V=1).",
        muestra="JLE 0x10", desensamblado="JLE L_0010",
    ),
    Instruccion(
        mnemonico="JGT", forma="a", pagina=0xD, bajo=0b0111, byte2=0x10,
        regla="(0xD<<4) + (01<<2) + 11 ; byte2 = a",
        banderas="—",
        descripcion="Jump if rd > rs signed (Z=0 and N xor V=0).",
        muestra="JGT 0x10", desensamblado="JGT L_0010",
    ),
    Instruccion(
        mnemonico="JVS", forma="a", pagina=0xD, bajo=0b1000, byte2=0x10,
        regla="(0xD<<4) + (10<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Jump if V=1.",
        muestra="JVS 0x10", desensamblado="JVS L_0010",
    ),
    Instruccion(
        mnemonico="JVC", forma="a", pagina=0xD, bajo=0b1001, byte2=0x10,
        regla="(0xD<<4) + (10<<2) + 01 ; byte2 = a",
        banderas="—",
        descripcion="Jump if V=0.",
        muestra="JVC 0x10", desensamblado="JVC L_0010",
    ),
    Instruccion(
        mnemonico="JMI", forma="a", pagina=0xD, bajo=0b1010, byte2=0x10,
        regla="(0xD<<4) + (10<<2) + 10 ; byte2 = a",
        banderas="—",
        descripcion="Jump if N=1.",
        muestra="JMI 0x10", desensamblado="JMI L_0010",
    ),
    Instruccion(
        mnemonico="JPL", forma="a", pagina=0xD, bajo=0b1011, byte2=0x10,
        regla="(0xD<<4) + (10<<2) + 11 ; byte2 = a",
        banderas="—",
        descripcion="Jump if N=0.",
        muestra="JPL 0x10", desensamblado="JPL L_0010",
    ),

    # ---- Page 0xE: OUT / IN register form (subtype in rs) -----------------
    Instruccion(
        mnemonico="OUT", forma="rd", pagina=0xE, bajo=0b0000, byte2=None,
        regla="(0xE<<4) + (rd<<2) + 00",
        banderas="—",
        descripcion="Write port 0: port0 <- rd.",
        muestra="OUT A", desensamblado="OUT A",
    ),
    Instruccion(
        mnemonico="IN", forma="rd", pagina=0xE, bajo=0b1101, byte2=None,
        regla="(0xE<<4) + (rd<<2) + 01",
        banderas="—",
        descripcion="Read port 0: rd <- port0.",
        muestra="IN D", desensamblado="IN D",
    ),

    # ---- Page 0xF: system/memory group ------------------------------------
    Instruccion(
        mnemonico="HLT", forma="", pagina=0xF, bajo=0b0000, byte2=None,
        regla="0xF0",
        banderas="—",
        descripcion="Halts the CPU.",
        muestra="HLT", desensamblado="HLT",
    ),
    Instruccion(
        mnemonico="RET", forma="", pagina=0xF, bajo=0b0001, byte2=None,
        regla="0xF1",
        banderas="—",
        descripcion="Return from subroutine: PC <- pop (does not change flags).",
        muestra="RET", desensamblado="RET",
    ),
    Instruccion(
        mnemonico="EI", forma="", pagina=0xF, bajo=0b0010, byte2=None,
        regla="0xF2",
        banderas="I",
        descripcion="Enable interrupts (I <- 1).",
        muestra="EI", desensamblado="EI",
    ),
    Instruccion(
        mnemonico="DI", forma="", pagina=0xF, bajo=0b0011, byte2=None,
        regla="0xF3",
        banderas="I",
        descripcion="Disable interrupts (I <- 0).",
        muestra="DI", desensamblado="DI",
    ),
    Instruccion(
        mnemonico="LD", forma="rd, [rs]", pagina=0xF, bajo=0b0100, byte2=0x06,
        regla="0xF4 ; byte2 = (rd<<2) + rs",
        banderas="—",
        descripcion="Indirect load: rd <- RAM[rs].",
        muestra="LD B, [C]", desensamblado="LD B, [C]",
    ),
    Instruccion(
        mnemonico="ST", forma="rd, [rs]", pagina=0xF, bajo=0b0101, byte2=0x0E,
        regla="0xF5 ; byte2 = (rd<<2) + rs",
        banderas="—",
        descripcion="Indirect store: RAM[rs] <- rd.",
        muestra="ST D, [C]", desensamblado="ST D, [C]",
    ),
    Instruccion(
        mnemonico="MUL", forma="rd, rs", pagina=0xF, bajo=0b0110, byte2=0x01,
        regla="0xF6 ; byte2 = (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="rd <- (rd * rs)[7:0]; C=1 if it does not fit in 8 bits (V=0).",
        muestra="MUL A, B", desensamblado="MUL A, B",
    ),
    Instruccion(
        mnemonico="DIV", forma="rd, rs", pagina=0xF, bajo=0b0111, byte2=0x0E,
        regla="0xF7 ; byte2 = (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="rd <- rd / rs (unsigned integer division); C=1 if rs=0 (V=0).",
        muestra="DIV D, C", desensamblado="DIV D, C",
    ),
    Instruccion(
        mnemonico="OUT", forma="n, rd", pagina=0xF, bajo=0b1000, byte2=0x06,
        regla="0xF8 ; byte2 = (rd<<2) + n",
        banderas="—",
        descripcion="Write port n (0..3): port n <- rd.",
        muestra="OUT 2, B", desensamblado="OUT 2, B",
    ),
    Instruccion(
        mnemonico="IN", forma="n, rd", pagina=0xF, bajo=0b1001, byte2=0x0F,
        regla="0xF9 ; byte2 = (rd<<2) + n",
        banderas="—",
        descripcion="Read port n (0..3): rd <- port n.",
        muestra="IN 3, D", desensamblado="IN 3, D",
    ),

    # ---- Page 0xF, prefix 0xFA: extended instructions (docs/ISA.md §10) -----
    # byte1 = 0xFA ; byte2 = (xop<<4)+(rd<<2)+rs ; LDW/STW add byte3 = off.
    Instruccion(
        mnemonico="NEG", forma="rd", pagina=0xF, bajo=0b1010, byte2=0x00,
        regla="0xFA ; byte2 = (0x0<<4) + (rd<<2)",
        banderas="Z C N V",
        descripcion="Negate rd: rd <- 0 - rd (Z, C, N, V).",
        muestra="NEG A", desensamblado="NEG A",
    ),
    Instruccion(
        mnemonico="NOT", forma="rd", pagina=0xF, bajo=0b1010, byte2=0x18,
        regla="0xFA ; byte2 = (0x1<<4) + (rd<<2)",
        banderas="Z C N V",
        descripcion="Bitwise NOT rd: rd <- ~rd (Z, N; C=0, V=0).",
        muestra="NOT C", desensamblado="NOT C",
    ),
    Instruccion(
        mnemonico="ADC", forma="rd, rs", pagina=0xF, bajo=0b1010, byte2=0x21,
        regla="0xFA ; byte2 = (0x2<<4) + (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="Add with carry: rd <- rd + rs + C (Z, C, N, V).",
        muestra="ADC A, B", desensamblado="ADC A, B",
    ),
    Instruccion(
        mnemonico="SBC", forma="rd, rs", pagina=0xF, bajo=0b1010, byte2=0x36,
        regla="0xFA ; byte2 = (0x3<<4) + (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="Subtract with borrow: rd <- rd - rs - C (Z, C, N, V).",
        muestra="SBC B, C", desensamblado="SBC B, C",
    ),
    Instruccion(
        mnemonico="SWAP", forma="rd, rs", pagina=0xF, bajo=0b1010, byte2=0x42,
        regla="0xFA ; byte2 = (0x4<<4) + (rd<<2) + rs",
        banderas="—",
        descripcion="Exchange two registers: rd <-> rs (does not change flags).",
        muestra="SWAP A, C", desensamblado="SWAP A, C",
    ),
    Instruccion(
        mnemonico="XCHG", forma="rd, rs", pagina=0xF, bajo=0b1010, byte2=0x42,
        regla="0xFA ; byte2 = (0x4<<4) + (rd<<2) + rs (alias of SWAP)",
        banderas="—",
        descripcion="Alias of SWAP: exchange two registers (rd <-> rs).",
        muestra="XCHG A, C", desensamblado="SWAP A, C", alias_de="SWAP",
    ),
    Instruccion(
        mnemonico="ROL", forma="rd", pagina=0xF, bajo=0b1010, byte2=0x5C,
        regla="0xFA ; byte2 = (0x5<<4) + (rd<<2)",
        banderas="Z C N V",
        descripcion="Rotate left through C: rd <- {rd[6:0], C}; C <- rd[7].",
        muestra="ROL D", desensamblado="ROL D",
    ),
    Instruccion(
        mnemonico="ROR", forma="rd", pagina=0xF, bajo=0b1010, byte2=0x60,
        regla="0xFA ; byte2 = (0x6<<4) + (rd<<2)",
        banderas="Z C N V",
        descripcion="Rotate right through C: rd <- {C, rd[7:1]}; C <- rd[0].",
        muestra="ROR A", desensamblado="ROR A",
    ),
    Instruccion(
        mnemonico="LDW", forma="rd, [rs+off]", pagina=0xF, bajo=0b1010,
        byte2=0x71, byte3=0x03,
        regla="0xFA ; byte2 = (0x7<<4) + (rd<<2) + rs ; byte3 = off",
        banderas="C",
        descripcion="Wide indexed load: EA = rs + off (9 bits); rd <- RAM[EA[7:0]]; "
                    "C <- EA[8] (16-bit pointer).",
        muestra="LDW A, [B+3]", desensamblado="LDW A, [B+3]",
    ),
    Instruccion(
        mnemonico="STW", forma="rd, [rs+off]", pagina=0xF, bajo=0b1010,
        byte2=0x8B, byte3=0x04,
        regla="0xFA ; byte2 = (0x8<<4) + (rd<<2) + rs ; byte3 = off",
        banderas="C",
        descripcion="Wide indexed store: EA = rs + off (9 bits); RAM[EA[7:0]] <- rd; "
                    "C <- EA[8] (16-bit pointer).",
        muestra="STW C, [D+4]", desensamblado="STW C, [D+4]",
    ),
)


# Set of covered mnemonics (including aliases), useful for the tests.
MNEMONICOS: Final[frozenset[str]] = frozenset(i.mnemonico for i in INSTRUCCIONES)


def por_pagina() -> dict[int, list[Instruccion]]:
    """Groups instructions by opcode page (for the documentation)."""
    grupos: dict[int, list[Instruccion]] = {p: [] for p in PAGINAS}
    for instr in INSTRUCCIONES:
        grupos[instr.pagina].append(instr)
    return grupos
