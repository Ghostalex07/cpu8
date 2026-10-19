# ISA — Instruction set of the 8-bit CPU (cpu8)

> **This document is the source of truth.** If the design changes, this is updated
> first and the RTL afterwards.

## 1. Machine model

- **von Neumann architecture**: code and data share a single 256-byte memory.
- **Data bus**: 8 bits. **Address bus**: 8 bits → 256 addresses (0x00–0xFF).
- **Instruction word**: variable (1 or 2 bytes).

### General-purpose registers (8 bits each)

| Name   | Index (rd/rs) | Description            |
|--------|----------------|------------------------|
| A      | `00`           | Accumulator / register 0|
| B      | `01`           | Register 1             |
| C      | `10`           | Register 2             |
| D      | `11`           | Register 3             |

### Internal registers

| Register | Width | Function                                                       |
|----------|-------|----------------------------------------------------------------|
| PC       | 8     | Program counter (address of the next instruction).             |
| IR       | 8     | Instruction register (opcode being executed).                  |
| MDR/op   | 8     | Auxiliary data / operand register (internal datapath use).     |
| SP       | 8     | Stack pointer; points to the next free slot (§10.2).           |
| I        | 1     | Interrupt enable (0 after reset) (§10.6).                      |

### Flags (status register)

| Flag | Name     | Meaning                                                            |
|------|----------|---------------------------------------------------------------------|
| Z    | Zero     | 1 if the result of the last flag-setting operation is 0x00.        |
| C    | Carry    | Carry (add) / **no-borrow** (subtract). See §5.                    |
| N    | Negative | Copy of bit 7 (MSB) of the result. For signed arithmetic (two's complement).|
| V    | Overflow | **Signed** overflow (two's complement). See §5.                    |

> Flag **V** (Phase 8) enables signed comparisons: after `CMP`/`SUB` (or `ADD`),
> `N ⊕ V` means "less than" in signed terms. See the `Jcc` families in §4.

### Output port

- A single (1) 8-bit output register, with no address. The `OUT rd` instruction
  writes it and the testbench prints it with `$display`. On an FPGA it would be
  mapped to LEDs.

## 2. Instruction format

First byte:

```
 7   6   5   4 | 3   2 | 1   0
[   opcode    ]|[ rd  ]|[ rs  ]
```

- `[7:4]` opcode (4 bits, 16 possible values).
- `[3:2]` `rd` — destination/source register (index into the register table).
- `[1:0]` `rs` — source register **or** selector (branch condition, shift
  direction, subtype). When unused, it must be `00`.

Some instructions occupy a **second byte** that is an **immediate** (8-bit
constant), an 8-bit **absolute address**, or the **indices of two registers**. In
that case the `rd`/`rs` bits of the first byte are used according to the table.

### Register encoding

`A=00`, `B=01`, `C=10`, `D=11`.

### Selectors in the `rd`/`rs` fields (per instruction)

| Instruction | `rd` / `rs` fields                                                   |
|-------------|-----------------------------------------------------------------------|
| LDI/ADDI/SUBI/CMPI | `rd`: register; `rs`: `00`=LDI, `01`=ADDI, `10`=SUBI, `11`=CMPI (§10.7) |
| SHL/SHR     | `rs`: `00` = SHL (left), `01` = SHR (right)                           |
| LD/ST rd,[a]| `rs`: `00` = absolute; `01`/`10`/`11` = indexed with base B/C/D (§10.7) |
| Jcc         | `rd`: family (`00` unsigned, `01` signed, `10` status); `rs`: condition (§4) |
| JMP/CALL    | `rs`: `00` = JMP, `01` = CALL                                         |
| Group `0x0` | `rd`: `00` = INC, `01` = DEC, `10` = PUSH, `11` = POP; `rs`: register |
| Group `0xF` | `rd`+`rs` = subcode (see §10.5)                                       |
| rest        | reserved, use `00`                                                    |

## 3. Instruction table

| Op (hex) | Mnemonic  | Bytes | Encoding (byte 1)          | Byte 2      | Description                                  |
|----------|------------|-------|----------------------------|-------------|----------------------------------------------|
| `0`      | INC/DEC/PUSH/POP rd | 1 | `0000 oo ss` (oo=op, ss=reg) | —     | Operation on a register (§10.1).             |
| `1`      | LDI/ADDI/SUBI/CMPI rd,imm | 2 | `0001 rr kk` (kk=00/01/10/11) | `imm` | `LDI`: `rd ← imm`; `ADDI`/`SUBI`: `rd ← rd ± imm` (flags); `CMPI`: flags only (§10.7). |
| `2`      | MOV rd,rs  | 1     | `0010 rr ss`               | —           | `rd ← rs`. **NOP = MOV A,A = `0x20`**.       |
| `3`      | LD rd,[a]  | 2     | `0011 rr ss`               | `a`/`off`   | `rd ← RAM[a]` (`ss=00`); indexed `rd ← RAM[rs+off]` (`ss≠00`, base B/C/D) (§10.7). |
| `4`      | ST rd,[a]  | 2     | `0100 rr ss`               | `a`/`off`   | `RAM[a] ← rd` (`ss=00`); indexed `RAM[rs+off] ← rd` (`ss≠00`) (§10.7). |
| `5`      | ADD rd,rs  | 1     | `0101 rr ss`               | —           | `rd ← rd + rs` (flags).                      |
| `6`      | SUB rd,rs  | 1     | `0110 rr ss`               | —           | `rd ← rd - rs` (flags).                      |
| `7`      | AND rd,rs  | 1     | `0111 rr ss`               | —           | `rd ← rd & rs` (flags Z,N).                  |
| `8`      | OR  rd,rs  | 1     | `1000 rr ss`               | —           | `rd ← rd \| rs` (flags Z,N).                 |
| `9`      | XOR rd,rs  | 1     | `1001 rr ss`               | —           | `rd ← rd ^ rs` (flags Z,N).                  |
| `A`      | CMP rd,rs  | 1     | `1010 rr ss`               | —           | computes `rd - rs`, updates flags, does **not** store the result. |
| `B`      | SHL/SHR rd | 1     | `1011 rr kk` (kk=00/01)    | —           | shifts `rd` by 1 bit (flags).                |
| `C`      | JMP/CALL a | 2     | `1100 00 kk` (kk=00/01)    | `a`         | `kk=00` JMP: `PC←a`; `kk=01` CALL: `push(PC)`, `PC←a` (§10.3). |
| `D`      | Jcc a      | 2     | `1101 ff cc` (ff=family)   | `a`         | conditional branch: family `ff` and condition `cc` (see §4). |
| `E`      | OUT rd / IN rd | 1 | `1110 rr kk` (kk=00/01)    | —           | `kk=00` OUT: port 0 ← `rd`; `kk=01` IN: `rd` ← port 0 (§10.9). |
| `F`      | System/memory group | 1–3 | `1111 dddd` (subcode) | (per subtype) | `HLT`, `RET`, `EI`, `DI`, indirect `LD/ST`, `MUL`/`DIV`, `OUT n,rd`/`IN n,rd` (§10.4, §10.5, §10.8, §10.9) and the `0xFA` **prefix** for the extended instructions (§10.10). |

`rr` = `rd` index, `ss` = `rs` index, `oo` = sub-operation, `dddd` = subcode.
`imm`/`a` = 8 bits.

## 4. Conditional branches (Jcc)

`Jcc a` evaluates a condition and, if it holds, performs `PC ← a`. Otherwise it
continues with the next instruction. Byte 1 is `1101 ff cc`, where `ff` (the `rd`
bits, reserved in the original Jcc) selects the **family** and `cc` (the `rs`
field) the condition within it.

**Family `ff=00` — unsigned** (backward-compatible with the original definition):

| cc (`rs`) | Mnemonic | Condition     |
|-----------|-----------|---------------|
| `00`      | JZ        | `Z == 1`      |
| `01`      | JNZ       | `Z == 0`      |
| `10`      | JC        | `C == 1`      |
| `11`      | JNC       | `C == 0`      |

Read aliases for unsigned comparisons:

| Alias | Equivalent | Branches when              |
|-------|-----------|----------------------------|
| JHS   | JC        | `rd >= rs` (no borrow)     |
| JLO   | JNC       | `rd <  rs` (borrow)        |

> **Confirmed (Phase 5).** Since we adopt the inverted-C convention (§5: `C=1` =
> no borrow), `JC` branches when `rd >= rs`, so the alias finally adopted is
> `JHS = JC` and `JLO = JNC`. Thus *JLO* really branches when the first operand is
> *lower* (`rd < rs`) and *JHS* when it is *higher or same* (`rd >= rs`).

**Family `ff=01` — signed (two's complement)** (Phase 8). They use `N` and `V`. It
is best to precede them with `CMP`/`SUB` (or `ADD`) on the two values. Let
`less = N ⊕ V`:

| cc (`rs`) | Mnemonic | Condition          | Meaning                  |
|-----------|-----------|--------------------|--------------------------|
| `00`      | JLT       | `N ⊕ V == 1`       | branches if `rd <  rs`   |
| `01`      | JGE       | `N ⊕ V == 0`       | branches if `rd >= rs`   |
| `10`      | JLE       | `Z == 1` or `N ⊕ V` | branches if `rd <= rs`  |
| `11`      | JGT       | `Z == 0` and `N ⊕ V == 0` | branches if `rd > rs` |

**Family `ff=10` — status** (Phase 8): tests `V` or `N` directly.

| cc (`rs`) | Mnemonic | Condition     |
|-----------|-----------|---------------|
| `00`      | JVS       | `V == 1`      |
| `01`      | JVC       | `V == 0`      |
| `10`      | JMI       | `N == 1`      |
| `11`      | JPL       | `N == 0`      |

Encoding: byte 1 = `0xD0 | (family << 2) | condition`. So `JZ`=`0xD0`, `JNZ`=`0xD1`,
`JC`=`0xD2`, `JNC`=`0xD3`, `JLT`=`0xD4`, `JGE`=`0xD5`, `JLE`=`0xD6`, `JGT`=`0xD7`,
`JVS`=`0xD8`, `JVC`=`0xD9`, `JMI`=`0xDA`, `JPL`=`0xDB`.

## 5. The C flag convention (carry / borrow)

The carry is defined from the ALU's **8-bit adder**, which always computes
`op1 + op2 + cin`:

- **ADD rd,rs** and **ADDI rd,imm**: `op1 = rd`, `op2 = rs` (or `imm`), `cin = 0`.
  `C` = carry out of bit 7. `C=1` means **unsigned** overflow (the result does not
  fit in 8 bits).

- **SUB rd,rs**, **SUBI rd,imm**, **CMP rd,rs** and **CMPI rd,imm**: the
  subtraction is done as `rd - rs = rd + (~rs) + 1`, i.e. `op1 = rd`, `op2 = ~rs`
  (or `~imm`), `cin = 1`. Then `C` = carry out of bit 7 of the adder, which in
  this setup means:

  | Situation (unsigned)  | `C` |
  |-----------------------|-----|
  | `rd >= rs` (no borrow)|  1  |
  | `rd <  rs` (borrow)   |  0  |

  **Chosen convention (inverted, 6502/AVR/ARM style): `C=1` ⇒ there was NO borrow;
  `C=0` ⇒ there was a borrow.** That is why `JC` = "branch if `rd >= rs`" and
  `JNC` = "branch if `rd < rs`". The advantage is that the subtraction **physically
  reuses the same adder** as the addition, with no extra logic.

- **AND / OR / XOR**: `C = 0`.
- **SHL**: `C` = bit 7 **before** the shift (the bit shifted out to the left).
- **SHR**: `C` = bit 0 **before** the shift (the bit shifted out to the right).
- **MUL rd,rs**: `C = 1` if the product does not fit in 8 bits (high byte ≠ 0); `V = 0`.
- **DIV rd,rs**: `C = 1` if the divisor was 0 (and then `rd = 0`); `V = 0`.
- **NEG rd** (§10.10): `C = 1` if the operand was `0` (otherwise `0`); `V` = signed overflow (`rd = 0x80`).
- **NOT rd** (§10.10): `C = 0`, `V = 0`.
- **ADC rd,rs** (§10.10): like ADD but adds the carry in: `rd' = rd + rs + C`; `C = 1` if the sum ≥ 256.
- **SBC rd,rs** (§10.10): like SUB but subtracts the borrow: `rd' = rd - rs - C`; `C = 0` if there was a borrow.
- **TEST rd,rs** (§10.10): the `AND` result is discarded: only `Z` and `N` are
  updated (`C=0`, `V=0`) and `rd` is not written.
- **ADCW pr,ps** / **SUBW pr,ps** (§10.10): 16-bit versions of `ADC`/`SBC`
  over the register pairs (`A:B`, `C:D`); the same `C` rule applies to each
  byte chained together, and `Z=1` only if **both** result bytes are zero.
- **PUSHF / POPF** (§10.10): `PUSHF` only saves the flags byte (it does not
  modify the flags); `POPF` **sets** `C,Z,N,V,I` from the byte popped.
- **ROL / ROR rd** (§10.10): `C` = the bit rotated out (`rd[7]` for ROL, `rd[0]` for ROR).
- **SWAP / XCHG rd,rs** (§10.10): do **not** modify flags.
- **LDW / STW rd,[rs+off]** (§10.10): only update `C` (bit 8 of the computed 9-bit address).
- **LDI / MOV / LD / ST / OUT / IN / NOP / JMP / Jcc / HLT / PUSH / POP / PUSHF / CALL / RET / EI / DI**: do **not** modify flags.

### The Z and N flags

- `Z = 1` if the result of the flag-setting operation is `0x00`.
- `N = result[7]` (copy of the MSB).
- **Only** these instructions update flags: **ADD, ADDI, SUB, SUBI, AND, OR, XOR,
  CMP, CMPI, SHL, SHR, MUL, DIV** and **NEG, NOT, ADC, SBC, ROL, ROR, TEST,
  ADCW, SUBW, POPF** (§10.10),
  and also **INC**/**DEC** (they change `Z`, `N`
  and `V` but **not** `C`).
  In **SHL/SHR**, `Z` and `N` are recomputed on the shifted value and `C` holds the
  bit shifted out (see above). Loads (`LDI/MOV/LD`) do **not** touch the flags.

### Flag V (signed overflow, Phase 8)

`V` indicates that the **signed** result (two's complement over 8 bits) does not
fit:

- **ADD / ADDI**: `V = 1` if both operands have the same sign and the result has a
  different one (e.g. `0x7F + 0x01 = 0x80` → `V=1`).
- **SUB / SUBI / CMP / CMPI**: `V = 1` if the operands have different signs and the
  result does not match the first operand's sign (e.g. `0x80 - 0x01 = 0x7F` → `V=1`).
- **INC / DEC**: they also update `V` (e.g. `INC` of `0x7F` gives `0x80` with `V=1`).
- **AND / OR / XOR / SHL / SHR** and the rest of the instructions: `V = 0` (not
  significant).

With `N` and `V` the signed comparison is implemented: **"rd < rs" ⇔ `N ⊕ V == 1`**.
The `JLT/JGE/JLE/JGT` families of `Jcc` (§4) use it directly.

## 6. Design notes and limitations (to revisit later)

1. **Opcode space saturated → chosen solution (Phase 7).** The 16 original codes
   (`0`–`F`) were all taken, so the already-reserved gaps are used: `NOP` is an
   **alias of `MOV A,A` (`0x20`)**; **opcode `0x0`** becomes the page of
   **operations on a register** (`INC`/`DEC`/`PUSH`/`POP`, 16 subcodes); **opcode
   `0xF`** is the **system/memory** page (`HLT`/`RET`/`EI`/`DI` and indirect
   `LD`/`ST`); and the `0xC` branch family adds `CALL` (`0xC1`) alongside `JMP`
   (`0xC0`). All of the above is **backward-compatible**: no existing byte changes
   meaning. Details in §10.
2. **`ADDI`/`SUBI`/`CMPI` (Phase 8)**: implemented in the `LDI` page
   (`0001 rr kk`, see §10.7) in a **backward-compatible** way (`kk=00` is still
   `LDI`). To add a constant you no longer need `LDI` into a free register + `ADD`.
3. **Register-indirect addressing**: **implemented in Phase 7** as
   `LD rd,[rs]` / `ST rd,[rs]` (`0xF4`/`0xF5`, see §10.4), using a register as a
   pointer. **Indexed addressing** (base + offset) **implemented in Phase 8** as
   `LD/ST rd,[rs+off]` (`ss≠00`, base B/C/D; see §10.7). There is still **no**
   memory `(indirect)` (double indirection: `RAM[RAM[a]]`).
4. **Flag V (Phase 8)**: implemented; it enables the signed comparisons
   `JLT/JGE/JLE/JGT` and the status branches `JVS/JVC/JMI/JPL` (see §4 and §5).
5. **I/O**: there are 4 selectable I/O ports (`OUT n, rd` / `IN n, rd`, §10.9). The
   first port (0) still works with the short form `OUT rd`.
6. **8-bit addresses** shared with code and data in von Neumann: be careful not to
   overwrite the program when writing data. Moreover, the **stack** occupies RAM
   growing downwards from `0xF0`, so that space must be left free (see §10.2).
7. **`MUL`/`DIV` (Phase 9)**: implemented as combinational hardware in the ALU
   (subcodes `0xF6`/`0xF7`). The multiplier and divider add LUT area, but the
   design still fits comfortably in the iCE40HX1K. `DIV` by zero gives `0` and
   `C=1`.

## 7. Examples

```asm
; Adds 5 + 3 and shows the result on the output port
        LDI A, 5        ; A = 0x05
        LDI B, 3        ; B = 0x03
        ADD A, B        ; A = A + B = 0x08, Z=0 C=0 N=0
        OUT A           ; prints 0x08
        HLT
```

Encoded as `.hex` for `$readmemh` (one byte per line):

```
10
05
11
03
51
E0
F0
```

> Here `ADD A,B` = `0101 rr ss` with `rd=A=00`, `rs=B=01` → `0101 0001` = `0x51`.

```asm
; Counts down from 3 to 0, printing each value
        LDI A, 3
loop:   OUT A
        LDI B, 1
        SUB A, B
        JNZ loop        ; repeats while A != 0
        HLT
```

> `SUB A,B` = `0110 0001` = `0x61`. `JNZ loop` = `1101 00 cc` with `cc=JNZ=01` → `0xD1`.

## 8. Assembler (`asm/assembler.py`, Phase 5)

Translates an `.asm` file into a `.hex` (one hexadecimal byte per line) that the
testbench loads with `$readmemh`.

**Usage**

```sh
python3 asm/assembler.py program.asm -o program.hex   # assemble
python3 asm/assembler.py program.asm -l               # + listing and labels
make asm  PROG=programs/demo                          # Makefile shortcut
make sim  PROG=programs/demo                          # assemble and simulate
```

**Syntax**

- Comments with `;` to the end of the line.
- Labels: `name:` at the start of a line, alone or before an instruction.
  E.g. `loop: OUT A`. Referenceable as the target of `JMP`/`Jcc` or as an address
  in `LD`/`ST`.
- Mnemonics and registers are case-insensitive (`ldi A, 5` = `LDI A, 5`).
- Registers: `A`, `B`, `C`, `D`.
- Numbers: decimal (`7`, `255`), hexadecimal (`0x20` or `$20`) and binary (`0b1010`).
- Direct `LD`/`ST` accept the address with or without brackets: `LD A, [0x20]` or
  `LD A, 0x20`. The target can be a label: `LD A, [loop]`.
- **Indirect** `LD`/`ST` (register-based) use a register name inside the brackets:
  `LD A, [B]` = `A ← RAM[B]`; `ST A, [B]` = `RAM[B] ← A` (see §10.4).
- **Indexed** `LD`/`ST` (base + offset, Phase 8): `LD A, [B+3]` = `A ← RAM[B+3]`;
  `ST A, [C+table]`. The base must be `B`, `C` or `D` (with `A` the absolute mode
  would be used); the offset accepts a sign (`[B-1]`) and labels.
- **16-bit indexed** `LDW`/`STW` (Phase 12, prefix `0xFA`): `LDW A, [B+3]`,
  `STW C, [D+4]`. Any register can be the base and the 9-bit sum's bit 8 goes to
  `C` (see §10.10).
- Immediates with the ALU (Phase 8): `ADDI`, `SUBI`, `CMPI` (e.g. `ADDI A, 5`).
- Extended ALU ops (Phase 12, §10.10): `NEG`, `NOT`, `ADC`, `SBC`, `SWAP`/`XCHG`,
  `ROL`, `ROR`, `TEST`, `PUSHF`, `POPF`, `ADCW`, `SUBW`.

**Accepted mnemonics**: `NOP`, `LDI`, `ADDI`, `SUBI`, `CMPI`, `MOV`, `LD`, `ST`,
`ADD`, `SUB`, `AND`, `OR`, `XOR`, `CMP`, `SHL`, `SHR`, `MUL`, `DIV`, `IN`, `OUT`,
`INC`, `DEC`, `PUSH`, `POP`, `JMP`, `CALL`, `RET`, `JZ`, `JNZ`, `JC`, `JNC`, `JHS`,
`JLO`, `JLT`, `JGE`, `JLE`, `JGT`, `JVS`, `JVC`, `JMI`, `JPL`, `EI`, `DI`, `HLT`,
`NEG`, `NOT`, `ADC`, `SBC`, `SWAP`, `XCHG`, `ROL`, `ROR`, `LDW`, `STW`,
`TEST`, `PUSHF`, `POPF`, `ADCW`, `SUBW`.
(`NOP` is encoded as `MOV A,A` = `0x20`; `JHS`/`JLO` are aliases of `JC`/`JNC`, see §4;
`XCHG` is an alias of `SWAP`, see §10.10.)

**Directives** (start with `.`, case-insensitive; Phase 9)

| Directive          | Effect                                                                |
|--------------------|-----------------------------------------------------------------------|
| `.equ NAME, expr`  | Defines a reusable constant (a number or a previous constant).        |
| `.org expr`        | Sets the current address. If it moves forward, it fills with `00`; moving backwards is an error. |
| `.db item, ...`    | Emits bytes: numbers, labels or strings `"..."` (ASCII).              |
| `.dw item, ...`    | Emits 16-bit little-endian words: numbers, labels or constants (2 bytes per item; no strings). |

Example:

```asm
.equ LEDS, 0xE0
table: .db 10, 20, 30, "Hello", 0   ; data bytes in RAM
.org 0x20                          ; the code starts at 0x20
start: LDI A, LEDS                 ; A = constant
        OUT A
        HLT
```

Inside a `.db` string the escapes `\n`, `\t`, `\r`, `\0`, `\\` and `\"` are
accepted; commas inside the quotes do not separate fields.

**How it works (two passes + constants)**

0. *Pass 0*: collects all `.equ` definitions into the constant table (so they can
   be used even if defined further down).
1. *Pass 1*: walks the source and assigns each label its address. To do so it needs
   the size of each instruction: **2 bytes** for `LDI`, `ADDI`, `SUBI`, `CMPI`,
   `LD`/`ST` (direct, indirect and indexed), `JMP`, `CALL`, `MUL`, `DIV`, `Jcc`
   and the 2-byte prefixed instructions (`NEG`, `NOT`, `ADC`, `SBC`, `SWAP`,
   `XCHG`, `ROL`, `ROR`, `TEST`, `PUSHF`, `POPF`, `ADCW`, `SUBW`); **3 bytes** for `LDW`/`STW`;
   **1 byte** for the rest (`OUT`/`IN` are 1 byte in their register form and 2 in
   the ported `OUT n, rd`/`IN n, rd`); `.org` sets the PC, `.db` contributes one byte per
   item and `.dw` two bytes per item.
2. *Pass 2*: emits the bytes (`.org` fills with zeros) and resolves references to
   labels and constants (already known, even if defined further down).

**Errors**: reported with the line number and a clear message (unknown mnemonic,
invalid register, number out of range `0..255`, undefined or duplicate label,
wrong number of operands, program larger than 256 bytes). The assembler exits
with a non-zero status code if there is an error.

## 9. Demo programs and automated verification (Phase 6)

In `programs/` there are several example programs written by hand with the ISA:

| Program         | What it does                                                    | Output (via `OUT`)                          |
|-----------------|-----------------------------------------------------------------|---------------------------------------------|
| `countdown.asm` | Counts down from 9 to 0                                         | `9 8 7 6 5 4 3 2 1 0`                        |
| `fibonacci.asm` | Fibonacci until the sum overflows 8 bits                        | `1 1 2 3 5 8 13 21 34 55 89 144 233`         |
| `multiply.asm`  | Multiplication by repeated addition (`6 x 7`), shows partials   | `6 12 18 24 30 36 42`                        |
| `fase4.asm`     | Countdown with a pass through memory (Phase 4 program)          | `7 6 5 4 3 2 1`                              |
| `incdec.asm`    | `INC`/`DEC` and checks that they do not alter flag C (Phase 7.2) | `1 2 3 4 5 4`                              |
| `stack.asm`     | `PUSH`/`POP` (LIFO) and `RET` to a pushed address (Phase 7.3)   | `2 1 1`                                      |
| `callret.asm`   | Subroutine `sum` called with `CALL`/`RET` (Phase 7.4)           | `7 14`                                       |
| `indirect.asm`  | Indirect addressing `LD/ST rd,[rs]` with a pointer (Phase 7.4)  | `7 42`                                       |
| `extensions.asm`| Immediates `ADDI`/`SUBI`/`CMPI`, indexed `[rs+off]` and signed/status branches (Phase 8) | `0A 0F 08 22 33 11 44 A1 A2 A3 B1 B2` (hex) |
| `muldiv.asm`    | Hardware `MUL`/`DIV`, including overflow and division by zero (Phase 9) | `2A 90 C1 1C 21 00 C2 C3` (hex) |
| `inout.asm`     | `IN` input and port output `OUT n, rd` (Phase 9)                | `10 12 AB 55` (hex) |
| `euclid.asm`    | Greatest common divisor of (144,60) by Euclid's algorithm with `DIV`/`MUL` | `0C` (hex) |
| `factorial.asm` | Iterative factorial 5! = 120 with the hardware `MUL`            | `78` (hex) |
| `primes.asm`    | Primes below 32 by trial division with `DIV`/`MUL`             | `02 03 05 07 0B 0D 11 13 17 1D 1F` (hex) |
| `sort.asm`      | Sorts an array with bubble sort; the data is declared with the `.db` directive | `01 02 03 05 08 09` (hex) |
| `irq.asm`       | Interrupt: `EI`, counter 0..9 and a handler that counts to 1 (Phase 7.5) | `0 1 2 3 4 5 6 7 8 9 1`                 |
| `extensions3.asm` | Prefix `0xFA`: `NEG`, `NOT`, `ADC`, `SBC`, `SWAP`, `ROL`, `ROR` and the 16-bit `LDW`/`STW` (Phase 12) | `FB 04 10 11 FF 01 1E 1F 02 05 00 80 34 12 77 88 99 99 C1 C2` (hex) |
| `extensions4.asm` | Prefix `0xFA`: `TEST`, `PUSHF`, `POPF` and the 16-bit pair operations `ADCW`/`SUBW` (Phase 12) | `0F 01 02 03 04 07 03 05 00 02 06 05 02 07 00 FF 08 09 0A FF FF 00 02 0B 0C` (hex) |

**How they are verified.** Each program has a sibling file `programs/<name>.ref`
with the list of expected outputs in hexadecimal (one value per line, no
comments). The testbench `tb/cpu_tb.v`:

- Loads the program with `+hex=<path>` and the expected outputs with `+exp=<path>`.
- Runs until `HLT`, prints each `OUT` and compares it with the `.ref`; it counts the
  outputs and fails if the number or any value does not match. Without `+exp` it
  only prints.
- Generates `build/cpu_tb.vcd` for GTKWave.

`make test` runs the module testbenches (`alu`, `pc`, `ram`, `regfile`) and then,
for each `programs/*.asm`, assembles it, simulates it and compares it with its
`.ref`. `make sim PROG=programs/<name>` does the same for a single program (it
compares automatically if the `.ref` exists).

`irq.asm` is verified separately with `make irqtest`: `tb/irq_tb.v` instantiates
the CPU with `IRQ_VECTOR = 0x10` and drives the `irq` signal after reset (the
normal `cpu_tb` leaves it at `0`, so `irq.asm` is excluded from the `progtests`
loop).

**Differential verification.** Besides the `.ref` files (which check that the
output *does not change*), `tools/iss.py` is a reference model of the ISA in
Python and `make difftest` runs it in parallel with the RTL (`tb/cpu_dump_tb.v`)
over the demo programs and hundreds of random programs, comparing the full state
(registers, flags, `SP`, `PC`, RAM and `OUT`) **after every instruction**. This
proves the RTL is *correct*, not only stable. Roughly half of the random programs
also run with the `irq` signal active (threshold derived from the seed) and the
ISS models interrupt handling just like the RTL (`S_IRQ` state: pushes `PC`,
clears `I` and jumps to the vector, without retiring an instruction), so the
interrupt path is also covered by the differential contrast. `tools/test_iss.py`
adds directed micro-tests (including IRQ) and contrasts the model with the `.ref`
files.

**Single source of truth for the ISA.** `asm/isa_table.py` describes the ISA in a
*machine-readable* way (mnemonics, operand forms, bytes, flags and description).
`make docs` generates the opcode listing `docs/OPCODES.md` from it;
`make docs-check` verifies that this file is up to date and `asm/test_isa_table.py`
(part of `make pytools`) verifies that the table does not drift from the real
assembler or disassembler.

## 10. Phase 7 extensions

### 10.1 Group `0x0` — operations on a register (1 byte)

Format `byte1 = 0000 oo ss`, where `oo` = sub-operation (bits `[3:2]`) and `ss` =
register (bits `[1:0]`).

| `oo` | Mnemonic | Effect                                        |
|------|-----------|-----------------------------------------------|
| `00` | INC rd    | `rd ← rd + 1`; updates `Z`,`N` (not `C`).     |
| `01` | DEC rd    | `rd ← rd - 1`; updates `Z`,`N` (not `C`).     |
| `10` | PUSH rd   | `RAM[SP] ← rd`; then `SP ← SP - 1` (§10.2).   |
| `11` | POP rd    | `SP ← SP + 1`; then `rd ← RAM[SP]` (§10.2).   |

Encoding: `INC A..D = 0x00..0x03`, `DEC A..D = 0x04..0x07`, `PUSH A..D = 0x08..0x0B`,
`POP A..D = 0x0C..0x0F`.

### 10.2 Stack and stack pointer (SP)

- `SP` is an 8-bit internal register. After reset it holds `0xF0`.
- The stack is **descending** (grows towards lower addresses) and lives in the same RAM.
- `SP` points to the **next free slot** (empty descending stack, 6502 model):
  - `PUSH rd`: `RAM[SP] ← rd`; `SP ← SP - 1`.
  - `POP rd` : `SP ← SP + 1`; `rd ← RAM[SP]`.
- **Collision**: the program and the data must be kept below `0xF0`; the stack grows
  down from there towards `0x00`.

### 10.3 Subroutines: CALL / RET

- `CALL a` (`0xC1` + `a`, 2 bytes): saves the return address (**the next
  instruction**, i.e. `CALL_addr + 2`) with an internal `PUSH` and performs `PC ← a`.
- `RET` (`0xF1`): `PC ← POP` (recovers the saved address).
- They rely on `SP` and the stack, so they cannot nest beyond the available stack
  space. They do not modify flags.

### 10.4 Register-indirect addressing

| Mnemonic     | Bytes | Byte 1 | Byte 2        | Effect          |
|--------------|-------|--------|---------------|-----------------|
| `LD rd,[rs]` | 2     | `0xF4` | `(rd<<2)\|rs` | `rd ← RAM[rs]`  |
| `ST rd,[rs]` | 2     | `0xF5` | `(rd<<2)\|rs` | `RAM[rs] ← rd`  |

It allows using a register as a **pointer** (e.g. walking an array by incrementing
the address register with `INC`). Byte 2 packs the `rd` and `rs` indices.

### 10.5 Group `0xF` — system and memory

`byte1 = 1111 dddd`, with `dddd` = `rd`+`rs` (subcode):

| Subcode   | Byte1 | Mnemonic    | Bytes | Effect                          |
|-----------|-------|-------------|-------|---------------------------------|
| `0000`    | `0xF0`| HLT         | 1     | stops the CPU (no changes).     |
| `0001`    | `0xF1`| RET         | 1     | `PC ← POP` (§10.3).             |
| `0010`    | `0xF2`| EI          | 1     | `I ← 1` (enables IRQ) (§10.6).  |
| `0011`    | `0xF3`| DI          | 1     | `I ← 0` (disables IRQ).         |
| `0100`    | `0xF4`| LD rd,[rs]  | 2     | `rd ← RAM[rs]` (§10.4).         |
| `0101`    | `0xF5`| ST rd,[rs]  | 2     | `RAM[rs] ← rd` (§10.4).         |
| rest      | —     | *(reserved)* | —    | —                               |

### 10.6 Interrupts

- Input signal `IRQ` (level, active high) and enable bit `I` (0 after reset):
  `EI` sets `I=1`; `DI` sets `I=0`.
- If `I=1` and `IRQ=1` **at the start of an instruction**, instead of fetching the
  next one the CPU:
  1. performs a `PUSH` of the return address (the current `PC`),
  2. sets `I ← 0` (prevents re-entry),
  3. jumps to the **`IRQ_VECTOR`** (a `cpu.v` parameter, default `0x08`).
- The handler ends with `RET`, which restores the `PC`.
- **Limitation**: when handling the interrupt only the `PC` is saved; the flags are
  not restored. The handler must save/restore with `PUSH`/`POP` the registers it
  uses, and the vector address must be reserved in the program.

**Implementation (Phase 7.5).** Handling takes one cycle in its own FSM state
(`S_IRQ`): on entering from `S_FETCH` (without fetching an instruction) the `PC` is
pushed, `I` is cleared and the `PC` loads `IRQ_VECTOR`. Since `I` is automatically
set to `0`, a single `EI` suffices: even if `IRQ` stays high, the interrupt is not
repeated until the next `EI`. `EI` takes effect immediately (the very next `FETCH`
cycle can already handle the IRQ).

### 10.7 Phase 8 extensions (immediates, indexing and flag V)

They are all **backward-compatible**: they reuse reserved fields that were `00`, so
no existing byte changes meaning (the `programs/*.hex` are byte-for-byte
identical).

**a) Immediates with the ALU** — page 0x1, with the sub-operation in the `rs` field
(`byte1 = 0001 rr kk`):

| `kk` (`rs`) | Mnemonic     | Byte 1 | Byte 2 | Effect                              |
|-------------|--------------|--------|--------|-------------------------------------|
| `00`        | LDI rd,imm   | `0x1r` | `imm`  | `rd ← imm` (backward-compatible).   |
| `01`        | ADDI rd,imm  | `0x1r+1`| `imm` | `rd ← rd + imm` (flags Z,C,N,V).    |
| `10`        | SUBI rd,imm  | `0x1r+2`| `imm` | `rd ← rd - imm` (flags Z,C,N,V).    |
| `11`        | CMPI rd,imm  | `0x1r+3`| `imm` | computes `rd - imm`, flags, no store.|

E.g.: `LDI A,10`=`10 0A`, `ADDI A,5`=`11 05`, `SUBI A,6`=`12 06`, `CMPI A,9`=`13 09`.

**b) Indexed addressing** — `LD`/`ST` with the base in the `rs` field
(`byte1 = 0011/0100 rr ss`, `byte2 = off`):

| `ss` (`rs`) | Mode                                            |
|-------------|-------------------------------------------------|
| `00`        | absolute (backward-compatible): `RAM[a]`        |
| `01`/`10`/`11` | indexed with base `B`/`C`/`D`: `RAM[rs+off]` |

E.g.: `LD D,[C+3]`=`3E 03`, `ST A,[B+3]`=`41 03`. Base `A` is not available because
`ss=00` encodes the absolute mode (to index with `A`, copy it to another register
first).

**c) Signed and status branches** — see §4. The `rd` field of the `Jcc` selects the
family: `JLT/JGE/JLE/JGT` (signed, using `N` and `V`) and `JVS/JVC/JMI/JPL`
(status).

### 10.8 Multiplication and division (Phase 9)

Two **2-byte** instructions are added to group `0xF` in the still-free subcodes.
The second byte carries the two registers, `(rd<<2)|rs`, just like the indirect
mode:

| Byte 1 | Mnemonic    | Byte 2     | Effect                                            |
|--------|-------------|------------|---------------------------------------------------|
| `0xF6` | MUL rd,rs   | `(rd<<2)\|rs` | `rd ← (rd × rs)[7:0]`. `C=1` if the product does not fit in 8 bits. |
| `0xF7` | DIV rd,rs   | `(rd<<2)\|rs` | `rd ← rd / rs` (unsigned). `C=1` if `rs = 0`.  |

Both update `Z` and `N`; `V = 0`. In `DIV`, dividing by zero gives `rd = 0` and
`C = 1` (a deterministic result, not `x` in simulation).

E.g.: `MUL A,B`=`F6 01` (7×6 → `0x2A`), `DIV A,B`=`F7 01` (200/7 → `0x1C`).
Example program: `programs/muldiv.asm`.

### 10.9 Input/output with ports (Phase 9)

The CPU exposes four 8-bit **ports** (0..3). The 1-byte form always uses port 0;
the ported **2-byte** form selects the port in the 2 low bits of the second byte:

| Byte 1 | Mnemonic    | Bytes | Byte 2        | Effect                                     |
|--------|-------------|-------|---------------|--------------------------------------------|
| `0xE0\|(rd<<2)` | OUT rd | 1 | —          | port 0 ← `rd` (backward-compatible).       |
| `0xE0\|(rd<<2)\|01` | IN rd | 1 | —       | `rd` ← port 0.                             |
| `0xF8` | OUT n, rd   | 2     | `(rd<<2)\|n`  | port `n` ← `rd`.                           |
| `0xF9` | IN n, rd    | 2     | `(rd<<2)\|n`  | `rd` ← port `n`.                           |

`n` is a number 0..3 (error if it is out of range). The CPU **drives** the `out_port`
signal (2 bits, the port of the last `OUT`) and **receives** `in_data` (8 bits); so
the environment knows which port it must present on `in_data`, the CPU also drives
`in_port` (2 bits) during the `IN` instruction (see `rtl/cpu.v`).

E.g.: `OUT A`=`E0`, `IN A`=`E1`, `OUT 2, B`=`F8 06`, `IN 3, D`=`F9 0F`.
Example program: `programs/inout.asm` (the testbench presents `0x10+n` on
`in_data` for port `n`).

### 10.10 Extended instructions (Phase 12, prefix `0xFA`)

The byte `0xFA` is a **prefix**: it selects an *extended operation* that is
carried in the next byte. This keeps the base ISA — and therefore every
existing `.hex` — byte-identical, while new instructions are added additively.
A prefixed instruction is **2 bytes**, or **3** for `LDW`/`STW`:

| Byte | Content |
|------|---------|
| 1 | `0xFA` (prefix) |
| 2 | `(xop << 4) \| (rd << 2) \| rs` — the extended sub-operation `xop` plus up to two register indices |
| 3 | the displacement `off` (only for `LDW`/`STW`) |

The sub-operations (`xop`) are:

| `xop` | Mnemonic | Bytes | Operands | Effect |
|-------|----------|-------|----------|--------|
| `0x0` | `NEG rd` | 2 | `rd` | `rd ← 0 - rd` (`Z C N V`). |
| `0x1` | `NOT rd` | 2 | `rd` | `rd ← ~rd` (`Z N`; `C=0`, `V=0`). |
| `0x2` | `ADC rd,rs` | 2 | `rd`, `rs` | `rd ← rd + rs + C` (`Z C N V`). |
| `0x3` | `SBC rd,rs` | 2 | `rd`, `rs` | `rd ← rd - rs - C` (`Z C N V`). |
| `0x4` | `SWAP rd,rs` (alias `XCHG`) | 2 | `rd`, `rs` | exchange `rd` and `rs` (no flags). |
| `0x5` | `ROL rd` | 2 | `rd` | rotate left through `C`: `rd ← {rd[6:0], C}`; `C ← rd[7]`. |
| `0x6` | `ROR rd` | 2 | `rd` | rotate right through `C`: `rd ← {C, rd[7:1]}`; `C ← rd[0]`. |
| `0x7` | `LDW rd,[rs+off]` | 3 | `rd`, `rs`, `off` | 9-bit `EA = rs + off`; `rd ← RAM[EA[7:0]]`; `C ← EA[8]`. |
| `0x8` | `STW rd,[rs+off]` | 3 | `rd`, `rs`, `off` | 9-bit `EA = rs + off`; `RAM[EA[7:0]] ← rd`; `C ← EA[8]`. |
| `0x9` | `TEST rd,rs` | 2 | `rd`, `rs` | `rd AND rs` **for the flags only** (`Z`, `N`; `C=0`, `V=0`); `rd` is **not** written. |
| `0xA` | `PUSHF` | 2 | — | push the flags byte: `RAM[SP] ← {0,0,0,I,V,N,Z,C}`; `SP ← SP - 1`. |
| `0xB` | `POPF` | 2 | — | `SP ← SP + 1`; the popped byte restores `C,Z,N,V,I` (bits 4..0). |
| `0xC` | `ADCW pr,ps` | 2 | `pr`, `ps` | 16-bit pair sum: `pr:pr|1 ← pr:pr|1 + ps:ps|1 + C` (`Z C N V`); 4 cycles. |
| `0xD` | `SUBW pr,ps` | 2 | `pr`, `ps` | 16-bit pair difference: `pr pair − ps pair − C` (`Z C N V`); 4 cycles. |
| `0xE`..`0xF` | — | 2 | — | **reserved** (2-byte no-op). |

Unlike the base indexed `LD/ST rd,[rs+off]`, the base register of `LDW`/`STW` may
be **any** register (`A`–`D`) and the sum is computed with **9 bits**: bit 8 is
delivered to `C`, which lets a 16-bit pointer be walked one page at a time
(`page ← page + carry`).

`ADC`/`SBC` reuse the adder (they share one ALU operation, selected by the `sh`
bit); likewise `ROL`/`ROR` share a rotate-through-carry unit.

`TEST` is the `AND` operation with its result discarded: the cheapest way to
probe a value or to **clear `C` and `V`** without touching any register.

`PUSHF`/`POPF` move the **flags byte** in and out of the stack: bit0 `C`,
bit1 `Z`, bit2 `N`, bit3 `V`, bit4 `I`; bits 5..7 are always 0.

`ADCW`/`SUBW` operate on **16-bit register pairs**: the low byte is the operand
(`pr`/`ps`) and the high byte is the same register with bit 0 set (`pr|1`).
The low operand must be `A` (pair `A:B`) or `C` (pair `C:D`); the assembler
rejects odd registers. The low byte executes first (state `S_EXEC`) and the
high byte in a second cycle (`S_EXEC2`), chaining the carry — or, for `SUBW`,
its inversion (the borrow). `Z` is set only when **both** result bytes are
zero, so a 16-bit zero is detected correctly. Each instruction takes 4 cycles.

Hardware (see `docs/ARCHITECTURE.md`): the FSM gains an `S_OPR2` state that
fetches the 3rd byte, `cpu.v` keeps byte 2 of the prefix in an `xop` register,
the register file has a **second write port** (so `SWAP` writes both registers in
the same cycle) and the RAM address can be taken from the ALU result (the 9-bit
`EA` of `LDW`/`STW`), and an `S_EXEC2` state that runs the high byte of the
16-bit `ADCW`/`SUBW` pairs (the FSM therefore has 7 states).

E.g.: `NEG A`=`FA 00`, `ADC A,B`=`FA 21`, `SWAP A,C`=`FA 42`, `ROL D`=`FA 5C`,
`LDW A,[B+3]`=`FA 71 03`, `STW C,[D+4]`=`FA 8B 04`, `TEST A,B`=`FA 91`,
`PUSHF`=`FA A0`, `POPF`=`FA B0`, `ADCW A,C`=`FA C2`, `SUBW A,C`=`FA D2`.
Example programs: `programs/extensions3.asm` and `programs/extensions4.asm`.
