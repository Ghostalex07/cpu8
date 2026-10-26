# Changelog

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Changes are grouped under *Unreleased* until a tag is cut.

## [Unreleased]

## [1.0.2] - 2026-10-22

### Added

- **IN wait state (`S_IN`)**: the input handshake now holds `in_port` from the
  operand fetch (or from `S_EXEC` for the 1-byte form) and samples `in_data` one
  cycle later. An external decoder plus the two-FF synchronizer in
  `fpga/top.v` therefore sees a stable port for at least two clock edges.
  `IN rd` takes 3 cycles and `IN n,rd` takes 4; the ISA, FSM table, debugger
  cycle model and formal properties are updated. `tb/top_in_tb.v` drives
  `pmod_in` combinationally from `dut.in_port` and fails on the old RTL.
- **Wrap-around programs**: `stack_wrap.asm` pushes across the SP `0x00 -> 0xFF`
  wrap, and `pc_wrap.asm` executes a 2-byte instruction at `0xFE` so the
  operand fetch wraps PC `0xFF -> 0x00`. Both have golden traces and `.ref`
  files, and the fuzzer round-trips them.
- **`.nostack` directive**: lets an image extend into the stack area when the
  program provably never uses the stack (required by the wrap tests).
- **Interrupt state in the dump**: `cpu_dump_tb.v`, the ISS, the debugger and
  the differential fuzzer now expose `flag_i` and the saved `C/Z/N/V` snapshot.
- **Formal BMC for the PC and register file** (`formal/pc.sby`,
  `formal/regfile.sby`), covering reset, load/write priority, increment and
  hold without hierarchical references.
- **Branch coverage budget**: `coverage_report.py` parses `BRDA` records and
  enforces a 95.5 % floor in addition to the 95 % line floor; `make coverage`
  enables every Verilator metric.
- **Directed tests**: reset from `S_HLT`, IRQ deassert/reassert, `RETI` in the
  fuzzer's no-operand list, and mutual-exclusion assertions between RAM/register
  writes, OUT, PC load/inc and SP inc/dec.

### Changed

- **SBC documentation and tests**: SBC subtracts the incoming no-borrow `C`
  directly (`rd - rs - C`, x86 convention), not the 6502 `rd - rs - (1 - C)`.
  The prose now states that two SBCs do not chain a borrow; use `SUBW` or handle
  it explicitly. New ISS tests cover borrow, ADCW and SUBW chaining.
- **ALU timing**: a dedicated `y_addr` adder drives `ram_addr`, removing the
  multiplier/divider from the LDW/STW address cone. nextpnr is constrained to
  16 MHz; the current build uses 870/1280 LCs (68 %) and reaches 25.45 MHz.
  Both release bitstream hashes are regenerated.
- **Assembler expressions and errors**: 16-bit `.equ` constants, `term +/- term`
  expressions in immediates, addresses and `.org`, `[label+3]` indexing, range
  checks with the offending expression, source-line context in errors, and
  removal of a stale `.hex` when assembly fails.
- **Tooling UX**: the ISS accepts `--irq`/`--irq-vector` and warns when the step
  limit is reached; the debugger counts an IRQ as 2 cycles, follows CALL in
  `next`, and treats watch names case-insensitively; `regress --update`
  assembles fresh images and refuses to save stale traces; `difftest` reports a
  missing iverilog clearly and labels whether an IRQ was actually taken;
  `fuzz` computes lengths through the assembler.

### Fixed

- Debugger `disasm`/`delete` argument validation, and an obsolete five-state /
  one-cycle interrupt description in the docs.
- Coverage instrumentation of structurally unreachable reserved flag bits and
  decoder states.

## [1.0.1] - 2026-10-21

### Added

- **Pmod hardware demo** (`programs/pmod.asm`): endless `IN A; OUT A; JMP` loop
  that shows the low five bits of the Pmod byte on the iCEstick LEDs. It is
  excluded from the halt-based program regression, differential fuzzing and
  golden traces; `tb/top_pmod_tb.v` loads its image and sweeps `0x00`, `0xFF`,
  `0x55`, `0xAA`, every single-bit value, `0xA5` and `0x5A`.
- **`make fpga-repro`** and `fpga/top.bin.sha256`: rebuild the default bitstream
  and verify its SHA-256 against a committed golden hash. The CI `fpga` job runs
  the same check after the area/timing report, so RTL or toolchain drift is
  caught even when the design still fits.
- **`make release-assets`**: build the two published bitstreams (`countdown`
  and `pmod`), write one `.sha256` per asset and a combined `SHA256SUMS` file.
  The default `build/top.bin` is the countdown demo. The halting `fibonacci`
  and `euclid` programs stay simulation-only: the top turns all LEDs on after
  `HLT`, so their final value would not be visible on the board.
