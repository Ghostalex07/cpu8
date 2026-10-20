# Contributing guide

Thanks for your interest in CPU8! This document explains how to set up the
environment, how to run the checks and the conventions of the project.

## Getting started

Requirements:

- `iverilog` + `vvp` (simulation)
- `python3` (≥ 3.10) with `pytest`, `ruff` and `verible` (pinned in
  `.github/requirements-ci.txt`)
- Optional: `verilator` (co-simulation) and the FPGA tools (FPGA synthesis):
  `yosys` + `nextpnr-ice40` + `fpga-icestorm` on Debian/Ubuntu (the
  `fpga-icestorm` package is the one providing `icepack`), or
  `pip install yowasp-yosys yowasp-nextpnr-ice40`

```bash
git clone https://github.com/Ghostalex07/cpu8.git
cd cpu8
python3 -m pip install -r ../.github/requirements-ci.txt
```

That file pins `pytest==9.0.2`, `ruff==0.16.1` and `verible==0.0.4071.0`, the
same versions CI uses. Keep the Verible version in sync with the formatter that
produced the sources: `make fmt-check` passes with 0.0.4071.0 (and may report
false diffs with other releases).

The `Makefile` is in `cpu8/`; run the commands from that folder.

## Running the checks

Before submitting changes, run the checks of the **CI test job** (the `fmt`,
`formal`, `fpga` and `coverage` jobs run separately, and `difftest-long` only
runs on the nightly schedule or a manual dispatch):

```bash
cd cpu8
make check
```

Piece by piece:

```bash
make test          # module testbenches + demo programs + interrupts
make vlint         # RTL lint with Verilator -Wall (must stay clean)
make pytools       # pytest: assembler, ISA table, disassembler, ISS, debugger, FPGA report and coverage report
make lint          # ruff over the Python code
make difftest      # differential RTL-vs-reference-model fuzzing (COUNT=150 in CI)
make difftest-long # long fuzz (default COUNT=10000, SEED=...; CI nightly/manual)
make regress       # byte + trace regression + round-trip fuzzing
make verilator     # C++ co-simulation (requires verilator)
make coverage      # Verilator coverage report of the RTL (requires verilator)
make formal        # SymbiYosys proofs of the ALU and the FSM (requires yowasp-yosys + z3)
make fpga          # iCEstick synthesis + bitstream (requires the FPGA tools)
make fpga-check    # fpga + area/timing budget check (tools/fpga_report.py)
make fmt           # format the Verilog sources with Verible (pip install verible==0.0.4071.0)
make fmt-check     # list the files Verible would reformat (CI `fmt` job; green with 0.0.4071.0)
```

If your change intentionally affects assembly you will have to regenerate the
golden reference:

```bash
make regress-update
```

> `programs/*.hex` are regenerated deterministically on every run; **do not**
> compare by modification time, use the `.ref` files / golden traces.

## Conventions

- **Language**: the project is commented and documented in **English** (code
  identifiers may be English or Spanish, but stay consistent with the file you
  edit).
- **Python style**: 100-column lines, `ruff` rules configured in
  `cpu8/ruff.toml`. `make lint` must pass with no warnings.
- **Verilog style**: follow the style of the files in `rtl/` (lowercase signal
  names, block comments with `====` lines). `make vlint` must stay
  **warning-free**.
- **Compatibility**: ISA changes must be **backward-compatible**: the `.hex`
  files of existing programs must not change byte-for-byte. If something has to
  change, also update `tools/golden/` with `make regress-update` and document the
  decision.

## Adding an example program

1. Create `cpu8/programs/<name>.asm` with the code (commented, in English).
2. Add it to the tables in `programs/README.md` and `cpu8/docs/ISA.md` (§9).
3. Assemble it and generate the expected `.ref` output:

   ```bash
   cd cpu8
   python3 asm/assembler.py programs/<name>.asm
   python3 tools/iss.py programs/<name>.hex          # review the OUT sequence
   ```

   The `.ref` file contains one `OUT` byte per line, in hexadecimal (2 digits).
   Generate the `.ref` from the **reference model** (already verified against the
   RTL) to avoid mistakes.
4. Check that RTL and model agree and update the golden reference:

   ```bash
   python3 tools/difftest.py --progs        # must print DIFFERENTIAL: ALL OK
   make test
   make regress-update
   make regress
   ```

   While developing you can step the program instruction by instruction with the
   interactive debugger: `make debug PROG=programs/<name>` (or
   `python3 tools/debugger.py programs/<name>.asm`). It offers breakpoints,
   watchpoints, memory/disassembly dumps and a cycle count.

## Adding or changing instructions

The **single source of truth for the ISA** is `cpu8/asm/isa_table.py`. If you
touch the instruction set:

1. Update the RTL (`rtl/alu.v`, `rtl/control.v`, `rtl/cpu.v`).
2. Update the assembler (`asm/assembler.py`) and the disassembler
   (`tools/disasm.py`).
3. Update `asm/isa_table.py` and regenerate the documentation: `make docs`.
4. Extend the reference model (`tools/iss.py`) — differential fuzzing requires it
   to stay useful.
5. Pass `make check` (it includes `make docs-check`, which fails if the generated
   table is out of date).

## Dependencies and CI

- **Actions are pinned**: every `uses:` in `.github/workflows/ci.yml` references
  a full 40-hex commit SHA with a trailing `# vX.Y.Z` comment. Never replace a
  SHA pin with a moving tag such as `@v5`; let Dependabot update the SHA.
- **Python tools are pinned**: `.github/requirements-ci.txt` pins `pytest`,
  `ruff` and `verible`; the `formal` and `fpga` jobs pin their YoWASP wheels in
  `requirements-formal.txt` / `requirements-fpga.txt`.
- **Dependabot** (`.github/dependabot.yml`) opens weekly, grouped minor/patch
  PRs for `github-actions` and for the pip requirements in `/.github`. Major
  bumps arrive as individual PRs. For a Verible bump, run `make fmt` and commit
  the reformat in the same PR so `fmt-check` stays green.
- `make check` is the CI **test** job only; `fmt`, `formal`, `fpga` and
  `coverage` are separate jobs, and `difftest-long` runs nightly at 03:00 UTC or
  via `workflow_dispatch` with the `long` input.

## Pull requests

- Create a descriptive branch (`feature/...`, `fix/...`).
- Keep CI **green**.
- Fill in the PR template (including a checklist with `make test`, `make vlint`,
  `make pytools` and `make regress`).
