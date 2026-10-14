## Description

<!-- What does this PR change and why? -->

## Type of change

- [ ] Bug fix
- [ ] New feature (ISA, tool, etc.)
- [ ] Refactor / cleanup
- [ ] Documentation
- [ ] CI / infrastructure

## Affected areas

- [ ] RTL (`cpu8/rtl/`)
- [ ] Testbenches (`cpu8/tb/`)
- [ ] Assembler / ISA table (`cpu8/asm/`)
- [ ] Disassembler / ISS / difftest / regress (`cpu8/tools/`)
- [ ] Documentation (`docs/`, `README.md`, …)
- [ ] CI (`.github/workflows/`)

## How it was tested

<!-- Describe the tests performed and paste the relevant output. -->

## Checklist

- [ ] `make test` passes
- [ ] `make vlint` is *warning*-free
- [ ] `make pytools` passes
- [ ] `make regress` passes (and, if assembly was touched, I ran `make regress-update` first)
- [ ] `make difftest` passes (if I touched the RTL or the reference model)
- [ ] `make check` passes locally
- [ ] I have updated the affected documentation (`docs/ISA.md`, `docs/OPCODES.md` with `make docs`, `README.md`, …)
- [ ] The ISA changes are backward-compatible (existing `.hex` files do not change byte-for-byte), or I justify otherwise above

## Notes for the reviewer

<!-- Any detail that helps review the change. -->
