# Opcodes de la ISA (cpu8)

> **Fichero generado automáticamente** por `tools/gen_docs.py` a partir de `asm/isa_table.py`,
> la fuente única de verdad machine-readable de la ISA. **No lo edites a mano**:
> regenéralo con `python3 tools/gen_docs.py` y compruébalo con `python3 tools/gen_docs.py --check`.

La codificación del primer byte es `(opcode<<4) + (rd<<2) + rs` (ver `docs/ISA.md` §2).
En *Codificación* se muestran los bytes de una instrucción representativa de cada forma y, a continuación, la regla.
Las banderas que aparecen en la columna *Banderas* son las que la instrucción **modifica**
(`—` = no altera ninguna); ver `docs/ISA.md` §5 para el convenio de C, Z, N, V (y `I`).

## Página `0x0` — Grupo 0x0 — operaciones sobre un registro (INC/DEC/PUSH/POP)

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `INC` | `0x00` — `(0x0<<4) + (00<<2) + rs` | 1 | rd | Z N V | Incrementa rd: rd <- rd + 1 (Z, N, V; no C). |
| `DEC` | `0x05` — `(0x0<<4) + (01<<2) + rs` | 1 | rd | Z N V | Decrementa rd: rd <- rd - 1 (Z, N, V; no C). |
| `PUSH` | `0x0A` — `(0x0<<4) + (10<<2) + rs` | 1 | rd | — | Apila rd: RAM[SP] <- rd; SP <- SP - 1. |
| `POP` | `0x0F` — `(0x0<<4) + (11<<2) + rs` | 1 | rd | — | Desapila: SP <- SP + 1; rd <- RAM[SP]. |

## Página `0x1` — Inmediatos (LDI/ADDI/SUBI/CMPI)

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `LDI` | `0x10 0x05` — `(0x1<<4) + (rd<<2) + 00 ; byte2 = imm` | 2 | rd, imm | — | Carga inmediato: rd <- imm. |
| `ADDI` | `0x15 0x03` — `(0x1<<4) + (rd<<2) + 01 ; byte2 = imm` | 2 | rd, imm | Z C N V | Suma inmediato: rd <- rd + imm (Z, C, N, V). |
| `SUBI` | `0x1A 0x06` — `(0x1<<4) + (rd<<2) + 10 ; byte2 = imm` | 2 | rd, imm | Z C N V | Resta inmediato: rd <- rd - imm (Z, C, N, V). |
| `CMPI` | `0x1F 0x07` — `(0x1<<4) + (rd<<2) + 11 ; byte2 = imm` | 2 | rd, imm | Z C N V | Compara con inmediato: calcula rd - imm (flags), no guarda. |

## Página `0x2` — MOV / NOP

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `MOV` | `0x21` — `(0x2<<4) + (rd<<2) + rs` | 1 | rd, rs | — | Copia registro: rd <- rs. |
| `NOP` (alias de `MOV`) | `0x20` — `0x20 (alias de MOV A, A)` | 1 | — | — | No operación; alias de MOV A,A (0x20). |

## Página `0x3` — LD — carga desde RAM (absoluto/indexado)

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `LD` | `0x30 0x20` — `(0x3<<4) + (rd<<2) + 00 ; byte2 = a` | 2 | rd, [a] | — | Carga absoluta: rd <- RAM[a]. |
| `LD` | `0x3E 0x03` — `(0x3<<4) + (rd<<2) + ss ; byte2 = off (ss=B/C/D)` | 2 | rd, [rs+off] | — | Carga indexada: rd <- RAM[rs+off] (base B/C/D). |

## Página `0x4` — ST — almacena en RAM (absoluto/indexado)

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `ST` | `0x40 0x20` — `(0x4<<4) + (rd<<2) + 00 ; byte2 = a` | 2 | rd, [a] | — | Almacena absoluta: RAM[a] <- rd. |
| `ST` | `0x41 0x03` — `(0x4<<4) + (rd<<2) + ss ; byte2 = off (ss=B/C/D)` | 2 | rd, [rs+off] | — | Almacena indexada: RAM[rs+off] <- rd (base B/C/D). |

