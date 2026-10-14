# Contributing guide

Thanks for your interest in CPU8! This document explains how to set up the
environment, how to run the checks and the conventions of the project.

## Getting started

Requirements:

- `iverilog` + `vvp` (simulation)
- `python3` (≥ 3.10) with `pytest` and `ruff`
- Optional: `verilator` (co-simulation) and
  `yosys` + `nextpnr-ice40` + `icepack` (FPGA synthesis)

```bash
git clone https://github.com/Ghostalex07/cpu8.git
cd cpu8
pip install pytest ruff        # or: python3 -m pip install pytest ruff
```

The `Makefile` is in `cpu8/`; run the commands from that folder.

## Running the checks

Before submitting changes, run the **full suite** (the same one CI runs):

```bash
cd cpu8
make check
```

Piece by piece:

```bash
make test          # module testbenches + demo programs + interrupts
make vlint         # RTL lint with Verilator -Wall (must stay clean)
make pytools       # pytest: assembler, ISA table, disassembler and ISS
make lint          # ruff over the Python code
make difftest      # differential RTL-vs-reference-model fuzzing
make regress       # byte + trace regression + round-trip fuzzing
make verilator     # C++ co-simulation (requires verilator)
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

## Pull requests

- Create a descriptive branch (`feature/...`, `fix/...`).
- Keep CI **green**.
- Fill in the PR template (including a checklist with `make test`, `make vlint`,
  `make pytools` and `make regress`).
