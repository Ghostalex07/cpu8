# iCEstick FPGA flow

This page covers the iCEstick implementation of CPU8: pinout, bitstream
generation, flashing, the Pmod input and the demos that are useful on real
hardware.

## Board and top level

The target is the **iCEstick** (Lattice iCE40HX1K-TQ144, 12 MHz clock, 5 LEDs
and one 2x6 Pmod connector). The board has no user switches, so the eight data
pins of the Pmod connector are the CPU input bus. The second FT2232H channel is
wired straight to the FPGA and is used as the console UART (FPGA pin 8 = TX,
pin 9 = RX).

`cpu8/fpga/top.v` instantiates the CPU and provides:

- a **power-on reset** that holds `rst` high for the first 8 clock cycles;
- a **two-flip-flop synchronizer** for the asynchronous Pmod inputs
  (`in_meta` → `in_sync` → `in_data`), initialized to `0xFF`;
- the **5 LEDs**: while the CPU runs they show the last value written to
  port 0; after `HLT` they all turn on;
- a **program image** loaded at synthesis time: `make fpga` assembles
  `programs/<FPGA_PROG>.asm`, copies it to `cpu8/fpga/program.hex`, and Yosys
  reads it through `$readmemh` under `-DRAM_INIT` into the 256-byte RAM.
- a **console** on the second FT2232H channel: `uart_tx` (FPGA pin 8) and
  `uart_rx` (FPGA pin 9), 115200 8N1, exposed on the host as `/dev/ttyUSB1`;
- a **programmable timer** whose output drives the CPU interrupt line;
- a small **I/O decoder** that maps the four CPU ports to peripherals:
  - port 0: `OUT` → LEDs, `IN` → Pmod byte;
  - port 1: `OUT` → start a UART transmission, `IN` → last byte received (read
    acknowledges `rx_ready`);
  - port 2: `OUT` → timer period in milliseconds (0 disables and clears the
    interrupt), `IN` → bit 0: interrupt pending;
  - port 3: `IN` → console status (bit 0 `rx_ready`, bit 1 `tx_busy`,
    bit 2 `rx_overrun`, bit 3 `rx_busy`); `OUT` is ignored.

## Pinout

### Clock and LEDs

| Signal | FPGA pin | Board |
|---|---|---|
| `clk` | 21 | 12 MHz oscillator |
| `led[0]` | 95 | D1 |
| `led[1]` | 96 | D2 |
| `led[2]` | 97 | D3 |
| `led[3]` | 98 | D4 |
| `led[4]` | 99 | D5 |

### Pmod connector J2

| J2 pin | Signal | FPGA pin |
|---|---|---|
| 1 | `pmod_in[0]` | 78 |
| 2 | `pmod_in[1]` | 79 |
| 3 | `pmod_in[2]` | 80 |
| 4 | `pmod_in[3]` | 81 |
| 5 | GND | — |
| 6 | VCC (3.3 V) | — |
| 7 | `pmod_in[4]` | 87 |
| 8 | `pmod_in[5]` | 88 |
| 9 | `pmod_in[6]` | 90 |
| 10 | `pmod_in[7]` | 91 |
| 11 | GND | — |
| 12 | VCC (3.3 V) | — |

### UART (second FT2232H channel)

| Signal | FPGA pin | Host |
|---|---|---|
| `uart_tx` | 8 | `/dev/ttyUSB1` RX (115200 8N1) |
| `uart_rx` | 9 | `/dev/ttyUSB1` TX (115200 8N1) |

> **3.3 V only.** The iCE40 pins are not 5 V tolerant. Do not connect a 5 V
> signal to the Pmod. Use 3.3 V logic, or a switch/jumper to GND (open = 1,
> closed = 0). If you need to interface 5 V logic, use a level shifter.

## Build

From `cpu8/`:

```bash
make fpga                       # countdown demo (default) -> build/top.bin
make fpga FPGA_PROG=pmod        # Pmod loop demo -> build/top.bin (copy it!)
make fpga-check                 # synthesis + area/timing budget
make fpga-repro                 # fpga-check + committed countdown SHA-256
make release-assets             # countdown + Pmod assets and checksums
```

`make fpga` always writes `build/top.bin`, so when you build a non-default demo
copy it before building another one:

```bash
make fpga FPGA_PROG=pmod
cp build/top.bin build/top_pmod.bin
```

