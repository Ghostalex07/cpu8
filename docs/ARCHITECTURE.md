# CPU8 architecture

## Overview

CPU8 is an educational **8-bit** CPU with a **von Neumann** architecture (unified memory for code and data). 8-bit address and data buses → **256 bytes** of addressable RAM.

- **Instruction words**: variable (1 byte or 2 bytes)
- **Registers**: A, B, C, D (GPR), PC, SP, IR, operand, flags (Z, C, N, V), register I (IRQ)
- **ALU**: combinational, with ADD/SUB/AND/OR/XOR/CMP/SHL/SHR operations, the immediate variants ADDI/SUBI/CMPI and MUL/DIV
- **Control**: synchronous FSM with 5 states (`FETCH`, `OPR`, `EXEC`, `IRQ`, `HLT`)
- **Stack**: LIFO growing towards lower addresses (see `docs/ISA.md`)
- **Interrupts**: configurable IRQ vector (`IRQ_VECTOR`), handled once per IRQ cycle
- **FPGA support**: iCEstick/iCE40HX1K (see `fpga/top.v`); the design **fits** using 1 BRAM for the memory (~30 % of the HX1K LUTs)

## Datapath

The datapath lives mainly in `rtl/cpu.v`. Key elements:

- **PC** (`rtl/pc.v`): synchronous program counter. Supports `reset`, `inc`, `load`. It is loaded with the jump/RET/IRQ address.
- **Regfile** (`rtl/regfile.v`): bank with 4 registers A,B,C,D. 2 combinational read ports, 1 synchronous write port with `we`.
- **ALU** (`rtl/alu.v`): combinational arithmetic-logic unit. Produces the result and the `Z`, `C`, `N`, `V` flags.
- **RAM** (`rtl/ram.v`): 256x8 memory. **Synchronous** write with `we` and read **registered on the falling edge** (`mem[addr] → rdata`). Because the data is available mid-cycle, the datapath (which registers on `posedge`) sees it in the same cycle, while the memory can be mapped to **BRAM** (SB_RAM40_4K) instead of distributed logic. Supports `$readmemh` in simulation and initialization for FPGA synthesis.
- **Internal registers**: `IR` (instruction register), `operand` (auxiliary byte for 2-byte instructions), `flags` (Z,C,N,V), `SP` (stack pointer), `OUT` (output to LEDs/monitor; the CPU also exposes `out_port`, `in_data` and `in_port` for 4 selectable I/O ports).
- **Buses**: `addr`, `data_in`, `data_out`, control signals from `control.v`.

## Control unit (FSM)

`rtl/control.v` implements a synchronous finite state machine with clock `clk` and `reset`.

**States:**

| State | Name | Description |
|---|---|---|
| `0` | `FETCH` | Read the instruction from `ram[PC]` → load `IR`. Increment `PC`. Decide the length from the fetched byte: 1 byte → `EXEC`, 2 bytes → `OPR`. If `I=1` and `irq=1`, go to `IRQ`. |
| `1` | `OPR` | Read the operand from `ram[PC]` → load `operand`. Increment `PC`. Move to `EXEC`. |
| `2` | `EXEC` | Execute the operation according to the decode (move data, ALU, branches, stack, I/O). Update flags/registers/RAM as appropriate. |
| `3` | `IRQ` | Handle the interrupt: save PC on the stack (PUSH), clear `I`, jump to `IRQ_VECTOR`. Return to FETCH. |
| `4` | `HLT` | Halted state. The CPU stays in HLT until `reset`. |

> The instruction length is decided inside `FETCH` itself with `fetched`
> (the byte just read from `RAM[PC]`), so there is no separate `DECODE` state.
> `fetched` only feeds the (registered) state transition, never `ram_addr`, so no
> combinational control↔RAM loop is formed.


**Priorities** (implicit in the FSM):
- `reset` forces the initial states
- If `irq` is active **and** it is not already being handled, transition to `IRQ` (after completing the appropriate cycle per the design)
- `HLT` stops the CPU (stays in `HLT` until `reset`)