- **`docs/FPGA.md` and `docs/RELEASE.md`**: iCEstick pinout, 3.3 V warning,
  flashing commands, Pmod demo behavior, release asset list, checksum
  verification and the release checklist. The README gains release/license
  badges and a Releases section.
- **Extra release asset**: `top_pmod.bin` joins `top.bin`, each with a checksum.

### Changed

- **Dependabot** now ignores the calibrated `verible`, `yowasp-yosys`,
  `yowasp-nextpnr-ice40` and `z3-solver` pins; only `pytest` and `ruff` update
  automatically. The FPGA/formal/formatting pins are bumped by hand after the
  corresponding checks, so an automatic Yosys bump cannot silently change the
  bitstream or the proofs.
- **README**: the Pmod instructions now point at `programs/pmod.asm` instead of
  the testbench-oriented `inout.asm`, coverage is documented as 100 % (605/605)
  and the new FPGA/release commands and documents are linked.

## [1.0.0] - 2026-10-20

### Added

- **Conditional breakpoints** (`tools/debugger.py`): `break <addr|label> if
  <expr>` stops only when the expression holds. The grammar covers registers
  `A`-`D`, `SP`/`PC`, the flags `CF`/`ZF`/`NF`/`VF`/`IF` (the `fC`/... forms are
  accepted too), memory cells (`@0x40`, `@label`), decimal/hex literals,
  `== != < <= > >=`, `&&`, `||` and parentheses. A small recursive-descent
  parser compiles the expression; nothing is passed to Python `eval`. An invalid
  condition is rejected without touching the existing breakpoint, and
  `delete`/`clear` remove the condition with the address. `break` without
  arguments and `bl` list every breakpoint with its expression.
- **`tb/flag_i_tb.v`**: directed RTL test of the interrupt flag. `DI` before an
  interrupt request suppresses the handler, `EI` re-enables it, `PUSHF`/`POPF`
  round-trip the `I` bit and `RETI` leaves it cleared; the testbench embeds a
  program, raises the IRQ after the first `OUT` and expects `1, 2, 255`.
  `tools/test_iss.py` gains nine matching ISS tests (`EI`, `DI`, `PUSHF`,
  `POPF`, `RETI` and the IRQ entry), so the reference model and the RTL agree on
  the flag.
- **FSM formal properties** (`formal/control.sby`, `formal/control_fv.sv`):
  BMC at depth 12 with the flattened FSM state wired to observation wires
  (`connect -set`). The properties cover the synchronous reset, the seven legal
  encodings, `S_HLT` stuttering until reset, the legal transition set of every
  state, interrupt entry only from `S_FETCH` with `flag_i && irq`, the
  interrupt-cycle actions and the mutual exclusion of the control outputs.
- **Cover trace** (`formal/control_cover.sby`): SymbiYosys strips `$cover`
  cells in `bmc` mode, so a separate `mode cover` run at depth 12 checks that
  all seven states, the interesting transitions and a stack operation are
  reachable with the same harness.
- **`make difftest-long`**: long differential fuzz (`COUNT=10000`, `SEED=1` by
  default). The nightly CI job runs it at 03:00 UTC with the run number as the
  seed; a manual `workflow_dispatch` can request it with the `long` input. The
  regular `test` job keeps the 150-program run.
- **CI `fmt` job**: `make fmt-check` is now enforced on every push/PR in its own
  fast job, with the pinned `verible==0.0.4071.0`. The `fpga` job publishes the
  bitstream as the `fpga-bitstream` artifact (30 days, `if-no-files-found:
  error`).
- **Dependabot** (`.github/dependabot.yml`): weekly grouped minor/patch PRs for
  the `github-actions` pins and for the pip requirements in `.github/`; major
  bumps arrive as individual PRs.
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
  coverage reaches **100 % (605/605)**: the two remaining unreachable defaults
  are marked with justified `coverage_off` pragmas, and the coverage floor is
  still enforced at 95 %.
- **Coverage floor** (`tools/coverage_report.py`): `make coverage` now fails when
  line coverage drops below 95 %. The CI `coverage` job is no longer
  `continue-on-error`: it enforces the same threshold and still uploads the
  annotated report as an artefact.
