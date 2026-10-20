# Changelog

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The project does not publish numbered releases yet, so changes are grouped under
*Unreleased*.

## [Unreleased]

### Added

- **Formal verification** (`make formal`): SymbiYosys + z3 proofs under
  `cpu8/formal/`. `alu.sby` checks `rtl/alu.v` against an exhaustive reference
  model for every operation and operand (result plus the four flags);
  `control.sby` proves that the control FSM never enters the reserved state `7`
  (and recovers to `S_FETCH` if it ever did). A dedicated `formal` CI job installs
  the pinned YoWASP Yosys and `z3-solver` wheels and runs the proofs.
- **`RETI` and flags across interrupts** (`0xFA 0xE0`, Phase 13): the interrupt
  entry saves `C,Z,N,V` in a shadow register and `RETI` pops the return PC (like
  `RET`) and restores them. `I` is deliberately left cleared so a level-triggered
  IRQ cannot re-enter the handler; use `EI` to re-enable interrupts. The
  assembler, disassembler, ISS, ISA table, `programs/irq.asm` and the docs are
  updated; the encoding reuses a previously reserved `0xFA` sub-operation.
- **Assembler stack guard**: the two-pass assembler now rejects an image that
  reaches `0xE0` or beyond. `SP` starts at `0xF0` and `PUSH` decrements it, so the
  last 16 bytes are stack; the error points at the line that crosses the limit
  instead of letting the program corrupt its own stack at run time.
- **`programs/reserved.asm` demo**: runs reserved encodings (`0xE2` and
  `0xFA 0xF0`) and `DI`, proving that they decode as backward-compatible no-ops
  and covering the defensive `default:` branches of `rtl/control.v`. Line
  coverage rises to 99.4 % (513/516); the three remaining lines are unreachable
  defaults (all 16 opcode pages are implemented, the FSM proof rules out state 7)
  and the default hex file of the co-simulation testbench.
- **Coverage floor** (`tools/coverage_report.py`): `make coverage` now fails when
  line coverage drops below 95 %. The CI `coverage` job is no longer
  `continue-on-error`: it enforces the same threshold and still uploads the
  annotated report as an artefact.
- **Verilog formatting** (`make fmt`, `make fmt-check`): optional Verible targets
  (`pip install verible`). `make fmt` rewrites `rtl/`, `tb/` and `fpga/` in place
  and `make fmt-check` lists the files that would change. They stay out of
  `make check` because the existing RTL predates the formatter.
- **Extended ISA with the `0xFA` prefix** (`cpu8/docs/ISA.md` §10.10): `NEG`,
  `NOT`, `ADC`, `SBC`, `SWAP`/`XCHG`, `ROL`, `ROR` (2 bytes) and the 16-bit
  indexed `LDW`/`STW` (3 bytes), all additive and backward compatible. The RTL
  gains an `S_OPR2` FSM state, an `xop` register, a `cin` ALU input and a second
  register-file write port; the assembler, disassembler, ISS, ISA table, tests and
  a new demo `programs/extensions3.asm` cover them. Every existing `.hex` stays
  byte-identical.
- **`0xFA` prefix completed** (`cpu8/docs/ISA.md` §10.10): `TEST` (flags-only
  `AND`), `PUSHF`/`POPF` (flags byte on the stack, bits `C,Z,N,V,I`) and the
  16-bit pair operations `ADCW`/`SUBW` over `A:B` and `C:D`. The pair ops run in
  4 cycles via a new `S_EXEC2` FSM state (7 states in total) with the `c16`/`z16`
  low-byte carry registers. The differential testbenches (`tb/cpu_dump_tb.v`,
  `tb/cpu_trace_tb.v`) were fixed to retire instructions in the *last* execution
  state instead of always in `EXEC`, which captured 2-cycle pair operations
  mid-instruction. New demo `programs/extensions4.asm` (25 outputs) with golden
  trace; all existing `.hex` files remain byte-identical.
- **`.dw` directive** in the two-pass assembler: emits 16-bit little-endian
  words (numbers, labels or constants, two bytes per item; strings are
  rejected). Both passes, the 16-bit range checks and new tests in
  `cpu8/asm/test_assembler.py` cover it.
- **Debugger symbols** (`cpu8/tools/debugger.py`): every printed address is
  annotated with its `.asm` label (breakpoint confirmations, `bl`, the `PC=` in
  `regs` and the `trace` rows); `break <label>`, `disasm <label>` and
  `watch @label` already resolved symbols.
- **Debugger `until`** (`cpu8/tools/debugger.py`): `until <address|label>` runs
  the program until the PC reaches that address again (at least one instruction
  is always executed, so `until loop` from the loop head stops on the next
  iteration); it also stops on `HLT`, on a breakpoint or at the step limit, and
  accepts `u` as a short form.
- **`programs/logic.asm` demo**: exercises the bitwise group (`OR`, `XOR`) and the
  shifts (`SHL`, `SHR`) plus `ROL`/`ROR` *through the carry* flag, which until now
  were only reached by the ALU unit tests. 15 outputs with their `.ref` and golden
  trace; the line coverage of `make coverage` rises to 98.6 %.
