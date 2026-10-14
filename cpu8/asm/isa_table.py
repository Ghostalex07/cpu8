#!/usr/bin/env python3
"""Fuente única de verdad (machine-readable) de la ISA de la CPU cpu8.

Este módulo describe, con una entrada por instrucción y forma de operandos,
TODO el juego de instrucciones de la CPU: mnemónico, forma, página de opcode,
longitud en bytes, la regla exacta de codificación (página + campos ``rd``/``rs``
y, si procede, el segundo byte), las banderas afectadas y una descripción breve
en español.

**Es la REFERENCIA.** ``tools/gen_docs.py`` genera ``docs/OPCODES.md`` a partir
de aquí y ``asm/test_isa_table.py`` garantiza que la tabla **no deriva**:

* ensambla una instrucción representativa de cada entrada con
  ``asm/assembler.py`` y comprueba que los bytes coinciden con los que declara
  la tabla;
* desensambla esos bytes con ``tools/disasm.py`` y comprueba el texto esperado;
* comprueba que el conjunto de mnemónicos de la tabla es exactamente
  ``assembler.MNEMONICOS``.

Si se cambia el codificador o el decodificador sin actualizar esta tabla (o al
revés), los tests fallan. Los valores siguen ``docs/ISA.md`` (fuente de verdad
en prosa) y el RTL (``rtl/alu.v``, ``rtl/control.v``, ``rtl/cpu.v``).

Convenio de banderas (``docs/ISA.md`` §5 y ``rtl/cpu.v``): ``flags_we``
actualiza Z, N y V; ``flags_c_we`` actualiza además C. Por eso INC/DEC tocan
``Z N V`` (no C) y la aritmética/lógica toca ``Z C N V``. ``EI``/``DI`` solo
tocan el flag ``I``. El resto no modifica banderas.

La codificación general del primer byte es ``(opcode<<4) | (rd<<2) | rs``
(``docs/ISA.md`` §2). En los campos:

* ``pagina``: nibble de opcode ``[7:4]`` (0x0..0xF);
* ``bajo``: nibble bajo de la página de 4 bits (``rd``/``rs``/subcódigo);
* ``byte2``: segundo byte (inmediato/dirección/índices) o ``None`` si es 1 byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Instruccion:
    """Una instrucción/mnemónico de la ISA y su forma de operandos.

    ``bytes_codificados()`` reconstruye los bytes a partir de ``pagina``,
    ``bajo`` y ``byte2`` (la regla declarativa); los tests contrastan esos bytes
    con lo que produce ``assembler.ensamblar`` para ``muestra``.
    """

    mnemonico: str          # p. ej. "ADD"
    forma: str              # forma de operandos, p. ej. "rd, rs"
    pagina: int             # nibble de opcode [7:4] (0x0..0xF)
    bajo: int               # nibble bajo del 1er byte (rd/rs/subcódigo)
    byte2: int | None       # 2o byte exacto, o None si la instrucción es de 1 byte
    regla: str              # regla legible de la codificación (para la doc)
    banderas: str           # banderas que modifica, p. ej. "Z C N V" o "—"
    descripcion: str        # descripción breve en español
    muestra: str            # fuente de ejemplo (una línea) que ensambla esta forma
    desensamblado: str      # texto exacto que produce tools/disasm.decodificar
    alias_de: str | None = None  # mnemónico canónico si es un alias

    @property
    def longitud(self) -> int:
        """Bytes que ocupa la instrucción (1 o 2)."""
        return 2 if self.byte2 is not None else 1

    def bytes_codificados(self) -> tuple[int, ...]:
        """Bytes exactos según la regla declarada en la tabla."""
        b1 = (self.pagina << 4) | self.bajo
        if self.byte2 is None:
            return (b1,)
        return (b1, self.byte2)

    @property
    def byte1(self) -> int:
        """Primer byte (para agrupar por página en la documentación)."""
        return (self.pagina << 4) | self.bajo


# --- Nombres de las páginas de opcode (para docs/OPCODES.md) -----------------
PAGINAS: Final[dict[int, str]] = {
    0x0: "Grupo 0x0 — operaciones sobre un registro (INC/DEC/PUSH/POP)",
    0x1: "Inmediatos (LDI/ADDI/SUBI/CMPI)",
    0x2: "MOV / NOP",
    0x3: "LD — carga desde RAM (absoluto/indexado)",
    0x4: "ST — almacena en RAM (absoluto/indexado)",
    0x5: "ADD",
    0x6: "SUB",
    0x7: "AND",
    0x8: "OR",
    0x9: "XOR",
    0xA: "CMP",
    0xB: "SHL / SHR",
    0xC: "JMP / CALL",
    0xD: "Saltos condicionales (Jcc)",
    0xE: "OUT / IN — puerto 0 (forma de registro)",
    0xF: "Grupo sistema/memoria (HLT, RET, EI, DI, indirecto, MUL/DIV, E/S portada)",
}


# ============================================================================
#  Tabla de la ISA (una entrada por instrucción / forma de operandos)
# ============================================================================
#  Cubre las 16 páginas de opcode (0x0..0xF).  Los bytes de la entrada son los
#  de `muestra`, que es una instrucción válida y representativa de esa forma.
INSTRUCCIONES: Final[tuple[Instruccion, ...]] = (
    # ---- Página 0x0: INC/DEC/PUSH/POP (subop en rd, registro en rs) --------
    Instruccion(
        mnemonico="INC", forma="rd", pagina=0x0, bajo=0b0000, byte2=None,
        regla="(0x0<<4) + (00<<2) + rs",
        banderas="Z N V",
        descripcion="Incrementa rd: rd <- rd + 1 (Z, N, V; no C).",
        muestra="INC A", desensamblado="INC A",
    ),
    Instruccion(
        mnemonico="DEC", forma="rd", pagina=0x0, bajo=0b0101, byte2=None,
        regla="(0x0<<4) + (01<<2) + rs",
        banderas="Z N V",
        descripcion="Decrementa rd: rd <- rd - 1 (Z, N, V; no C).",
        muestra="DEC B", desensamblado="DEC B",
    ),
    Instruccion(
        mnemonico="PUSH", forma="rd", pagina=0x0, bajo=0b1010, byte2=None,
        regla="(0x0<<4) + (10<<2) + rs",
        banderas="—",
        descripcion="Apila rd: RAM[SP] <- rd; SP <- SP - 1.",
        muestra="PUSH C", desensamblado="PUSH C",
    ),
    Instruccion(
        mnemonico="POP", forma="rd", pagina=0x0, bajo=0b1111, byte2=None,
        regla="(0x0<<4) + (11<<2) + rs",
        banderas="—",
        descripcion="Desapila: SP <- SP + 1; rd <- RAM[SP].",
        muestra="POP D", desensamblado="POP D",
    ),

    # ---- Página 0x1: inmediatos (suboperación en rs) ----------------------
    Instruccion(
        mnemonico="LDI", forma="rd, imm", pagina=0x1, bajo=0b0000, byte2=0x05,
        regla="(0x1<<4) + (rd<<2) + 00 ; byte2 = imm",
        banderas="—",
        descripcion="Carga inmediato: rd <- imm.",
        muestra="LDI A, 0x05", desensamblado="LDI A, 0x05",
    ),
    Instruccion(
        mnemonico="ADDI", forma="rd, imm", pagina=0x1, bajo=0b0101, byte2=0x03,
        regla="(0x1<<4) + (rd<<2) + 01 ; byte2 = imm",
        banderas="Z C N V",
        descripcion="Suma inmediato: rd <- rd + imm (Z, C, N, V).",
        muestra="ADDI B, 0x03", desensamblado="ADDI B, 0x03",
    ),
    Instruccion(
        mnemonico="SUBI", forma="rd, imm", pagina=0x1, bajo=0b1010, byte2=0x06,
        regla="(0x1<<4) + (rd<<2) + 10 ; byte2 = imm",
        banderas="Z C N V",
        descripcion="Resta inmediato: rd <- rd - imm (Z, C, N, V).",
        muestra="SUBI C, 0x06", desensamblado="SUBI C, 0x06",
    ),
    Instruccion(
        mnemonico="CMPI", forma="rd, imm", pagina=0x1, bajo=0b1111, byte2=0x07,
        regla="(0x1<<4) + (rd<<2) + 11 ; byte2 = imm",
        banderas="Z C N V",
        descripcion="Compara con inmediato: calcula rd - imm (flags), no guarda.",
        muestra="CMPI D, 0x07", desensamblado="CMPI D, 0x07",
    ),

    # ---- Página 0x2: MOV / NOP --------------------------------------------
    Instruccion(
        mnemonico="MOV", forma="rd, rs", pagina=0x2, bajo=0b0001, byte2=None,
        regla="(0x2<<4) + (rd<<2) + rs",
        banderas="—",
        descripcion="Copia registro: rd <- rs.",
        muestra="MOV A, B", desensamblado="MOV A, B",
    ),
    Instruccion(
        mnemonico="NOP", forma="", pagina=0x2, bajo=0b0000, byte2=None,
        regla="0x20 (alias de MOV A, A)",
        banderas="—",
        descripcion="No operación; alias de MOV A,A (0x20).",
        muestra="NOP", desensamblado="MOV A, A", alias_de="MOV",
    ),

    # ---- Página 0x3: LD (absoluto / indexado) -----------------------------
    Instruccion(
        mnemonico="LD", forma="rd, [a]", pagina=0x3, bajo=0b0000, byte2=0x20,
        regla="(0x3<<4) + (rd<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Carga absoluta: rd <- RAM[a].",
        muestra="LD A, [0x20]", desensamblado="LD A, [0x20]",
    ),
    Instruccion(
        mnemonico="LD", forma="rd, [rs+off]", pagina=0x3, bajo=0b1110, byte2=0x03,
        regla="(0x3<<4) + (rd<<2) + ss ; byte2 = off (ss=B/C/D)",
        banderas="—",
        descripcion="Carga indexada: rd <- RAM[rs+off] (base B/C/D).",
        muestra="LD D, [C+3]", desensamblado="LD D, [C+3]",
    ),

    # ---- Página 0x4: ST (absoluto / indexado) -----------------------------
    Instruccion(
        mnemonico="ST", forma="rd, [a]", pagina=0x4, bajo=0b0000, byte2=0x20,
        regla="(0x4<<4) + (rd<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Almacena absoluta: RAM[a] <- rd.",
        muestra="ST A, [0x20]", desensamblado="ST A, [0x20]",
    ),
    Instruccion(
        mnemonico="ST", forma="rd, [rs+off]", pagina=0x4, bajo=0b0001, byte2=0x03,
        regla="(0x4<<4) + (rd<<2) + ss ; byte2 = off (ss=B/C/D)",
        banderas="—",
        descripcion="Almacena indexada: RAM[rs+off] <- rd (base B/C/D).",
        muestra="ST A, [B+3]", desensamblado="ST A, [B+3]",
    ),

    # ---- Páginas 0x5..0xA: ALU rd,rs --------------------------------------
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
        descripcion="Calcula rd - rs (flags), no guarda (Z, C, N, V).",
        muestra="CMP A, D", desensamblado="CMP A, D",
    ),

    # ---- Página 0xB: SHL / SHR (suboperación en rs) -----------------------
    Instruccion(
        mnemonico="SHL", forma="rd", pagina=0xB, bajo=0b0000, byte2=None,
        regla="(0xB<<4) + (rd<<2) + 00",
        banderas="Z C N V",
        descripcion="Desplaza rd 1 bit a la izquierda (Z, C, N, V).",
        muestra="SHL A", desensamblado="SHL A",
    ),
    Instruccion(
        mnemonico="SHR", forma="rd", pagina=0xB, bajo=0b1101, byte2=None,
        regla="(0xB<<4) + (rd<<2) + 01",
        banderas="Z C N V",
        descripcion="Desplaza rd 1 bit a la derecha (Z, C, N, V).",
        muestra="SHR D", desensamblado="SHR D",
    ),

    # ---- Página 0xC: JMP / CALL (subtipo en rs) ---------------------------
    Instruccion(
        mnemonico="JMP", forma="a", pagina=0xC, bajo=0b0000, byte2=0x10,
        regla="(0xC<<4) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Salto incondicional: PC <- a.",
        muestra="JMP 0x10", desensamblado="JMP L_0010",
    ),
    Instruccion(
        mnemonico="CALL", forma="a", pagina=0xC, bajo=0b0001, byte2=0x10,
        regla="(0xC<<4) + 01 ; byte2 = a",
        banderas="—",
        descripcion="Llama subrutina: push(PC); PC <- a (no altera flags).",
        muestra="CALL 0x10", desensamblado="CALL L_0010",
    ),

    # ---- Página 0xD: Jcc (familia en rd, condición en rs) -----------------
    Instruccion(
        mnemonico="JZ", forma="a", pagina=0xD, bajo=0b0000, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Salta si Z=1 (rd == rs).",
        muestra="JZ 0x10", desensamblado="JZ L_0010",
    ),
    Instruccion(
        mnemonico="JNZ", forma="a", pagina=0xD, bajo=0b0001, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 01 ; byte2 = a",
        banderas="—",
        descripcion="Salta si Z=0 (rd != rs).",
        muestra="JNZ 0x10", desensamblado="JNZ L_0010",
    ),
    Instruccion(
        mnemonico="JC", forma="a", pagina=0xD, bajo=0b0010, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 10 ; byte2 = a",
        banderas="—",
        descripcion="Salta si C=1 (rd >= rs, sin borrow); alias JHS.",
        muestra="JC 0x10", desensamblado="JC L_0010",
    ),
    Instruccion(
        mnemonico="JNC", forma="a", pagina=0xD, bajo=0b0011, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 11 ; byte2 = a",
        banderas="—",
        descripcion="Salta si C=0 (rd < rs, con borrow); alias JLO.",
        muestra="JNC 0x10", desensamblado="JNC L_0010",
    ),
    Instruccion(
        mnemonico="JHS", forma="a", pagina=0xD, bajo=0b0010, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 10 ; byte2 = a (alias de JC)",
        banderas="—",
        descripcion="Alias de JC: salta si rd >= rs (no hubo borrow).",
        muestra="JHS 0x10", desensamblado="JC L_0010", alias_de="JC",
    ),
    Instruccion(
        mnemonico="JLO", forma="a", pagina=0xD, bajo=0b0011, byte2=0x10,
        regla="(0xD<<4) + (00<<2) + 11 ; byte2 = a (alias de JNC)",
        banderas="—",
        descripcion="Alias de JNC: salta si rd < rs (hubo borrow).",
        muestra="JLO 0x10", desensamblado="JNC L_0010", alias_de="JNC",
    ),
    Instruccion(
        mnemonico="JLT", forma="a", pagina=0xD, bajo=0b0100, byte2=0x10,
        regla="(0xD<<4) + (01<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Salta si rd < rs con signo (N xor V = 1).",
        muestra="JLT 0x10", desensamblado="JLT L_0010",
    ),
    Instruccion(
        mnemonico="JGE", forma="a", pagina=0xD, bajo=0b0101, byte2=0x10,
        regla="(0xD<<4) + (01<<2) + 01 ; byte2 = a",
        banderas="—",
        descripcion="Salta si rd >= rs con signo (N xor V = 0).",
        muestra="JGE 0x10", desensamblado="JGE L_0010",
    ),
    Instruccion(
        mnemonico="JLE", forma="a", pagina=0xD, bajo=0b0110, byte2=0x10,
        regla="(0xD<<4) + (01<<2) + 10 ; byte2 = a",
        banderas="—",
        descripcion="Salta si rd <= rs con signo (Z=1 o N xor V=1).",
        muestra="JLE 0x10", desensamblado="JLE L_0010",
    ),
    Instruccion(
        mnemonico="JGT", forma="a", pagina=0xD, bajo=0b0111, byte2=0x10,
        regla="(0xD<<4) + (01<<2) + 11 ; byte2 = a",
        banderas="—",
        descripcion="Salta si rd > rs con signo (Z=0 y N xor V=0).",
        muestra="JGT 0x10", desensamblado="JGT L_0010",
    ),
    Instruccion(
        mnemonico="JVS", forma="a", pagina=0xD, bajo=0b1000, byte2=0x10,
        regla="(0xD<<4) + (10<<2) + 00 ; byte2 = a",
        banderas="—",
        descripcion="Salta si V=1.",
        muestra="JVS 0x10", desensamblado="JVS L_0010",
    ),
    Instruccion(
        mnemonico="JVC", forma="a", pagina=0xD, bajo=0b1001, byte2=0x10,
        regla="(0xD<<4) + (10<<2) + 01 ; byte2 = a",
        banderas="—",
        descripcion="Salta si V=0.",
        muestra="JVC 0x10", desensamblado="JVC L_0010",
    ),
    Instruccion(
        mnemonico="JMI", forma="a", pagina=0xD, bajo=0b1010, byte2=0x10,
        regla="(0xD<<4) + (10<<2) + 10 ; byte2 = a",
        banderas="—",
        descripcion="Salta si N=1.",
        muestra="JMI 0x10", desensamblado="JMI L_0010",
    ),
    Instruccion(
        mnemonico="JPL", forma="a", pagina=0xD, bajo=0b1011, byte2=0x10,
        regla="(0xD<<4) + (10<<2) + 11 ; byte2 = a",
        banderas="—",
        descripcion="Salta si N=0.",
        muestra="JPL 0x10", desensamblado="JPL L_0010",
    ),

    # ---- Página 0xE: OUT / IN forma de registro (subtipo en rs) -----------
    Instruccion(
        mnemonico="OUT", forma="rd", pagina=0xE, bajo=0b0000, byte2=None,
        regla="(0xE<<4) + (rd<<2) + 00",
        banderas="—",
        descripcion="Escribe el puerto 0: puerto0 <- rd.",
        muestra="OUT A", desensamblado="OUT A",
    ),
    Instruccion(
        mnemonico="IN", forma="rd", pagina=0xE, bajo=0b1101, byte2=None,
        regla="(0xE<<4) + (rd<<2) + 01",
        banderas="—",
        descripcion="Lee el puerto 0: rd <- puerto0.",
        muestra="IN D", desensamblado="IN D",
    ),

    # ---- Página 0xF: grupo sistema/memoria --------------------------------
    Instruccion(
        mnemonico="HLT", forma="", pagina=0xF, bajo=0b0000, byte2=None,
        regla="0xF0",
        banderas="—",
        descripcion="Detiene la CPU.",
        muestra="HLT", desensamblado="HLT",
    ),
    Instruccion(
        mnemonico="RET", forma="", pagina=0xF, bajo=0b0001, byte2=None,
        regla="0xF1",
        banderas="—",
        descripcion="Retorno de subrutina: PC <- pop (no altera flags).",
        muestra="RET", desensamblado="RET",
    ),
    Instruccion(
        mnemonico="EI", forma="", pagina=0xF, bajo=0b0010, byte2=None,
        regla="0xF2",
        banderas="I",
        descripcion="Habilita interrupciones (I <- 1).",
        muestra="EI", desensamblado="EI",
    ),
    Instruccion(
        mnemonico="DI", forma="", pagina=0xF, bajo=0b0011, byte2=None,
        regla="0xF3",
        banderas="I",
        descripcion="Deshabilita interrupciones (I <- 0).",
        muestra="DI", desensamblado="DI",
    ),
    Instruccion(
        mnemonico="LD", forma="rd, [rs]", pagina=0xF, bajo=0b0100, byte2=0x06,
        regla="0xF4 ; byte2 = (rd<<2) + rs",
        banderas="—",
        descripcion="Carga indirecta: rd <- RAM[rs].",
        muestra="LD B, [C]", desensamblado="LD B, [C]",
    ),
    Instruccion(
        mnemonico="ST", forma="rd, [rs]", pagina=0xF, bajo=0b0101, byte2=0x0E,
        regla="0xF5 ; byte2 = (rd<<2) + rs",
        banderas="—",
        descripcion="Almacena indirecta: RAM[rs] <- rd.",
        muestra="ST D, [C]", desensamblado="ST D, [C]",
    ),
    Instruccion(
        mnemonico="MUL", forma="rd, rs", pagina=0xF, bajo=0b0110, byte2=0x01,
        regla="0xF6 ; byte2 = (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="rd <- (rd * rs)[7:0]; C=1 si no cabe en 8 bits (V=0).",
        muestra="MUL A, B", desensamblado="MUL A, B",
    ),
    Instruccion(
        mnemonico="DIV", forma="rd, rs", pagina=0xF, bajo=0b0111, byte2=0x0E,
        regla="0xF7 ; byte2 = (rd<<2) + rs",
        banderas="Z C N V",
        descripcion="rd <- rd / rs (entero sin signo); C=1 si rs=0 (V=0).",
        muestra="DIV D, C", desensamblado="DIV D, C",
    ),
    Instruccion(
        mnemonico="OUT", forma="n, rd", pagina=0xF, bajo=0b1000, byte2=0x06,
        regla="0xF8 ; byte2 = (rd<<2) + n",
        banderas="—",
        descripcion="Escribe el puerto n (0..3): puerto n <- rd.",
        muestra="OUT 2, B", desensamblado="OUT 2, B",
    ),
    Instruccion(
        mnemonico="IN", forma="n, rd", pagina=0xF, bajo=0b1001, byte2=0x0F,
        regla="0xF9 ; byte2 = (rd<<2) + n",
        banderas="—",
        descripcion="Lee el puerto n (0..3): rd <- puerto n.",
        muestra="IN 3, D", desensamblado="IN 3, D",
    ),
)


# Conjunto de mnemónicos cubiertos (incluye alias), útil para los tests.
MNEMONICOS: Final[frozenset[str]] = frozenset(i.mnemonico for i in INSTRUCCIONES)


def por_pagina() -> dict[int, list[Instruccion]]:
    """Agrupa las instrucciones por página de opcode (para la documentación)."""
    grupos: dict[int, list[Instruccion]] = {p: [] for p in PAGINAS}
    for instr in INSTRUCCIONES:
        grupos[instr.pagina].append(instr)
    return grupos