- **Verilog formatting** (`make fmt`, `make fmt-check`): optional Verible targets
  (`pip install verible==0.0.4071.0`). `make fmt` rewrites `rtl/`, `tb/` and
  `fpga/` in place and `make fmt-check` lists the files that would change. They
  stay out of `make check` (which mirrors the CI `test` job) but the dedicated
  `fmt` CI job enforces `fmt-check`.
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
  80 % of the logic cells or misses the 12 MHz timing target (currently 862/1280
  LCs, ~12.8 MHz). `make fpga-check` runs the same check locally. The Makefile now
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
- **FPGA input bus**: the iCEstick has no user switches, so `fpga/top.v` wires
  the eight data pins of the Pmod connector to the CPU `in_data` bus through a
  two-flip-flop synchronizer (the PCF enables the internal pull-ups).
  `cpu8/tb/top_tb.v` checks the `IN`/`OUT` path end to end.

### Changed

- `make fmt-check` is no longer optional: a `fmt` CI job enforces it, and the
  RTL, testbenches and FPGA sources were reformatted in place with Verible
  0.0.4071.0 so a fresh checkout is green. Run `make fmt` after bumping
  Verible, since another release may produce different output.
- CI dependencies and Actions are pinned for reproducibility:
  `.github/requirements-ci.txt` pins `pytest==9.0.2`, `ruff==0.16.1` and
  `verible==0.0.4071.0`, and every `uses:` references a full commit SHA with a
  `# vX.Y.Z` comment (Dependabot maintains both).
- `make pytools` now collects every test under `asm/` and `tools/` instead of a
  hard-coded list, so a new `test_*.py` runs in CI without editing the Makefile.
- `make clean` also removes every `formal/*/` work directory and the generated
  `fpga/program.hex`; `V_FILES` includes `tb/verilator/cpu_sim.v` so `make fmt`
  and `make fmt-check` cover the co-simulation harness too.
- The CI `test` job uploads `build/difftest-fallos/` and `build/regress/` when it
  fails, and the workflow declares `permissions: contents: read` plus
  `workflow_dispatch`.
- Documentation: the ISA now describes the reserved-encoding aliases (Jcc family
  `11`, ignored `SHL`/`SHR` and `JMP` bits), HLT vs. a pending interrupt, the
  shared `in_port` bus during `OUT n,rd` and the 8-bit `SP` wrap; INC/DEC are
  documented as updating `V`; instruction words are 1, 2 or 3 bytes; `.ref`
  files are described as the complete output sequence.

### Fixed

- `make fmt-check` inspected nothing: it piped the file list to Verible's
  stdin, and the formatter ignored those names and produced no output, so the
  target passed even with unformatted sources. It now passes the files as
  arguments and fails on the first diff.
- `rtl/ram.v`: a synchronous reset no longer commits a pending write (ST, PUSH,
  CALL, PUSHF, STW or the interrupt push landed in RAM on the reset edge).
- The FPGA build now uses the full 256-byte RAM (the `FPGA_RAM64` variant
  aliased every address modulo 64, moved `SP` to `0x3F` and silently truncated
  programs longer than 64 bytes). A fresh build uses 862/1280 LCs at 12.81 MHz.
- `tools/disasm.py`: an image ending in a conditional jump no longer raises
  `IndexError`; reserved and aliased encodings disassemble to `.db` so the
  round trip is byte-identical; truncated instructions are emitted as bytes;
  jump targets that do not start an instruction no longer produce undefined
  labels; `main` exits with status 2 on bad input.
- `asm/assembler.py`: `.db "a; b"` keeps the semicolon inside the string; a
  label and a constant can no longer share a name silently; a constant named
  like a register (`[B]`) is treated as a direct address, consistently with
  immediates; `.org` now applies the 256-byte and stack-margin checks.
- `tools/debugger.py`: watchpoints are checked on the interrupt cycle; `-e`
  returns a non-zero status when a command fails; out-of-range addresses and
  non-positive counts are rejected; `until 08` accepts decimal addresses with
  leading zeros.
- `tools/iss.py`: `_leer_hex` ignores `;`/`//` comments and the CLI reports a
  missing file or a bad `--max` with status 2.
- `tools/difftest.py`: a demo program that does not assemble is a failure (it
  used to be a silent SKIP with exit status 0), a generated program that does
  not assemble is reported instead of crashing, the failure directory is cleaned
  at the start and a run with nothing tested is not reported as OK.
- `tools/coverage_report.py`: `--min nan`/`inf` is rejected instead of always
  passing or always failing; `tools/regress.py` reports a missing `--fuzz`
  value with status 2.
- Testbenches: `cpu_tb` no longer prints `ALL TESTS PASSED` when no `+exp` list
  was loaded, `irq_tb` uses the same policy instead of failing a run without a
  reference, and the Verilator harness returns 1 when `+exp` is unreadable or
  empty. `make verilator`/`make coverage` now require a `.ref` for every demo.
- `cpu8/cpu.gtkw` uses a relative dump path and selects `state[2:0]`/`nstate[2:0]`
  (7-state FSM).
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
