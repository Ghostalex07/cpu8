# ISA Opcodes (cpu8)

> **Automatically generated file** by `tools/gen_docs.py` from `asm/isa_table.py`,
> the single machine-readable source of truth for the ISA. **Do not edit it by hand**:
> regenerate it with `python3 tools/gen_docs.py` and check it with `python3 tools/gen_docs.py --check`.

The encoding of the first byte is `(opcode<<4) + (rd<<2) + rs` (see `docs/ISA.md` §2).
Under *Encoding* the bytes of a representative instruction of each form are shown and, next, the rule.
The flags appearing in the *Flags* column are those that the instruction **modifies**
(`—` = does not change any); see `docs/ISA.md` §5 for the convention of C, Z, N, V (and `I`).

## Page `0x0` — Group 0x0 — single-register operations (INC/DEC/PUSH/POP)

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `INC` | `0x00` — `(0x0<<4) + (00<<2) + rs` | 1 | rd | Z N V | Increment rd: rd <- rd + 1 (Z, N, V; not C). |
| `DEC` | `0x05` — `(0x0<<4) + (01<<2) + rs` | 1 | rd | Z N V | Decrement rd: rd <- rd - 1 (Z, N, V; not C). |
| `PUSH` | `0x0A` — `(0x0<<4) + (10<<2) + rs` | 1 | rd | — | Push rd: RAM[SP] <- rd; SP <- SP - 1. |
| `POP` | `0x0F` — `(0x0<<4) + (11<<2) + rs` | 1 | rd | — | Pop: SP <- SP + 1; rd <- RAM[SP]. |

## Page `0x1` — Immediates (LDI/ADDI/SUBI/CMPI)

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `LDI` | `0x10 0x05` — `(0x1<<4) + (rd<<2) + 00 ; byte2 = imm` | 2 | rd, imm | — | Load immediate: rd <- imm. |
| `ADDI` | `0x15 0x03` — `(0x1<<4) + (rd<<2) + 01 ; byte2 = imm` | 2 | rd, imm | Z C N V | Add immediate: rd <- rd + imm (Z, C, N, V). |
| `SUBI` | `0x1A 0x06` — `(0x1<<4) + (rd<<2) + 10 ; byte2 = imm` | 2 | rd, imm | Z C N V | Subtract immediate: rd <- rd - imm (Z, C, N, V). |
| `CMPI` | `0x1F 0x07` — `(0x1<<4) + (rd<<2) + 11 ; byte2 = imm` | 2 | rd, imm | Z C N V | Compare with immediate: computes rd - imm (flags), does not store. |

## Page `0x2` — MOV / NOP

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `MOV` | `0x21` — `(0x2<<4) + (rd<<2) + rs` | 1 | rd, rs | — | Copy register: rd <- rs. |
| `NOP` (alias of `MOV`) | `0x20` — `0x20 (alias of MOV A, A)` | 1 | — | — | No operation; alias of MOV A,A (0x20). |

## Page `0x3` — LD — load from RAM (absolute/indexed)

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `LD` | `0x30 0x20` — `(0x3<<4) + (rd<<2) + 00 ; byte2 = a` | 2 | rd, [a] | — | Absolute load: rd <- RAM[a]. |
| `LD` | `0x3E 0x03` — `(0x3<<4) + (rd<<2) + ss ; byte2 = off (ss=B/C/D)` | 2 | rd, [rs+off] | — | Indexed load: rd <- RAM[rs+off] (base B/C/D). |

## Page `0x4` — ST — store to RAM (absolute/indexed)

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `ST` | `0x40 0x20` — `(0x4<<4) + (rd<<2) + 00 ; byte2 = a` | 2 | rd, [a] | — | Absolute store: RAM[a] <- rd. |
| `ST` | `0x41 0x03` — `(0x4<<4) + (rd<<2) + ss ; byte2 = off (ss=B/C/D)` | 2 | rd, [rs+off] | — | Indexed store: RAM[rs+off] <- rd (base B/C/D). |

