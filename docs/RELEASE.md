# Release process

This page documents the release assets, how to rebuild and verify them, and the
checklist used for a tagged CPU8 release. The first numbered release was
`v1.0.0`; `v1.0.1` adds the Pmod hardware demo and the reproducible-bitstream
check.

## Assets

| Asset | Program | Size | SHA-256 |
|---|---|---|---|
| `top.bin` | `countdown` (default demo) | 32,220 B | `c8e861a9e22afad891c54555bc8a4fdd9827afffd23cef7dd3c96f25e5eb7f1f` |
| `top_pmod.bin` | `pmod` (endless Pmod loop) | 32,220 B | `6f01a07ce1707387ae9e1bf4f791d7d5acff97383bf3bf2d7e867ee9473c3fb0` |

Each bitstream has a matching `.sha256` file. `SHA256SUMS` contains both lines
and can be checked in one command.

`fibonacci.asm` and `euclid.asm` are **not** release bitstreams: they halt, and
the FPGA top turns all LEDs on after `HLT`, so the final value would not be
visible. They remain simulation programs covered by the normal regression.

## Build

From `cpu8/`:

```bash
make release-assets
```

This target:

1. assembles and synthesizes `programs/pmod.asm` → `build/top_pmod.bin`;
2. assembles and synthesizes `programs/countdown.asm` → `build/top.bin`;
3. writes `top.bin.sha256`, `top_pmod.bin.sha256` and `SHA256SUMS` in `build/`.

`countdown` is built last on purpose: `build/top.bin` is the default demo and
must match the committed golden hash in `cpu8/fpga/top.bin.sha256`.

The bitstream depends on the exact RTL, the assembled program image and the
pinned toolchain (yosys 0.69 / nextpnr 0.11 from the YoWASP wheels). Do not
publish a bitstream built with a different toolchain unless the golden hash and
the area/timing report are updated deliberately.

## Verify

From `cpu8/build/`:

```bash
sha256sum -c top.bin.sha256
sha256sum -c top_pmod.bin.sha256
sha256sum -c SHA256SUMS
sha256sum -c ../fpga/top.bin.sha256
```

From a directory with the downloaded release files:

```bash
sha256sum -c SHA256SUMS
```

The CI `fpga` job also runs `sha256sum -c ../fpga/top.bin.sha256` after
`tools/fpga_report.py`, so a pushed commit that changes the countdown bitstream
fails even if it still fits and meets timing.

## Release checklist

1. Start from a clean `main`:
   ```bash
   git status --short          # must be empty
   git pull --ff-only
   ```
2. Run the full verification:
   ```bash
   cd cpu8
   make check
   make fmt-check
   make formal
   make coverage
   make fpga-check
   make fpga-repro
   ```
3. Build the assets and verify them:
   ```bash
   make release-assets
   cd build
   sha256sum -c top.bin.sha256
   sha256sum -c top_pmod.bin.sha256
   sha256sum -c SHA256SUMS
   sha256sum -c ../fpga/top.bin.sha256
   ```
4. Update `CHANGELOG.md`, `README.md` and, if the assets or hashes changed,
   `docs/RELEASE.md`, `docs/FPGA.md` and `cpu8/fpga/top.bin.sha256`.
5. Commit and push `main`.
6. Create an **annotated** tag and push it:
   ```bash
   git tag -a v1.0.1 -m "cpu8 v1.0.1: Pmod demo and reproducible bitstream"
   git push origin main
   git push origin v1.0.1
   ```
7. Create the GitHub release with the assets:
   ```bash
   gh release create v1.0.1 \
     --title "cpu8 v1.0.1" \
     --notes-file /tmp/cpu8-v1.0.1-notes.md \
     cpu8/build/top.bin \
     cpu8/build/top.bin.sha256 \
     cpu8/build/top_pmod.bin \
     cpu8/build/top_pmod.bin.sha256 \
     cpu8/build/SHA256SUMS
   ```
   Mark it as the latest release unless it is a pre-release.
8. Download the published assets into a fresh directory and run
   `sha256sum -c SHA256SUMS` again.
9. Check the CI run for the tagged commit: `test`, `fmt`, `formal`, `fpga` and
   `coverage` must be green. `difftest-long` is expected to be skipped on a
   push; it runs on schedule or manual dispatch.

## Versioning

CPU8 uses semantic versioning for the project and the release assets:

- **patch** (`v1.0.1`): verification, tooling, documentation or a new demo that
  does not change the ISA or the default bitstream;
- **minor** (`v1.1.0`): new instructions, new I/O features or a changed default
  bitstream;
- **major** (`v2.0.0`): incompatible ISA or memory-map changes.

The `v1.0.0` countdown bitstream hash is kept as the golden reference for the
current RTL and toolchain. If a release changes it, update
`cpu8/fpga/top.bin.sha256` and the asset table together.

## Signing

The project currently publishes **checksums only**; no GPG or minisign key is
used. Do not invent or reuse a key you do not control. If signing is added
later, document the public key, the exact command and the verification steps in
this file, and attach the signature next to each asset.

## CI and artifacts

The `fpga` job uploads the countdown bitstream as the `fpga-bitstream` artifact
(30 days). The artifact is convenient for inspection, but the release assets are
built from the tagged commit and verified against the committed hash; do not
publish an artifact whose hash differs from `top.bin.sha256`.

The `coverage` job publishes the annotated Verilator report, and the `test` job
runs the full suite including `top_tb` and `top_pmod_tb`. The formatter, FPGA and
formal dependency pins are deliberately ignored by Dependabot; bump them by
hand with the corresponding checks.