`make release-assets` does this for you and writes `top.bin`, `top_pmod.bin`,
their `.sha256` files and `SHA256SUMS` in `build/`. It builds `countdown` last,
so `build/top.bin` is always the default demo and matches the committed
`cpu8/fpga/top.bin.sha256`.

The area/timing report expects the pinned YoWASP toolchain (yosys 0.69 /
nextpnr 0.11). The current design uses **1064/1280 logic cells (83 %)** and closes
timing at **26.28 MHz** with nextpnr constrained to 16 MHz, leaving margin over
the board's 12 MHz clock. The report enforces that 16 MHz target. The pinned
YoWASP wheels keep synthesis reproducible and are the toolchain the bitstreams
are calibrated against; distro nextpnr 0.6 does not close the constraint.

## Verify before flashing

Every released asset has a checksum. From the directory that contains the
downloaded files:

```bash
sha256sum -c top.bin.sha256
sha256sum -c top_pmod.bin.sha256
sha256sum -c SHA256SUMS
```

The countdown hash is also committed in `cpu8/fpga/top.bin.sha256`; a local
rebuild can be checked with:

```bash
cd cpu8
make fpga-repro
```

A mismatch means the RTL, the program image or the toolchain changed. Do not
flash a bitstream whose hash does not match the release.

## Flash

The iCEstick has an onboard SPI flash. With `iceprog` installed (Debian/Ubuntu:
the `fpga-icestorm` package, or build the IceStorm tools):

```bash
iceprog build/top.bin          # write the bitstream to the SPI flash
iceprog -t                     # optional: verify the flash contents
```

Power-cycle the board after programming; the iCEstick has no user reset button
after programming. If `iceprog` reports a permission error, install the
IceStorm udev rules or run it with `sudo`; do not run arbitrary downloads as
root.

## Demos

| Bitstream | Program | What you see |
|---|---|---|
| `top.bin` | `countdown.asm` | counts 9…0 on the LEDs once; after `HLT` all five turn on. Power-cycle to repeat. |
| `top_pmod.bin` | `pmod.asm` | endless `IN A; OUT A; JMP` loop: the low five bits of the Pmod byte follow the inputs in real time. Open inputs read `0xFF` (all LEDs on); grounding a pin clears its bit. |
| (build it) | `uart_echo.asm` | prints `CPU8` over the serial port and echoes every received byte back to the host and to the LEDs. Build with `make fpga FPGA_PROG=uart_echo`. |
| (build it) | `timer.asm` | counts up on the LEDs roughly 20 times per second, driven by the programmable timer interrupt. Build with `make fpga FPGA_PROG=timer`. |

`fibonacci.asm` and `euclid.asm` are **simulation demos**, not bitstreams:
they end in `HLT`, and the top turns all LEDs on at `HLT`, so their final value
would be hidden. They remain part of the program regression.

The Pmod demo reads all eight bits, but only five LEDs are available; bits 5–7
are read by the CPU but not displayed. `top_pmod_tb.v` sweeps `0x00`, `0xFF`,
`0x55`, `0xAA`, every single-bit value, `0xA5` and `0x5A` through the complete
path (Pmod pins → synchronizer → `IN` → `OUT` → LEDs).

## Tests

```bash
cd cpu8
make modtests       # includes top_tb and top_pmod_tb
make fpga-check
make fpga-repro
```

- `tb/top_tb.v` loads a small `IN A / OUT A / HLT` program, drives
  `pmod_in = 0xA5` and checks `out_data`, `halted` and the LEDs. Changing the
  input to `0x00` makes it fail, so the check is not vacuous.
- `tb/top_pmod_tb.v` loads the assembled `programs/pmod.hex` and sweeps the
  input values while the CPU loops forever.

## Troubleshooting

| Symptom | Check |
|---|---|
| `iceprog: command not found` | install `fpga-icestorm` or build IceStorm. |
| `iceprog` permission denied | install the udev rules or use `sudo`. |
| All LEDs on with `top_pmod.bin` | inputs are open (`0xFF`) or the low five bits are all 1; ground pins to change the pattern. |
| Nothing happens | verify the hash, reflash, check the 12 MHz clock and the board power. |
| `make fpga-check` fails timing | use the pinned YoWASP yosys/nextpnr versions, not the distro nextpnr 0.6. |
| `make fpga-repro` hash mismatch | clean `build/`, rerun with the pinned toolchain; do not publish the bitstream. |