## Typical instruction flow

1. **FETCH**: `IR = RAM[PC]; PC = PC+1`; decide the length (1 byte → `EXEC`, 2 bytes → `OPR`)
2. **OPR** (if 2 bytes): `operand = RAM[PC]; PC = PC+1`
3. **EXEC**: perform the operation, write the results, update the flags
4. The next cycle returns to **FETCH**

## ALU

Implemented in `rtl/alu.v`. Flags:

- **Z (Zero)**: result == 0
- **N (Negative)**: bit 7 of the result set (interpreted as signed)
- **C (Carry)**: carry/borrow out of the 8-bit add/subtract depending on the operation
- **V (Overflow)**: **signed** overflow (two's complement); only for ADD/ADDI/SUB/SUBI/CMP/CMPI and INC/DEC

Supported operations: `ADD`, `SUB`, `AND`, `OR`, `XOR`, `CMP`, `SHL`, `SHR`, `MUL`, `DIV` (`MUL`/`DIV` in phase 9).

> `CMP` is a subtraction that does not store the result (it only updates flags).
> `N` and `V` implement the signed comparisons (`JLT/JGE/JLE/JGT`).

## Stack and subroutines

- **SP** points to the top of the stack. Behaviour defined in `docs/ISA.md`.
- **PUSH** decrements SP and writes the value
- **POP** reads the value and increments SP
- **CALL** saves the return address and jumps
- **RET** recovers the return address from the stack

See `programs/callret.asm`, `programs/stack.asm` with their `.ref`.

## Interrupts (IRQ)

- External signal `irq` raises the request
- Vector configurable by parameter: `cpu #(.IRQ_VECTOR(0x10))` (used in `irq_tb.v`)
- When handled: the current PC is saved on the stack and PC is loaded with `IRQ_VECTOR`
- The implementation avoids handling IRQs repeatedly (a single handling per event, per the `irq_tb.v` test)
- See `programs/irq.asm` and `tb/irq_tb.v`

## Assembler

`asm/assembler.py` is a **2-pass** assembler:

- **Pass 1**: collects labels/symbols
- **Pass 2**: generates bytes with the encoding from `docs/ISA.md`
- Supports mnemonics, immediates (`LDI`/`ADDI`/`SUBI`/`CMPI`), registers, direct addressing `[a]`, register-indirect `[r]`, **indexed** `[r+off]`, labels, `;` comments and unsigned branches/signed `Jcc` (`JLT/JGE/JLE/JGT`, `JVS/JVC/JMI/JPL`)
- Generates `.hex` with hexadecimal bytes (one instruction per line or sequence)

## Verification

- **Modules**: `alu_tb.v`, `pc_tb.v`, `ram_tb.v`, `regfile_tb.v` (includes exhaustive sweeps in the ALU)
- **Programs**: each `programs/*.asm` is assembled, simulated with `cpu_tb.v` and its `OUT` is compared with `programs/*.ref`
- **IRQ**: `irq_tb.v` verifies correct handling
- **Verilator**: `tb/verilator/cpu_sim.v` + `sim_main.cpp` load a `.hex` and compare with the `.ref`
- **Directed**: `cpu_directed_tb.v` covers corner cases (CALL/RET, stack, ported I/O, etc.)
- **Assembler**: `asm/test_assembler.py` (pytest) verifies the instruction-by-instruction encoding; `asm/test_isa_table.py` checks that the ISA table does not drift from the assembler or the disassembler.
- **Differential**: `tools/iss.py` (reference model) is contrasted instruction by
  instruction with the RTL through `tb/cpu_dump_tb.v` (`make difftest`); the
  golden `.ref` files in `programs/` are also reproduced from the model
  (`tools/test_iss.py`). Differential fuzzing additionally covers interrupt
  handling: some of the random programs run with the `irq` signal active and the
  ISS models `S_IRQ` just like the RTL.
- **Lint / docs**: `make lint` (ruff) reviews the Python code and `make docs-check`
  verifies that `docs/OPCODES.md` is up to date with respect to `asm/isa_table.py`.

## Tools (`tools/`)

- **Disassembler** (`tools/disasm.py`): `.hex` → readable assembler listing
  (`make disasm PROG=programs/<name>`). Its output is valid assembler syntax, so
  it can be reassembled (the *round-trip* property tested in
  `tools/test_disasm.py`).
- **Trace debugger** (`tb/cpu_trace_tb.v`): runs a program and prints one line per
  retired instruction with `PC`, `IR`, `A`, `B`, `C`, `D`, `Z`, `C`, `N`, `V` and
  `SP` (`make trace PROG=programs/<name>`).
- **Interactive debugger** (`tools/debugger.py`): steps a `.asm`/`.hex` program on
  the reference model (so it needs no RTL build) with `gdb`-like commands —
  `step`/`next` (which steps *over* a `CALL`), `continue`, `break`, `watch`
  (registers, flags or a memory cell), `mem`, `disasm`, `trace`, `out`, `reset`,
  `labels`. It also reports cycles: it models the 5-state FSM of `rtl/control.v`
  (`FETCH + EXEC` = 2 cycles for 1-byte instructions, `FETCH + OPR + EXEC` = 3 for
  2-byte ones, and 1 cycle per interrupt serviced), so it can be used to measure a
  program's CPI. Usage: `make debug PROG=programs/<name>` or
  `python3 tools/debugger.py programs/<name>.asm`; its tests live in
  `tools/test_debugger.py` (`make pytools`).
- **Regression harness** (`tools/regress.py`): checks that (1) assembly produces
  the same bytes as the golden reference (`tools/golden/hex.sha256`), (2) each
  program's trace matches the golden one (`tools/golden/traces/*.trace`) and
  (3) 200 random programs survive the assemble→disassemble→assemble *round-trip*
  (`make regress`). Regenerate the reference with `make regress-update`.
- **Fuzz** (`tools/fuzz.py`): generator of valid random programs used by the
  harness and the tests.
- **Reference model / ISS** (`tools/iss.py`): functional simulator of the ISA in
  Python (full architectural state: registers, flags, `SP`, `PC`, RAM and I/O
  ports). It is not cycle-accurate, but it replicates the semantics of `rtl/`
  exactly. It can be used directly:
  `python3 tools/iss.py programs/countdown.hex --trace`.
- **Differential fuzzing** (`tools/difftest.py` + `tb/cpu_dump_tb.v`): runs each
  program (the `programs/*.asm` ones and random programs from `tools/fuzz.py`) on
  the RTL and on the ISS and compares the state **after every instruction** (A-D,
  Z/C/N/V, SP, PC, the `OUT` sequence and the final RAM). It is the verification
  that catches bugs the golden traces cannot see (those only prove *stability*,
  not *correctness*). Usage: `make difftest [COUNT=N] [SEED=S] [ONLYPROGS=1]`.
- **ISS tests** (`tools/test_iss.py`): directed micro-tests for the ALU/flags/
  stack/indexing/`Jcc`/ports/IRQ and contrasting the ISS with the golden `.ref`
  files (`make pytools`).
- **ISA table and opcode documentation** (`asm/isa_table.py` + `tools/gen_docs.py`):
  the table is the single source of truth for the ISA; `make docs` regenerates
  `docs/OPCODES.md` and `make docs-check` verifies it is up to date.

## References

- `docs/ISA.md` – Full specification (opcode map, modes, flags, stack, IRQ)
- `rtl/` – RTL implementation
- `tb/` – Testbenches
- `tools/` – Assembler (disassembler), trace, regression, ISS and differential fuzzing
- `programs/` – Examples with references
- `programs/README.md` – Description of the example programs
