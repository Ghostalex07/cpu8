# CPU8 — Educational 8-bit CPU in Verilog

[![CI](https://github.com/Ghostalex07/cpu8/actions/workflows/ci.yml/badge.svg)](https://github.com/Ghostalex07/cpu8/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Ghostalex07/cpu8?display_name=tag)](https://github.com/Ghostalex07/cpu8/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

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
- **Control unit** implemented as a **7-state FSM**
  (`FETCH` → `OPR` → (`OPR2`) → `EXEC` (→ `EXEC2` for the 16-bit pair ops), plus
  `IRQ` and `HLT`). The length (1, 2 or 3 bytes) is decided in `FETCH`; there is
  no decode state.
- **ALU** built from a single **9-bit adder** that performs both `ADD` and
  `SUB`/`CMP` (via `a + ~b + 1`), with full flag computation and a carry input for
  `ADC`/`SBC`/`ROL`/`ROR` (and for the high byte of `ADCW`/`SUBW`).
- **Rich instruction set**: load/store (absolute, indexed `[rs+off]` and
  register-indirect), arithmetic and logic, shifts, `INC`/`DEC`, stack
  (`PUSH`/`POP`), subroutines (`CALL`/`RET`), unconditional and conditional
  branches (unsigned and signed/status), **hardware `MUL`/`DIV`**, **port I/O**
  (`IN`/`OUT`), **interrupts** (`EI`/`DI`) and the **`0xFA`-prefixed extended
  instructions** (`NEG`, `NOT`, `ADC`, `SBC`, `SWAP`, `ROL`, `ROR`, `TEST`,
  `PUSHF`, `POPF`, 16-bit `ADCW`/`SUBW` and `LDW`/`STW`).
- **Custom two-pass assembler** with `.org`, `.db`, `.dw` and `.equ` directives.
- **Verification**: module testbenches, per-program output comparison against a
  golden reference (`.ref`), byte/trace hash regression, assemble→disassemble→
  assemble *round-trip*, and **differential fuzzing** that compares the RTL
  against a reference model **after every instruction**.

---

## Quick start

**Requirements**: `iverilog` + `vvp`, `python3` (≥ 3.10), `pytest` and `ruff`.
The versions CI uses are pinned in [`.github/requirements-ci.txt`](.github/requirements-ci.txt);
install them with
`python3 -m pip install -r ../.github/requirements-ci.txt` from `cpu8/`.
Optional: `verilator` (co-simulation) and the FPGA tools (FPGA synthesis). The
FPGA flow looks for `yosys`, `nextpnr-ice40` and `icepack` on the `PATH` and
falls back to the YoWASP wheels, so either install the distro packages (on
Debian/Ubuntu: `yosys`, `nextpnr-ice40` and `fpga-icestorm`, which is the one
that provides `icepack`) or `pip install yowasp-yosys yowasp-nextpnr-ice40`.
Note that the budget in `make fpga-check` was calibrated with the YoWASP
(yosys 0.69 / nextpnr 0.11) tools, the same ones CI pins.

Everything runs from the `cpu8/` folder:

```bash
cd cpu8

make test        # module testbenches + assemble/simulate/compare programs/*.asm
make pytools     # pytest: assembler, ISA table, disassembler, ISS, debugger, FPGA report and coverage report
make vlint       # Verilator -Wall analysis of the RTL (must be clean)
make verilator   # C++ co-simulation of the whole processor
make coverage    # Verilator coverage report of the RTL (line/toggle/FSM)
make formal      # SymbiYosys proofs of the ALU and the FSM
make fpga-check  # FPGA synthesis + area/timing budget
make fpga-repro  # fpga-check + verify the committed bitstream SHA-256
make release-assets  # build the release bitstreams and their checksums
make fpga FPGA_PROG=pmod  # Pmod input demo bitstream (see docs/FPGA.md)
make fmt-check   # check Verilog formatting with Verible 0.0.4071.0
make fmt         # format the Verilog sources with Verible (opt-in)
make difftest    # differential RTL-vs-model fuzzing (COUNT=150 in CI)
make difftest-long  # long fuzz, COUNT=10000 SEED=... (CI nightly/manual)
make regress     # byte + trace regression + round-trip fuzzing
make check       # the CI test job only (fmt, formal, FPGA and coverage are separate)

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
│   ├── ARCHITECTURE.md     # overview of the datapath and the FSM
│   ├── FPGA.md             # iCEstick pinout, flashing and Pmod demo
│   └── RELEASE.md          # release assets, hashes and checklist
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
    │   ├── top_tb.v        # FPGA top-level IN/OUT/HLT test
    │   ├── top_pmod_tb.v   # Pmod loop demo sweep
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
    ├── formal/            # SymbiYosys properties and scripts
    ├── docs/
    │   ├── ISA.md          # instruction set specification
    │   └── OPCODES.md      # opcode table (generated)
    └── fpga/               # iCEstick synthesis flow
        ├── top.v           # board top level (POR, Pmod sync, LEDs)
        ├── icestick.pcf    # pin constraints
        └── top.bin.sha256  # golden hash of the released countdown bitstream
```

---

## The instruction set

The ISA includes:

| Family | Instructions |
|---|---|
| Data | `LDI`, `MOV`, `LD`, `ST` (absolute / indexed / indirect), `NOP` |
| Arithmetic | `ADD`, `ADDI`, `SUB`, `SUBI`, `CMP`, `CMPI`, `INC`, `DEC`, `MUL`, `DIV`, `ADC`, `SBC`, `ADCW`, `SUBW`, `NEG` |
| Logic | `AND`, `OR`, `XOR`, `NOT`, `TEST` |
| Shift/rotate | `SHL`, `SHR`, `ROL`, `ROR` |
| Data (16-bit indexed) | `LDW`, `STW` |
| Stack and register moves | `PUSH`, `POP`, `PUSHF`/`POPF`, `SWAP`/`XCHG`, `JMP`, `CALL`, `RET`, `HLT` |
| Conditional branches | `JZ`/`JNZ`, `JC`/`JNC`, `JLT`/`JGE`/`JLE`/`JGT`, `JVS`/`JVC`/`JMI`/`JPL` |
| System and I/O | `EI`, `DI`, `RETI`, `IN`, `OUT` (register and port `IN n,rd` / `OUT n,rd`) |

- Full, instruction-by-instruction specification: **[`cpu8/docs/ISA.md`](cpu8/docs/ISA.md)**.
- Opcode table (with *bytes*, operands and flags): **[`cpu8/docs/OPCODES.md`](cpu8/docs/OPCODES.md)**,
  generated automatically from `cpu8/asm/isa_table.py` with `make docs`
  (`make docs-check` verifies it is up to date).

---

## Verification

The project relies on several layers of checking, all runnable locally:

- **Module testbenches** (`alu`, `pc`, `ram`, `regfile`, `flag_i`,
  `cpu_directed`, `top` and `top_pmod`), with exhaustive sweeps in the ALU.
- **Example programs**: each `programs/*.asm` is assembled, simulated with
  `cpu_tb.v` and its `OUT` output is compared with `programs/*.ref`.
- **Interrupts**: `irq_tb.v` checks IRQ handling; `RETI` restores the arithmetic
  flags saved on entry.
- **Co-simulation** with Verilator (`make verilator`).
- **Formal verification** (`make formal`): SymbiYosys proves, with the `z3`
  solver, that the ALU matches an exhaustive reference model for every
  operation/operand (result and all four flags) and that the control FSM only
  follows its documented state transitions. The `formal/` directory holds the
  `.sby` and `_fv.sv` files; the job runs in CI too.
- **Coverage** of the RTL with `make coverage`: Verilator instruments a separate
  build (`--coverage`), runs every demo program and merges the runs into an
  annotated report (line, toggle, branch and FSM-state coverage) under
  `build/verilator-cov/`. The target fails if line coverage drops below 95 %
  (`tools/coverage_report.py`); the demo suite currently reaches 100 % (605/605
  lines), with the two unreachable decoder defaults marked by justified
  `coverage_off` pragmas.
- **FPGA synthesis** (`make fpga`): yosys, `nextpnr-ice40` and `icepack` build a
  bitstream for the iCEstick (iCE40HX1K). `make fpga-check` — and a dedicated CI
  job — fails if the design outgrows the area budget or misses the 12 MHz timing
  target (`tools/fpga_report.py`). The job installs the pinned YoWASP wheels
  instead of the distro packages: nextpnr 0.6 places the design at 11.35 MHz and
  then aborts, so the area/timing budget would not be comparable. The iCEstick
  has no user switches: `IN` reads the eight data pins of the Pmod connector
  (with internal pull-ups). `programs/pmod.asm` is an endless `IN A; OUT A; JMP`
  loop that shows the low five bits on the LEDs, so moving the Pmod inputs
  between 3.3 V and GND changes the pattern in real time; with nothing connected
  the pull-ups make it read `0xFF`. `tb/top_tb.v` checks the `IN`/`OUT`/`HLT`
  path and `tb/top_pmod_tb.v` sweeps the loop demo over several input values.
  See [`docs/FPGA.md`](docs/FPGA.md) for the pinout, the 3.3 V limit, the
  flashing commands and the released bitstreams.
- **Reference model (ISS)**: `tools/iss.py` implements the ISA in Python. The
  **differential fuzzing** (`make difftest`, `tools/difftest.py` +
  `tb/cpu_dump_tb.v`) runs each program on the RTL and on the ISS and compares the
  full state **after every instruction** (registers, flags, `SP`, `PC`, `OUT`
  sequence and final RAM). This proves the RTL is *correct*, not merely *stable*.
  The interrupt path is covered too.
- **Interactive debugger** (`tools/debugger.py`): steps a program on the ISS with
  breakpoints, watchpoints, `until <label>` (run to the next visit of an
  address), register/memory dumps and on-the-fly disassembly that
  shows the `.asm` symbols (labels work as breakpoints and appear next to every
  address), and reports a cycle count that models the `control.v` FSM
  (`make debug PROG=programs/<name>`).
- **Golden regression** (`make regress`): hash of the assembled bytes, reference
  traces and assemble→disassemble→assemble *round-trip* of hundreds of random
  programs.
- **Linters**: `make vlint` (Verilator `-Wall` over the RTL) and `make lint` (ruff
  over the Python code).
- **Formatting**: `make fmt-check` lists the Verilog files that would change
  under Verible, and `make fmt` rewrites them in place. The sources are
  formatted with `verible==0.0.4071.0` (the version pinned in
  `.github/requirements-ci.txt`), so `make fmt-check` passes with that release;
  a different Verible version may report spurious diffs. The check is enforced
  by the CI `fmt` job.

All of it runs in **GitHub Actions** on every push and *pull request*
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): the `test` job runs
the test suite (`make check`), `fmt` enforces the Verilog formatting, `formal`
proves the ALU and the FSM with SymbiYosys, `fpga` synthesizes the design,
enforces the area/timing budget, verifies the bitstream SHA-256 against the
committed golden hash and publishes the `fpga-bitstream` artifact (30 days),
and `coverage` enforces the 95 % line-coverage floor and publishes the
annotated report. A `difftest-long` job runs `make difftest-long
COUNT=10000` nightly at 03:00 UTC, or on manual dispatch when the `long` input
is ticked; it never runs on push or pull request.

Every action is pinned to a full commit SHA (with a `# vX.Y.Z` comment) and the
Python tools are pinned in `.github/requirements-ci.txt`. Dependabot
([`.github/dependabot.yml`](.github/dependabot.yml)) opens weekly, grouped
minor/patch PRs for the `github-actions` pins and for `pytest`/`ruff`. The
formatter, FPGA and formal pins are deliberately ignored: they are calibrated
for reproducible formatting, timing and proofs, so they are bumped by hand with
the corresponding checks.

---

## Releases

The latest release ships two iCEstick bitstreams built from this tree:

| Asset | Demo |
|---|---|
| `top.bin` | `countdown` (default demo) |
| `top_pmod.bin` | Pmod input loop (`IN A; OUT A; JMP`) |

Every asset has a matching `.sha256`, and `SHA256SUMS` covers both. The
`fibonacci` and `euclid` programs remain simulation demos: they halt, and the
top turns all LEDs on after `HLT`, so their final value would not be visible on
the board. See
[`docs/RELEASE.md`](docs/RELEASE.md) for the release checklist and the hash
verification, and [`docs/FPGA.md`](docs/FPGA.md) for the Pmod wiring, the
3.3 V limit and the flashing commands.

---

## License

Released under the **MIT** license — see [`LICENSE`](LICENSE).
