# CPU8 — Educational 8-bit CPU in Verilog

[![CI](https://github.com/Ghostalex07/cpu8/actions/workflows/ci.yml/badge.svg)](https://github.com/Ghostalex07/cpu8/actions/workflows/ci.yml)

CPU8 is an **8-bit von Neumann CPU** written in synthesizable Verilog, designed as
a **complete educational project**: not only the processor (RTL), but also its
**assembler**, its **disassembler**, a **reference simulator** in Python and a
**verification** system (testbenches, golden regression and differential
RTL-vs-model *fuzzing*).

It fits on a small FPGA (synthesis proven for the **iCEstick / iCE40HX1K**) and
can run entirely **without hardware**, using `iverilog` and/or `verilator`.

---

## Features

- **von Neumann architecture**: a single **256-byte** memory shared by program and
  data, an 8-bit address bus and an 8-bit data bus.
- **Registers**: `A`, `B`, `C`, `D` (8 bits) and, inside the CPU, `PC`, `SP`,
  `IR`, `operand` and the flags **Z** (zero), **C** (carry/no-*borrow*), **N**
  (negative), **V** (signed overflow) and **I** (interrupts).
- **Control unit** implemented as a **5-state FSM**
  (`FETCH` → `OPR` → `EXEC`, plus `IRQ` and `HLT`). The length (1 or 2 bytes) is
  decided in `FETCH`; there is no decode state.
- **ALU** built from a single **9-bit adder** that performs both `ADD` and
  `SUB`/`CMP` (via `a + ~b + 1`), with full flag computation.
- **Rich instruction set**: load/store (absolute, indexed `[rs+off]` and
  register-indirect), arithmetic and logic, shifts, `INC`/`DEC`, stack
  (`PUSH`/`POP`), subroutines (`CALL`/`RET`), unconditional and conditional
  branches (unsigned and signed/status), **hardware `MUL`/`DIV`**, **port I/O**
  (`IN`/`OUT`) and **interrupts** (`EI`/`DI`).
- **Custom two-pass assembler** with `.org`, `.db` and `.equ` directives.
- **Verification**: module testbenches, per-program output comparison against a
  golden reference (`.ref`), byte/trace hash regression, assemble→disassemble→
  assemble *round-trip*, and **differential fuzzing** that compares the RTL
  against a reference model **after every instruction**.

---

## Quick start

**Requirements**: `iverilog` + `vvp`, `python3` (≥ 3.10), `pytest` and `ruff`.
Optional: `verilator` (co-simulation) and `yosys` + `nextpnr-ice40` + `icepack`
(FPGA synthesis).

Everything runs from the `cpu8/` folder:

```bash
cd cpu8

make test        # module testbenches + assemble/simulate/compare programs/*.asm
make pytools     # pytest: assembler, ISA table, disassembler, ISS model and debugger
make vlint       # Verilator -Wall analysis of the RTL (must be clean)
make verilator   # C++ co-simulation of the whole processor
make difftest    # differential RTL-vs-model fuzzing
make regress     # byte + trace regression + round-trip fuzzing
make check       # all of the above (the same suite CI runs)

make sim  PROG=programs/countdown   # simulate a program (compares with its .ref)
make wave PROG=programs/countdown   # same, and opens GTKWave
make trace PROG=programs/countdown  # trace: one line per retired instruction
make disasm PROG=programs/countdown # disassemble the .hex into a listing
make debug PROG=programs/countdown  # interactive debugger: step/breakpoints/watch
```

`make help` shows the full list of targets.

---

## Repository layout

```
.
├── README.md               # this file
├── CONTRIBUTING.md         # contribution guide
├── CHANGELOG.md            # change history
├── LICENSE                 # MIT license
├── docs/
│   └── ARCHITECTURE.md     # overview of the datapath and the FSM
├── programs/
│   └── README.md           # description of the example programs
└── cpu8/                   # the project (Makefile and everything else)
    ├── Makefile
    ├── ruff.toml           # Python linter configuration
    ├── rtl/                # synthesizable Verilog
    │   ├── cpu.v           # instantiates the datapath
    │   ├── control.v       # control FSM
    │   ├── alu.v           # ALU (9-bit adder)
    │   ├── regfile.v       # A-D register file
    │   ├── pc.v            # program counter
    │   └── ram.v           # unified memory (BRAM)
    ├── tb/                 # testbenches
    │   ├── cpu_tb.v        # simulates a program and compares with .ref
    │   ├── cpu_dump_tb.v   # per-instruction dump (differential fuzzing)
    │   ├── cpu_trace_tb.v  # human-readable per-instruction trace
    │   ├── irq_tb.v        # interrupt test
    │   ├── *_tb.v          # module testbenches
    │   └── verilator/      # C++ co-simulation
    ├── asm/
    │   ├── assembler.py    # 2-pass assembler
    │   └── isa_table.py    # single (machine-readable) source of truth for the ISA
    ├── programs/           # .asm demos (+ generated .hex and .ref)
    ├── tools/
    │   ├── disasm.py       # disassembler
    │   ├── debugger.py     # interactive debugger (step/breakpoints/watch)
    │   ├── iss.py          # Python reference model (ISS)
    │   ├── difftest.py     # differential RTL-vs-ISS fuzzing
    │   ├── regress.py      # golden regression
    │   ├── fuzz.py         # random program generator
    │   ├── gen_docs.py     # generates docs/OPCODES.md from isa_table.py
    │   └── golden/         # golden references (bytes and traces)
    ├── docs/
    │   ├── ISA.md          # instruction set specification
    │   └── OPCODES.md      # opcode table (generated)
    └── fpga/               # iCEstick synthesis flow
```

---

## The instruction set

The ISA includes:

| Family | Instructions |
|---|---|
| Data | `LDI`, `MOV`, `LD`, `ST` (absolute / indexed / indirect) |
| Arithmetic | `ADD`, `ADDI`, `SUB`, `SUBI`, `CMP`, `CMPI`, `INC`, `DEC`, `MUL`, `DIV` |
| Logic | `AND`, `OR`, `XOR` |
| Shift | `SHL`, `SHR` |
| Stack and control | `PUSH`, `POP`, `JMP`, `CALL`, `RET`, `HLT` |
| Conditional branches | `JZ`/`JNZ`, `JC`/`JNC`, `JLT`/`JGE`/`JLE`/`JGT`, `JVS`/`JVC`/`JMI`/`JPL` |
| System and I/O | `EI`, `DI`, `IN`, `OUT` (register and port `IN n,rd` / `OUT n,rd`) |

- Full, instruction-by-instruction specification: **[`cpu8/docs/ISA.md`](cpu8/docs/ISA.md)**.
- Opcode table (with *bytes*, operands and flags): **[`cpu8/docs/OPCODES.md`](cpu8/docs/OPCODES.md)**,
  generated automatically from `cpu8/asm/isa_table.py` with `make docs`
  (`make docs-check` verifies it is up to date).

---

## Verification

The project relies on several layers of checking, all runnable locally:

- **Module testbenches** (`alu`, `pc`, `ram`, `regfile`), with exhaustive sweeps
  in the ALU.
- **Example programs**: each `programs/*.asm` is assembled, simulated with
  `cpu_tb.v` and its `OUT` output is compared with `programs/*.ref`.
- **Interrupts**: `irq_tb.v` checks IRQ handling.
- **Co-simulation** with Verilator (`make verilator`).
- **Reference model (ISS)**: `tools/iss.py` implements the ISA in Python. The
  **differential fuzzing** (`make difftest`, `tools/difftest.py` +
  `tb/cpu_dump_tb.v`) runs each program on the RTL and on the ISS and compares the
  full state **after every instruction** (registers, flags, `SP`, `PC`, `OUT`
  sequence and final RAM). This proves the RTL is *correct*, not merely *stable*.
  The interrupt path is covered too.
- **Interactive debugger** (`tools/debugger.py`): steps a program on the ISS with
  breakpoints, watchpoints, register/memory dumps and on-the-fly disassembly, and
  reports a cycle count that models the `control.v` FSM
  (`make debug PROG=programs/<name>`).
- **Golden regression** (`make regress`): hash of the assembled bytes, reference
  traces and assemble→disassemble→assemble *round-trip* of hundreds of random
  programs.
- **Linters**: `make vlint` (Verilator `-Wall` over the RTL) and `make lint` (ruff
  over the Python code).

All of it runs in **GitHub Actions** on every push and *pull request*
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

---

## License

Released under the **MIT** license — see [`LICENSE`](LICENSE).