## Page `0x5` — ADD

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `ADD` | `0x51` — `(0x5<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd + rs (Z, C, N, V). |

## Page `0x6` — SUB

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `SUB` | `0x61` — `(0x6<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd - rs (Z, C, N, V). |

## Page `0x7` — AND

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `AND` | `0x7B` — `(0x7<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd AND rs (Z, N; C=0, V=0). |

## Page `0x8` — OR

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `OR` | `0x8B` — `(0x8<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd OR rs (Z, N; C=0, V=0). |

## Page `0x9` — XOR

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `XOR` | `0x9B` — `(0x9<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | rd <- rd XOR rs (Z, N; C=0, V=0). |

## Page `0xA` — CMP

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `CMP` | `0xA3` — `(0xA<<4) + (rd<<2) + rs` | 1 | rd, rs | Z C N V | Computes rd - rs (flags), does not store (Z, C, N, V). |

## Page `0xB` — SHL / SHR

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `SHL` | `0xB0` — `(0xB<<4) + (rd<<2) + 00` | 1 | rd | Z C N V | Shift rd 1 bit left (Z, C, N, V). |
| `SHR` | `0xBD` — `(0xB<<4) + (rd<<2) + 01` | 1 | rd | Z C N V | Shift rd 1 bit right (Z, C, N, V). |

## Page `0xC` — JMP / CALL

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `JMP` | `0xC0 0x10` — `(0xC<<4) + 00 ; byte2 = a` | 2 | a | — | Unconditional jump: PC <- a. |
| `CALL` | `0xC1 0x10` — `(0xC<<4) + 01 ; byte2 = a` | 2 | a | — | Call subroutine: push(PC); PC <- a (does not change flags). |

## Page `0xD` — Conditional jumps (Jcc)

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `JZ` | `0xD0 0x10` — `(0xD<<4) + (00<<2) + 00 ; byte2 = a` | 2 | a | — | Jump if Z=1 (rd == rs). |
| `JNZ` | `0xD1 0x10` — `(0xD<<4) + (00<<2) + 01 ; byte2 = a` | 2 | a | — | Jump if Z=0 (rd != rs). |
| `JC` | `0xD2 0x10` — `(0xD<<4) + (00<<2) + 10 ; byte2 = a` | 2 | a | — | Jump if C=1 (rd >= rs, no borrow); alias JHS. |
| `JNC` | `0xD3 0x10` — `(0xD<<4) + (00<<2) + 11 ; byte2 = a` | 2 | a | — | Jump if C=0 (rd < rs, borrow); alias JLO. |
| `JHS` (alias of `JC`) | `0xD2 0x10` — `(0xD<<4) + (00<<2) + 10 ; byte2 = a (alias of JC)` | 2 | a | — | Alias of JC: jumps if rd >= rs (no borrow). |
| `JLO` (alias of `JNC`) | `0xD3 0x10` — `(0xD<<4) + (00<<2) + 11 ; byte2 = a (alias of JNC)` | 2 | a | — | Alias of JNC: jumps if rd < rs (borrow). |
| `JLT` | `0xD4 0x10` — `(0xD<<4) + (01<<2) + 00 ; byte2 = a` | 2 | a | — | Jump if rd < rs signed (N xor V = 1). |
| `JGE` | `0xD5 0x10` — `(0xD<<4) + (01<<2) + 01 ; byte2 = a` | 2 | a | — | Jump if rd >= rs signed (N xor V = 0). |
| `JLE` | `0xD6 0x10` — `(0xD<<4) + (01<<2) + 10 ; byte2 = a` | 2 | a | — | Jump if rd <= rs signed (Z=1 or N xor V=1). |
| `JGT` | `0xD7 0x10` — `(0xD<<4) + (01<<2) + 11 ; byte2 = a` | 2 | a | — | Jump if rd > rs signed (Z=0 and N xor V=0). |
| `JVS` | `0xD8 0x10` — `(0xD<<4) + (10<<2) + 00 ; byte2 = a` | 2 | a | — | Jump if V=1. |
| `JVC` | `0xD9 0x10` — `(0xD<<4) + (10<<2) + 01 ; byte2 = a` | 2 | a | — | Jump if V=0. |
| `JMI` | `0xDA 0x10` — `(0xD<<4) + (10<<2) + 10 ; byte2 = a` | 2 | a | — | Jump if N=1. |
| `JPL` | `0xDB 0x10` — `(0xD<<4) + (10<<2) + 11 ; byte2 = a` | 2 | a | — | Jump if N=0. |

## Page `0xE` — OUT / IN — port 0 (register form)

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `OUT` | `0xE0` — `(0xE<<4) + (rd<<2) + 00` | 1 | rd | — | Write port 0: port0 <- rd. |
| `IN` | `0xED` — `(0xE<<4) + (rd<<2) + 01` | 1 | rd | — | Read port 0: rd <- port0. |

## Page `0xF` — System/memory group (HLT, RET, EI, DI, indirect, MUL/DIV, ported I/O, 0xFA prefix)

| Mnemonic | Encoding (hex) | Bytes | Operands | Flags | Description |
|----------|----------------|-------|----------|-------|-------------|
| `HLT` | `0xF0` — `0xF0` | 1 | — | — | Halts the CPU. |
| `RET` | `0xF1` — `0xF1` | 1 | — | — | Return from subroutine: PC <- pop (does not change flags). |
| `EI` | `0xF2` — `0xF2` | 1 | — | I | Enable interrupts (I <- 1). |
| `DI` | `0xF3` — `0xF3` | 1 | — | I | Disable interrupts (I <- 0). |
| `LD` | `0xF4 0x06` — `0xF4 ; byte2 = (rd<<2) + rs` | 2 | rd, [rs] | — | Indirect load: rd <- RAM[rs]. |
| `ST` | `0xF5 0x0E` — `0xF5 ; byte2 = (rd<<2) + rs` | 2 | rd, [rs] | — | Indirect store: RAM[rs] <- rd. |
| `MUL` | `0xF6 0x01` — `0xF6 ; byte2 = (rd<<2) + rs` | 2 | rd, rs | Z C N V | rd <- (rd * rs)[7:0]; C=1 if it does not fit in 8 bits (V=0). |
| `DIV` | `0xF7 0x0E` — `0xF7 ; byte2 = (rd<<2) + rs` | 2 | rd, rs | Z C N V | rd <- rd / rs (unsigned integer division); C=1 if rs=0 (V=0). |
| `OUT` | `0xF8 0x06` — `0xF8 ; byte2 = (rd<<2) + n` | 2 | n, rd | — | Write port n (0..3): port n <- rd. |
| `IN` | `0xF9 0x0F` — `0xF9 ; byte2 = (rd<<2) + n` | 2 | n, rd | — | Read port n (0..3): rd <- port n. |
| `NEG` | `0xFA 0x00` — `0xFA ; byte2 = (0x0<<4) + (rd<<2)` | 2 | rd | Z C N V | Negate rd: rd <- 0 - rd (Z, C, N, V). |
| `NOT` | `0xFA 0x18` — `0xFA ; byte2 = (0x1<<4) + (rd<<2)` | 2 | rd | Z C N V | Bitwise NOT rd: rd <- ~rd (Z, N; C=0, V=0). |
| `ADC` | `0xFA 0x21` — `0xFA ; byte2 = (0x2<<4) + (rd<<2) + rs` | 2 | rd, rs | Z C N V | Add with carry: rd <- rd + rs + C (Z, C, N, V). |
| `SBC` | `0xFA 0x36` — `0xFA ; byte2 = (0x3<<4) + (rd<<2) + rs` | 2 | rd, rs | Z C N V | Subtract with borrow: rd <- rd - rs - C (Z, C, N, V). |
| `SWAP` | `0xFA 0x42` — `0xFA ; byte2 = (0x4<<4) + (rd<<2) + rs` | 2 | rd, rs | — | Exchange two registers: rd <-> rs (does not change flags). |
| `XCHG` (alias of `SWAP`) | `0xFA 0x42` — `0xFA ; byte2 = (0x4<<4) + (rd<<2) + rs (alias of SWAP)` | 2 | rd, rs | — | Alias of SWAP: exchange two registers (rd <-> rs). |
| `ROL` | `0xFA 0x5C` — `0xFA ; byte2 = (0x5<<4) + (rd<<2)` | 2 | rd | Z C N V | Rotate left through C: rd <- {rd[6:0], C}; C <- rd[7]. |
| `ROR` | `0xFA 0x60` — `0xFA ; byte2 = (0x6<<4) + (rd<<2)` | 2 | rd | Z C N V | Rotate right through C: rd <- {C, rd[7:1]}; C <- rd[0]. |
| `LDW` | `0xFA 0x71 0x03` — `0xFA ; byte2 = (0x7<<4) + (rd<<2) + rs ; byte3 = off` | 3 | rd, [rs+off] | C | Wide indexed load: EA = rs + off (9 bits); rd <- RAM[EA[7:0]]; C <- EA[8] (16-bit pointer). |
| `STW` | `0xFA 0x8B 0x04` — `0xFA ; byte2 = (0x8<<4) + (rd<<2) + rs ; byte3 = off` | 3 | rd, [rs+off] | C | Wide indexed store: EA = rs + off (9 bits); RAM[EA[7:0]] <- rd; C <- EA[8] (16-bit pointer). |
| `TEST` | `0xFA 0x91` — `0xFA ; byte2 = (0x9<<4) + (rd<<2) + rs` | 2 | rd, rs | Z C N V | Test (AND for the flags): Z, N <- rd AND rs; C=0, V=0 (rd is not written). |
| `PUSHF` | `0xFA 0xA0` — `0xFA ; byte2 = (0xA<<4)` | 2 | — | — | Push the flags byte {I,V,N,Z,C} onto the stack (bits 4..0) and decrement SP. |
| `POPF` | `0xFA 0xB0` — `0xFA ; byte2 = (0xB<<4)` | 2 | — | Z C N V I | Pop the flags byte from the stack into C, Z, N, V and I (SP incremented). |
| `ADCW` | `0xFA 0xC2` — `0xFA ; byte2 = (0xC<<4) + (pr<<2) + ps ; 2 EXEC cycles` | 2 | pr, ps | Z C N V | 16-bit pair add: pair pr <- pair pr + pair ps + C, where the pair is (low, low\|1): A=A:B, C=C:D (Z = 16-bit zero; 4 cycles). |
| `SUBW` | `0xFA 0xD2` — `0xFA ; byte2 = (0xD<<4) + (pr<<2) + ps ; 2 EXEC cycles` | 2 | pr, ps | Z C N V | 16-bit pair subtract: pair pr <- pair pr - pair ps - C (C=1 means no borrow; Z = 16-bit zero; 4 cycles). |
