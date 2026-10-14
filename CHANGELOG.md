# Changelog

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The project does not publish numbered releases yet, so changes are grouped under
*Unreleased*.

## [Unreleased]

### Added

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
- **Quality tooling**: `ruff` configuration (`cpu8/ruff.toml`) and the `make lint`,
  `make docs`, `make docs-check` and `make check` targets.
- **CI**: Python lint (ruff) and a check that the opcode documentation is up to
  date (`make docs-check`).
- **Documentation**: root `README.md`, `CONTRIBUTING.md`, this `CHANGELOG.md`,
  *issue* and *pull request* templates, and `.gitattributes`.

### Changed

- `make pytools` now includes the ISA table tests.

### Fixed

- `tools/regress.py`: removed ambiguous names (`E741`) flagged by `ruff`.

## Earlier milestones

Throughout development, the project grew in phases:

- The **RTL**: datapath, ALU built on a single 9-bit adder, 5-state control FSM,
  register file, program counter and unified memory.
- The two-pass **assembler** and the **disassembler** (exact *round-trip*).
- **Stack and subroutines** (`PUSH`/`POP`, `CALL`/`RET`) and **interrupts**
  (`EI`/`DI`, configurable vector).
- **Indexed and indirect addressing** and **flag V** with signed branches.
- **Hardware `MUL`/`DIV`** and **port I/O** (`IN`/`OUT`).
- The **FPGA synthesis flow** for iCEstick (iCE40HX1K).
- The **verification tools**: trace *debugger*, regression *harness* and
  differential RTL-vs-model *fuzzing*.
- **Continuous integration** on GitHub Actions.