- **RTL coverage with Verilator** (`make coverage`): builds a separate
  instrumented model (`--coverage`; `-Wno-COVERIGN` is added only when the
  installed Verilator understands it), runs every demo program with `+cov=<file>`
  and merges the runs into an annotated report under `build/verilator-cov/`
  (line, toggle, branch, expression and FSM-state coverage).
  `tb/verilator/sim_main.cpp` writes the coverage file at exit when built with
  coverage (guarded by `VM_COVERAGE`); it uses its own `+cov=` plusarg because
  Verilator <= 5.020 rejects `+verilator+coverage+file+` as an unknown runtime
  argument.
- **FPGA timing/area check in CI**: a dedicated `fpga` GitHub Actions job installs
  the pinned YoWASP iCE40 toolchain (yosys 0.69 / nextpnr 0.11, which is what the
  design is calibrated with — the distro nextpnr 0.6 places the design at 11.35 MHz
  and aborts before the check even runs), runs `make fpga` on the iCE40HX1K and
  then `cpu8/tools/fpga_report.py`, which fails the build if the design exceeds
  80 % of the logic cells or misses the 12 MHz timing target (currently 826/1280
  LCs, ~14.9 MHz). `make fpga-check` runs the same check locally. The Makefile now
  also finds `nextpnr-ice40` and `icepack` from YoWASP on the `PATH`.
- **CI caching and artefacts**: pip caching keyed on
  `.github/requirements-ci.txt` / `.github/requirements-fpga.txt` so the FPGA job
  no longer re-downloads the ~85 MB YoWASP toolchain on every run; a failing
  `fpga` job uploads its `build/fpga.log`, and the `coverage` job enforces the
  95 % line floor and publishes the annotated RTL coverage report as an artefact. The
  workflow also cancels superseded runs on non-`main` branches.
- **ISA table as the single source of truth** (`cpu8/asm/isa_table.py`,
  *machine-readable*): a declarative description of every instruction (operand
  forms, opcode page, length, bytes, flags and description).
  `cpu8/tools/gen_docs.py` generates `cpu8/docs/OPCODES.md` from it, and
  `cpu8/asm/test_isa_table.py` checks that it does not drift from the real
  assembler or disassembler.
- **Interrupt coverage in differential fuzzing**: `tb/cpu_dump_tb.v` accepts
  `+irq=N`, `tools/iss.py` models interrupt handling (`irq_at` / `take_irq`) and
  `tools/difftest.py` runs some of the random programs with `irq` active
  (`--irq-prob`).
- **New example programs**: `euclid.asm` (GCD via Euclid's algorithm with
  `DIV`/`MUL`), `factorial.asm` (iterative factorial with `MUL`), `primes.asm`
  (primes by trial division) and `sort.asm` (*bubble sort* with the `.db`
  directive), with their `.ref` files and golden traces.
- **Interactive debugger** (`cpu8/tools/debugger.py`): steps a program on the
  reference model with `gdb`-like commands (breakpoints, watchpoints, register and
  memory dumps, on-the-fly disassembly) and a cycle count that models the FSM of
  `rtl/control.v`. Available as `make debug PROG=programs/<name>`; tested by
  `cpu8/tools/test_debugger.py`.
- **Quality tooling**: `ruff` configuration (`cpu8/ruff.toml`) and the `make lint`,
  `make docs`, `make docs-check` and `make check` targets.
- **CI**: Python lint (ruff) and a check that the opcode documentation is up to
  date (`make docs-check`).
- **Documentation**: root `README.md`, `CONTRIBUTING.md`, this `CHANGELOG.md`,
  *issue* and *pull request* templates, and `.gitattributes`.

### Changed

- `make pytools` now includes the ISA table tests and the debugger tests.

### Fixed

- `tools/regress.py`: removed ambiguous names (`E741`) flagged by `ruff`.

## Earlier milestones

Throughout development, the project grew in phases:

- The **RTL**: datapath, ALU built on a single 9-bit adder, control FSM (7 states),
  register file, program counter and unified memory.
- The two-pass **assembler** and the **disassembler** (exact *round-trip*).
- **Stack and subroutines** (`PUSH`/`POP`, `CALL`/`RET`) and **interrupts**
  (`EI`/`DI`, configurable vector).
- **Indexed and indirect addressing** and **flag V** with signed branches.
- **Hardware `MUL`/`DIV`** and **port I/O** (`IN`/`OUT`).
- **Extended instructions** behind the `0xFA` prefix (`NEG`/`NOT`/`ADC`/`SBC`/
  `SWAP`/`ROL`/`ROR`/`TEST`/`PUSHF`/`POPF`, 16-bit `ADCW`/`SUBW` and `LDW`/`STW`).
- The **FPGA synthesis flow** for iCEstick (iCE40HX1K).
- The **verification tools**: trace *debugger*, regression *harness* and
  differential RTL-vs-model *fuzzing*.
- **Continuous integration** on GitHub Actions.