## Página `0x5` — ADD

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `ADD` | `0x51` — `(0x5<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd + rs (Z, C, N, V). |

## Página `0x6` — SUB

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `SUB` | `0x61` — `(0x6<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd - rs (Z, C, N, V). |

## Página `0x7` — AND

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `AND` | `0x7B` — `(0x7<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd AND rs (Z, N; C=0, V=0). |

## Página `0x8` — OR

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `OR` | `0x8B` — `(0x8<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd OR rs (Z, N; C=0, V=0). |

## Página `0x9` — XOR

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `XOR` | `0x9B` — `(0x9<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd XOR rs (Z, N; C=0, V=0). |

## Página `0xA` — CMP

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `CMP` | `0xA3` — `(0xA<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | Calcula rd - rs (flags), no guarda (Z, C, N, V). |

## Página `0xB` — SHL / SHR

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `SHL` | `0xB0` — `(0xB<<4) + (rd<<2) + 00` | 1 | rd | Z C N V | Desplaza rd 1 bit a la izquierda (Z, C, N, V). |
| `SHR` | `0xBD` — `(0xB<<4) + (rd<<2) + 01` | 1 | rd | Z C N V | Desplaza rd 1 bit a la derecha (Z, C, N, V). |

## Página `0xC` — JMP / CALL

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `JMP` | `0xC0 0x10` — `(0xC<<4) + 00 ; byte2 = a` | 2 | a | — | Salto incondicional: PC <- a. |
| `CALL` | `0xC1 0x10` — `(0xC<<4) + 01 ; byte2 = a` | 2 | a | — | Llama subrutina: push(PC); PC <- a (no altera flags). |

## Página `0xD` — Saltos condicionales (Jcc)

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `JZ` | `0xD0 0x10` — `(0xD<<4) + (00<<2) + 00 ; byte2 = a` | 2 | a | — | Salta si Z=1 (rd == rs). |
| `JNZ` | `0xD1 0x10` — `(0xD<<4) + (00<<2) + 01 ; byte2 = a` | 2 | a | — | Salta si Z=0 (rd != rs). |
| `JC` | `0xD2 0x10` — `(0xD<<4) + (00<<2) + 10 ; byte2 = a` | 2 | a | — | Salta si C=1 (rd >= rs, sin borrow); alias JHS. |
| `JNC` | `0xD3 0x10` — `(0xD<<4) + (00<<2) + 11 ; byte2 = a` | 2 | a | — | Salta si C=0 (rd < rs, con borrow); alias JLO. |
| `JHS` (alias de `JC`) | `0xD2 0x10` — `(0xD<<4) + (00<<2) + 10 ; byte2 = a (alias de JC)` | 2 | a | — | Alias de JC: salta si rd >= rs (no hubo borrow). |
| `JLO` (alias de `JNC`) | `0xD3 0x10` — `(0xD<<4) + (00<<2) + 11 ; byte2 = a (alias de JNC)` | 2 | a | — | Alias de JNC: salta si rd < rs (hubo borrow). |
| `JLT` | `0xD4 0x10` — `(0xD<<4) + (01<<2) + 00 ; byte2 = a` | 2 | a | — | Salta si rd < rs con signo (N xor V = 1). |
| `JGE` | `0xD5 0x10` — `(0xD<<4) + (01<<2) + 01 ; byte2 = a` | 2 | a | — | Salta si rd >= rs con signo (N xor V = 0). |
| `JLE` | `0xD6 0x10` — `(0xD<<4) + (01<<2) + 10 ; byte2 = a` | 2 | a | — | Salta si rd <= rs con signo (Z=1 o N xor V=1). |
| `JGT` | `0xD7 0x10` — `(0xD<<4) + (01<<2) + 11 ; byte2 = a` | 2 | a | — | Salta si rd > rs con signo (Z=0 y N xor V=0). |
| `JVS` | `0xD8 0x10` — `(0xD<<4) + (10<<2) + 00 ; byte2 = a` | 2 | a | — | Salta si V=1. |
| `JVC` | `0xD9 0x10` — `(0xD<<4) + (10<<2) + 01 ; byte2 = a` | 2 | a | — | Salta si V=0. |
| `JMI` | `0xDA 0x10` — `(0xD<<4) + (10<<2) + 10 ; byte2 = a` | 2 | a | — | Salta si N=1. |
| `JPL` | `0xDB 0x10` — `(0xD<<4) + (10<<2) + 11 ; byte2 = a` | 2 | a | — | Salta si N=0. |

## Página `0xE` — OUT / IN — puerto 0 (forma de registro)

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `OUT` | `0xE0` — `(0xE<<4) + (rd<<2) + 00` | 1 | rd | — | Escribe el puerto 0: puerto0 <- rd. |
| `IN` | `0xED` — `(0xE<<4) + (rd<<2) + 01` | 1 | rd | — | Lee el puerto 0: rd <- puerto0. |

## Página `0xF` — Grupo sistema/memoria (HLT, RET, EI, DI, indirecto, MUL/DIV, E/S portada)

| Mnemónico | Codificación (hex) | Bytes | Operandos | Banderas | Descripción |
|-----------|--------------------|-------|-----------|----------|-------------|
| `HLT` | `0xF0` — `0xF0` | 1 | — | — | Detiene la CPU. |
| `RET` | `0xF1` — `0xF1` | 1 | — | — | Retorno de subrutina: PC <- pop (no altera flags). |
| `EI` | `0xF2` — `0xF2` | 1 | — | I | Habilita interrupciones (I <- 1). |
| `DI` | `0xF3` — `0xF3` | 1 | — | I | Deshabilita interrupciones (I <- 0). |
| `LD` | `0xF4 0x06` — `0xF4 ; byte2 = (rd<<2) + rs` | 2 | rd, [rs] | — | Carga indirecta: rd <- RAM[rs]. |
| `ST` | `0xF5 0x0E` — `0xF5 ; byte2 = (rd<<2) + rs` | 2 | rd, [rs] | — | Almacena indirecta: RAM[rs] <- rd. |
| `MUL` | `0xF6 0x01` — `0xF6 ; byte2 = (rd<<2) + rs` | 2 | rd, rs | Z C N V | rd <- (rd * rs)[7:0]; C=1 si no cabe en 8 bits (V=0). |
| `DIV` | `0xF7 0x0E` — `0xF7 ; byte2 = (rd<<2) + rs` | 2 | rd, rs | Z C N V | rd <- rd / rs (entero sin signo); C=1 si rs=0 (V=0). |
| `OUT` | `0xF8 0x06` — `0xF8 ; byte2 = (rd<<2) + n` | 2 | n, rd | — | Escribe el puerto n (0..3): puerto n <- rd. |
| `IN` | `0xF9 0x0F` — `0xF9 ; byte2 = (rd<<2) + n` | 2 | n, rd | — | Lee el puerto n (0..3): rd <- puerto n. |
