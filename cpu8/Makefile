# ============================================================================
#  cpu8 project Makefile
#
#  Usage:
#    make test                -> module tests + assembles and verifies programs/*.asm
#    make irqtest             -> interrupt test (irq.asm with irq active)
#    make sim  PROG=programs/foo  -> assembles foo.asm and simulates the full CPU
#    make wave PROG=programs/foo  -> same as sim, and opens GTKWave with the trace
#    make asm  PROG=programs/foo  -> assemble only
#    make debug PROG=programs/foo -> interactive debugger (step/breakpoints/watch)
#    make clean               -> removes the build/ artifacts
#
#  Tools (can be overridden): iverilog, vvp, gtkwave, python3.
# ============================================================================

IVERILOG ?= iverilog
VVP      ?= vvp
GTKWAVE  ?= gtkwave
PYTHON   ?= python3
# Ruff for linting the Python code (config in ruff.toml); `pip install ruff`.
RUFF     ?= ruff
# Verilator (Phase 7.6): uses the one from PATH or, if not, the one installed in ~/.local/bin.
VERILATOR ?= $(shell command -v verilator 2>/dev/null || echo $(HOME)/.local/bin/verilator)
VERILATOR_COVERAGE ?= $(shell command -v verilator_coverage 2>/dev/null || echo $(HOME)/.local/bin/verilator_coverage)
# FPGA flow (Phase 7.6): yosys + nextpnr-ice40 + icepack.  The ones from
# PATH can be used, or the YoWASP packages (pip install yowasp-yosys yowasp-nextpnr-ice40).
YOSYS    ?= $(shell command -v yosys 2>/dev/null || command -v yowasp-yosys 2>/dev/null || echo $(HOME)/.local/bin/yowasp-yosys)
NEXTPNR  ?= $(shell command -v nextpnr-ice40 2>/dev/null || command -v yowasp-nextpnr-ice40 2>/dev/null || echo $(HOME)/.local/bin/yowasp-nextpnr-ice40)
ICEPACK  ?= $(shell command -v icepack 2>/dev/null || command -v yowasp-icepack 2>/dev/null || echo $(HOME)/.local/bin/yowasp-icepack)
# Verilog formatter (Phase 12e): optional, `pip install verible` provides the
# real Verible binaries.  Not part of `make check`: the RTL predates the
# formatter, so `make fmt` would reformat the whole tree in one go.
VERIBLE  ?= $(shell command -v verible-verilog-format 2>/dev/null || echo $(HOME)/.local/bin/verible-verilog-format)
# Formal verification (SymbiYosys).  SBY finds yosys/smtbmc/witness through the
# environment (the yowasp wrappers) and a SMT solver in PATH (z3, from
# `pip install z3-solver`).
SBY       ?= $(shell command -v sby 2>/dev/null || command -v yowasp-sby 2>/dev/null || echo $(HOME)/.local/bin/yowasp-sby)
YOSYS_FV  ?= $(shell command -v yosys 2>/dev/null || command -v yowasp-yosys 2>/dev/null || echo $(HOME)/.local/bin/yowasp-yosys)
SMTBMC_FV ?= $(shell command -v yosys-smtbmc 2>/dev/null || command -v yowasp-yosys-smtbmc 2>/dev/null || echo $(HOME)/.local/bin/yowasp-yosys-smtbmc)
WITNESS_FV ?= $(shell command -v yosys-witness 2>/dev/null || command -v yowasp-yosys-witness 2>/dev/null || echo $(HOME)/.local/bin/yowasp-yosys-witness)
Z3        ?= $(shell command -v z3 2>/dev/null || echo z3)

IVFLAGS  ?= -g2012 -Wall

RTL_DIR  = rtl
TB_DIR   = tb
ASM_DIR  = asm
TOOLS_DIR = tools
PROG_DIR = programs
BUILD    = build
VL_DIR   = $(BUILD)/verilator
COV_DIR  = $(BUILD)/verilator-cov
FORMAL_DIR = formal

# All the testbenches: tb/<module>_tb.v
TB_SRCS  = $(wildcard $(TB_DIR)/*_tb.v)
# cpu_tb.v is special: it needs a program (+hex) and its expected list (+exp),
# so it is not run in the module test loop but with the programs.
CPU_TB   = $(TB_DIR)/cpu_tb.v
# irq_tb.v is also special: it instantiates the CPU with IRQ_VECTOR=0x10 and asserts
# the irq signal; it is run with its own program irq.asm in the irqtest target.
IRQ_TB   = $(TB_DIR)/irq_tb.v
# cpu_trace_tb.v is a tool (trace debugger): it needs a +hex and is
# not part of the module test loop.
TRACE_TB = $(TB_DIR)/cpu_trace_tb.v
# cpu_dump_tb.v is the machine-readable dump used by the differential fuzz
# (tools/difftest.py): it needs a +hex and is not in the module test loop.
DUMP_TB  = $(TB_DIR)/cpu_dump_tb.v
MOD_TB   = $(filter-out $(CPU_TB) $(IRQ_TB) $(TRACE_TB) $(DUMP_TB),$(TB_SRCS))

# Demo programs: each programs/<name>.asm with its programs/<name>.ref.
# irq.asm is excluded: it needs the irq signal, which only irq_tb handles (irqtest).
# pmod.asm is excluded: it never halts (it is a hardware demo), so it is tested
# by top_pmod_tb instead of the halt-based program regression.
PROGS    = $(filter-out $(PROG_DIR)/irq.asm $(PROG_DIR)/pmod.asm,$(wildcard $(PROG_DIR)/*.asm))

# Default program for sim/wave (without the .asm extension)
PROG ?= $(PROG_DIR)/countdown

# FPGA: folder with the top and the constraints; program to synthesize.
FPGA_DIR  = fpga
# Verilog sources covered by `make fmt` / `make fmt-check`.
V_FILES  = $(RTL_DIR)/*.v $(TB_DIR)/*.v $(TB_DIR)/verilator/*.v $(FPGA_DIR)/*.v
FPGA_PROG ?= countdown


all: test

dirs:
	@mkdir -p $(BUILD)

## --- Full suite: module tests + program tests + interrupts ---
test: modtests progtests irqtest

## --- Assemble the infinite-loop Pmod demo (used by top_pmod_tb and the FPGA) ---
pmodhex: dirs
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG_DIR)/pmod.asm

## --- Individual module tests (ALU, RAM, PC, registers) ---
## Each testbench is compiled together with ALL the RTL and run.
modtests: dirs pmodhex
	@if [ -z "$(MOD_TB)" ]; then \
	  echo "There are no module testbenches in $(TB_DIR)/ yet."; \
	else \
	  set -e; \
	  for tb in $(MOD_TB); do \
	    name=$$(basename $$tb .v); \
	    echo "=== $$name ==="; \
	    $(IVERILOG) $(IVFLAGS) -s $$name -o $(BUILD)/$$name.vvp $$tb \
	      $(RTL_DIR)/*.v $(FPGA_DIR)/top.v; \
	    $(VVP) $(BUILD)/$$name.vvp +hex=$(PROG_DIR)/pmod.hex; \
	    echo ""; \
	  done; \
	fi

## --- Interrupt test: assembles irq.asm and runs it with irq active ---
irqtest: dirs
	@set -e; \
	echo "=== irq_tb (interrupts) ==="; \
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG_DIR)/irq.asm; \
	$(IVERILOG) $(IVFLAGS) -s irq_tb -o $(BUILD)/irq_tb.vvp $(IRQ_TB) $(RTL_DIR)/*.v; \
	$(VVP) $(BUILD)/irq_tb.vvp +hex=$(PROG_DIR)/irq.hex +exp=$(PROG_DIR)/irq.ref

## --- Program tests: assembles each .asm and runs it comparing the output ---
## Each program needs a programs/<name>.ref with the expected outputs.
progtests: dirs
	@set -e; \
	$(IVERILOG) $(IVFLAGS) -s cpu_tb -o $(BUILD)/cpu_prog.vvp $(CPU_TB) $(RTL_DIR)/*.v; \
	for p in $(PROGS); do \
	  base=$${p%.asm}; ref=$$base.ref; \
	  echo "=== program $$(basename $$base) ==="; \
	  if [ ! -f $$ref ]; then echo "MISSING $$ref (expected output)"; exit 1; fi; \
	  $(PYTHON) $(ASM_DIR)/assembler.py $$p -o $$base.hex; \
	  $(VVP) $(BUILD)/cpu_prog.vvp +hex=$$base.hex +exp=$$ref; \
	  echo ""; \
	done

## --- Assemble a .asm program -> .hex ---
asm: dirs
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG).asm -o $(PROG).hex

## --- Simulate the full CPU with a program ---
## If asm/assembler.py exists the .asm -> .hex is assembled; if not (Phase 4),
## the .hex already present on disk is used.
sim: dirs
	@if [ -f $(ASM_DIR)/assembler.py ]; then \
	  $(PYTHON) $(ASM_DIR)/assembler.py $(PROG).asm -o $(PROG).hex; \
	else \
	  test -f $(PROG).hex || { echo "Missing $(PROG).hex (and there is no assembler yet)"; exit 1; }; \
	fi
	$(IVERILOG) $(IVFLAGS) -s cpu_tb -o $(BUILD)/cpu_sim.vvp $(TB_DIR)/cpu_tb.v $(RTL_DIR)/*.v
	@if [ -f $(PROG).ref ]; then \
	  $(VVP) $(BUILD)/cpu_sim.vvp +hex=$(PROG).hex +exp=$(PROG).ref; \
	else \
	  $(VVP) $(BUILD)/cpu_sim.vvp +hex=$(PROG).hex; \
	fi

## --- Simulate and view waveforms (opens GTKWave with the signals already set up) ---
wave: sim
	$(GTKWAVE) cpu.gtkw &

## --- Trace debugger: one line per retired instruction (CPU state) ---
## Usage: make trace PROG=programs/foo   (accepts IN=<byte> to set the input)
trace: dirs
	@if [ -f $(ASM_DIR)/assembler.py ] && [ -f $(PROG).asm ]; then \
	  $(PYTHON) $(ASM_DIR)/assembler.py $(PROG).asm -o $(PROG).hex; \
	fi
	$(IVERILOG) $(IVFLAGS) -s cpu_trace_tb -o $(BUILD)/trace.vvp $(TRACE_TB) $(RTL_DIR)/*.v
	$(VVP) $(BUILD)/trace.vvp +hex=$(PROG).hex $(if $(IN),+in=$(IN),)

## --- Disassemble a .hex program to a readable listing ---
## Usage: make disasm PROG=programs/foo   (or HEXFILE=programs/foo.hex)
disasm:
	$(PYTHON) $(TOOLS_DIR)/disasm.py $(if $(HEXFILE),$(HEXFILE),$(PROG).hex)

## --- Interactive debugger over the reference model (tools/iss.py) ---
## Steps instruction by instruction, with breakpoints, watchpoints, memory and
## disassembly dumps, and a cycle count that models the FSM of rtl/control.v.
## Usage: make debug PROG=programs/<name>
debug:
	$(PYTHON) $(TOOLS_DIR)/debugger.py $(if $(wildcard $(PROG).asm),$(PROG).asm,$(PROG).hex)

## --- Tests for the Python tools (assembler + ISA table + disassembler + ISS + debugger) ---
pytools:
	$(PYTHON) -m pytest $(ASM_DIR) $(TOOLS_DIR) -q

## --- Lint of the Python code with Ruff (config in ruff.toml) ---
lint:
	$(RUFF) check .

## --- Generate the docs/OPCODES.md opcode table from the single source asm/isa_table.py ---
docs:
	$(PYTHON) $(TOOLS_DIR)/gen_docs.py

## --- Check that docs/OPCODES.md is up to date (for CI; does not write) ---
docs-check:
	$(PYTHON) $(TOOLS_DIR)/gen_docs.py --check

## --- Differential fuzz: RTL (tb/cpu_dump_tb.v) against the model tools/iss.py ---
## Runs each program on the RTL and on the reference model and compares the
## state after each instruction (registers, flags, SP, PC, RAM, OUT).
## Usage: make difftest                 (100 random + the programs/*.asm)
##      make difftest COUNT=500 SEED=7
##      make difftest ONLYPROGS=1     (only the programs/*.asm)
difftest: dirs
	$(PYTHON) $(TOOLS_DIR)/difftest.py --count $(if $(COUNT),$(COUNT),100) \
	  --seed $(if $(SEED),$(SEED),1) $(if $(filter 1,$(ONLYPROGS)),--progs,)

## Long differential run for the scheduled CI job (10,000 random programs).
##      make difftest-long COUNT=10000 SEED=7
difftest-long: dirs
	$(PYTHON) $(TOOLS_DIR)/difftest.py --count $(if $(COUNT),$(COUNT),10000) \
	  --seed $(if $(SEED),$(SEED),1)

## --- Regression harness: bytes + golden traces + round-trip fuzz ---
regress: dirs
	$(PYTHON) $(TOOLS_DIR)/regress.py

## --- (Re)generate the golden regression reference (use after validated changes) ---
regress-update: dirs
	$(PYTHON) $(TOOLS_DIR)/regress.py --update

## --- Simulation with Verilator (Phase 7.6) ---
## Compiles the RTL with Verilator to a C++ model and runs it on the same
## programs as the iverilog simulation, comparing with the .ref.
$(VL_DIR)/Vcpu_sim: $(TB_DIR)/verilator/sim_main.cpp $(TB_DIR)/verilator/cpu_sim.v $(RTL_DIR)/*.v
	$(VERILATOR) --cc --exe --build -j -O3 \
	  --top-module cpu_sim -Wno-UNOPTFLAT \
	  -Mdir $(VL_DIR) \
	  $(CURDIR)/$(TB_DIR)/verilator/sim_main.cpp $(CURDIR)/$(TB_DIR)/verilator/cpu_sim.v $(CURDIR)/$(RTL_DIR)/*.v

verilator: dirs $(VL_DIR)/Vcpu_sim
	@set -e; \
	for p in $(PROGS); do \
	  base=$${p%.asm}; \
	  echo "=== verilator: $$(basename $$base) ==="; \
	  $(PYTHON) $(ASM_DIR)/assembler.py $$p; \
	  if [ ! -f $$base.ref ]; then echo "missing $$base.ref"; exit 1; fi; \
	  $(VL_DIR)/Vcpu_sim +hex=$$base.hex +exp=$$base.ref; \
	  echo ""; \
	done; \
	echo "=== verilator: irq ==="; \
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG_DIR)/irq.asm; \
	$(VL_DIR)/Vcpu_sim +hex=$(PROG_DIR)/irq.hex +exp=$(PROG_DIR)/irq.ref +irq=1

## --- Coverage (Phase 12c): line/toggle coverage of the RTL with Verilator ---
## Builds a SEPARATE instrumented model (--coverage), runs the demo programs
## writing one .dat per run and then merges everything into an annotated
## report: build/verilator-cov/coverage.info and build/verilator-cov/report/.
# -Wno-COVERIGN only exists in recent Verilators: the distro's 5.020 (Ubuntu
# 24.04) errors out on the unknown warning.  Probe for it so `make coverage`
# also builds with the older toolchain used by the CI job.
COV_FLAG = $(shell $(VERILATOR) -Wno-COVERIGN --version >/dev/null 2>&1 && echo -Wno-COVERIGN)
# The dump path is passed with our own +cov= plusarg: Verilator <= 5.020 does
# not know +verilator+coverage+file+ and aborts on unknown runtime arguments.

$(COV_DIR)/Vcpu_sim: $(TB_DIR)/verilator/sim_main.cpp $(TB_DIR)/verilator/cpu_sim.v $(RTL_DIR)/*.v
	$(VERILATOR) --cc --exe --build -j -O3 --coverage $(COV_FLAG) \
	  --top-module cpu_sim -Wno-UNOPTFLAT \
	  -Mdir $(COV_DIR) \
	  $(CURDIR)/$(TB_DIR)/verilator/sim_main.cpp $(CURDIR)/$(TB_DIR)/verilator/cpu_sim.v $(CURDIR)/$(RTL_DIR)/*.v

coverage: dirs $(COV_DIR)/Vcpu_sim
	@set -e; rm -f $(COV_DIR)/cov_*.dat; \
	for p in $(PROGS); do \
	  base=$${p%.asm}; name=$$(basename $$base); \
	  echo "=== coverage: $$name ==="; \
	  $(PYTHON) $(ASM_DIR)/assembler.py $$p; \
	  if [ ! -f $$base.ref ]; then echo "missing $$base.ref"; exit 1; fi; \
	  $(COV_DIR)/Vcpu_sim +hex=$$base.hex +exp=$$base.ref \
	    +cov=$(COV_DIR)/cov_$$name.dat >/dev/null; \
	done; \
	echo "=== coverage: irq ==="; \
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG_DIR)/irq.asm; \
	$(COV_DIR)/Vcpu_sim +hex=$(PROG_DIR)/irq.hex +exp=$(PROG_DIR)/irq.ref +irq=1 \
	  +cov=$(COV_DIR)/cov_irq.dat >/dev/null; \
	echo "=== coverage: merge + annotated report ==="; \
	$(VERILATOR_COVERAGE) -write-info $(COV_DIR)/coverage.info $(COV_DIR)/cov_*.dat; \
	$(VERILATOR_COVERAGE) -annotate $(COV_DIR)/report $(COV_DIR)/cov_*.dat; \
	tot=$$(grep -c '^DA:' $(COV_DIR)/coverage.info || true); \
	cov=$$(grep '^DA:' $(COV_DIR)/coverage.info | grep -vc ',0$$' || true); \
	echo "coverage (lines): $$cov/$$tot executed $$([ "$$tot" -gt 0 ] && awk -v c=$$cov -v t=$$tot 'BEGIN {printf "(%.1f%%)", 100*c/t}' || echo '')"; \
	echo "report: $(COV_DIR)/coverage.info and $(COV_DIR)/report/"; \
	$(PYTHON) $(TOOLS_DIR)/coverage_report.py $(COV_DIR)/coverage.info

## --- Analysis only (lint) of Verilator on the RTL ---
vlint:
	$(VERILATOR) --lint-only -Wall --top-module cpu $(RTL_DIR)/*.v

## Lint the FPGA top level as well.  The CPU's out_port is intentionally left
## unconnected (the board only has LEDs), out_valid/in_port are unused by the
## board, and the initial values of por/in_meta/in_sync are the iCE40 power-on
## state; disable only those three warnings for this target.  PROCASSINIT does
## not exist in older Verilator releases (the Ubuntu 24.04 package is 5.020),
## where -Wno-<unknown> is a hard error, so probe it before using it.
VLINT_TOP_PROCASSINIT = $(shell $(VERILATOR) -Wno-PROCASSINIT --version >/dev/null 2>&1 && echo -Wno-PROCASSINIT)
vlint-top:
	$(VERILATOR) --lint-only -Wall \
	  -Wno-PINMISSING -Wno-UNUSEDSIGNAL $(VLINT_TOP_PROCASSINIT) \
	  --top-module top $(RTL_DIR)/*.v $(FPGA_DIR)/top.v

## --- Verilog formatting (Phase 12e, opt-in) ---
## `make fmt` rewrites the sources in place with Verible; `make fmt-check`
## reports the files that would change (exit status 1).  The sources are
## formatted with the pinned Verible release (see .github/requirements-ci.txt),
## so keep that version when running the check.
fmt:
	@command -v $(VERIBLE) >/dev/null 2>&1 || { \
	  echo "verible-verilog-format not found (pip install verible)"; exit 1; }
	$(VERIBLE) --inplace $(V_FILES)

fmt-check:
	@command -v $(VERIBLE) >/dev/null 2>&1 || { \
	  echo "verible-verilog-format not found (pip install verible)"; exit 1; }
	@rc=0; tmp=$$(mktemp) || exit 1; \
	for f in $(V_FILES); do \
	  $(VERIBLE) "$$f" > "$$tmp" 2>/dev/null || { rm -f "$$tmp"; exit 2; }; \
	  if ! diff -q "$$f" "$$tmp" >/dev/null; then \
	    echo "needs formatting: $$f"; rc=1; \
	  fi; \
	done; rm -f "$$tmp"; exit $$rc

## --- FPGA (Phase 7.6): synthesis for iCEstick (iCE40HX1K, TQ144) ---
## Assembles FPGA_PROG, loads its .hex into RAM (via -DRAM_INIT) and generates the
## bitstream build/top.bin with yosys + nextpnr-ice40 + icepack.
##   make fpga                    (uses programs/countdown.asm)
##   make fpga FPGA_PROG=fibonacci
fpga: dirs
	@set -e; \
	echo "=== FPGA: assemble $(FPGA_PROG) and prepare memory image ==="; \
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG_DIR)/$(FPGA_PROG).asm; \
	cp $(PROG_DIR)/$(FPGA_PROG).hex $(FPGA_DIR)/program.hex; \
	echo "=== FPGA: synthesis (yosys) ==="; \
	$(YOSYS) -p "read_verilog -DRAM_INIT $(wildcard $(RTL_DIR)/*.v) $(FPGA_DIR)/top.v; synth_ice40 -top top -json $(BUILD)/top.json"; \
	echo "=== FPGA: place & route (nextpnr) ==="; \
	$(NEXTPNR) --hx1k --package tq144 --json $(BUILD)/top.json \
	  --pcf $(FPGA_DIR)/icestick.pcf --asc $(BUILD)/top.asc; \
	echo "=== FPGA: bitstream (icepack) ==="; \
	$(ICEPACK) $(BUILD)/top.asc $(BUILD)/top.bin; \
	ls -l $(BUILD)/top.bin $(BUILD)/top.asc $(BUILD)/top.json

## Same as fpga, but also checks the area/timing budget (tools/fpga_report.py).
fpga-check: dirs
	@$(MAKE) --no-print-directory fpga > $(BUILD)/fpga.log 2>&1 \
	  || { tail -n 40 $(BUILD)/fpga.log; exit 1; }
	@$(PYTHON) $(TOOLS_DIR)/fpga_report.py $(BUILD)/fpga.log

## Rebuild one of the published bitstreams and verify its committed SHA-256.
## Only the two release demos have a golden hash; anything else is rejected so
## a typo cannot silently compare the wrong bitstream against top.bin.sha256.
fpga-repro:
	@case "$(FPGA_PROG)" in \
	  ""|countdown) prog=countdown; golden=top.bin.sha256; out=top.bin ;; \
	  pmod) prog=pmod; golden=top_pmod.bin.sha256; out=top_pmod.bin ;; \
	  *) echo "fpga-repro: no golden hash for FPGA_PROG=$(FPGA_PROG)"; \
	     echo "            available: countdown (default), pmod"; exit 2 ;; \
	esac; \
	$(MAKE) --no-print-directory fpga-check FPGA_PROG=$$prog && \
	if [ "$$out" != "top.bin" ]; then cp $(BUILD)/top.bin $(BUILD)/$$out; fi; \
	cd $(BUILD) && sha256sum -c ../$(FPGA_DIR)/$$golden

## Build the bitstreams published in a release, plus one .sha256 per asset and
## a combined SHA256SUMS file.  Only demos that stay visible on the board are
## shipped: countdown (runs once, then HLT lights all LEDs) and pmod (endless
## loop).  fibonacci/euclid halt, so the top would hide their result behind the
## all-LEDs-on HLT indicator; they remain simulation-only programs.
## countdown is built last so build/top.bin is the default demo and matches
## fpga/top.bin.sha256.
release-assets: dirs
	@set -e; \
	for p in pmod countdown; do \
	  echo "=== release asset: $$p ==="; \
	  $(MAKE) --no-print-directory fpga FPGA_PROG=$$p > $(BUILD)/fpga-$$p.log 2>&1; \
	  $(PYTHON) $(TOOLS_DIR)/fpga_report.py $(BUILD)/fpga-$$p.log; \
	  if [ "$$p" = "countdown" ]; then out=top.bin; else out=top_$$p.bin; cp $(BUILD)/top.bin $(BUILD)/$$out; fi; \
	  (cd $(BUILD) && sha256sum $$out > $$out.sha256); \
	done; \
	(cd $(BUILD) && sha256sum top.bin top_pmod.bin > SHA256SUMS); \
	(cd $(BUILD) && sha256sum -c ../$(FPGA_DIR)/top.bin.sha256 && \
	 sha256sum -c ../$(FPGA_DIR)/top_pmod.bin.sha256); \
	ls -l $(BUILD)/top*.bin $(BUILD)/*.sha256 $(BUILD)/SHA256SUMS

## --- Formal verification (SymbiYosys): bounded proofs with z3 ---
##   make formal
## Each formal/*.sby runs in its own work directory; `-f` overwrites it.
formal: dirs
	@set -e; \
	for f in $(FORMAL_DIR)/*.sby; do \
	  echo "=== formal: $$(basename $$f .sby) ==="; \
	  ( cd $(FORMAL_DIR) && \
	    YOSYS="$(YOSYS_FV)" SMTBMC="$(SMTBMC_FV)" WITNESS="$(WITNESS_FV)" \
	    PATH="$(dir $(Z3)):$$PATH" $(SBY) -f "$$(basename $$f)" ); \
	done
	@echo "formal: all proofs passed"

clean:
	rm -rf $(BUILD) $(FORMAL_DIR)/*/ $(FPGA_DIR)/program.hex

.PHONY: all dirs test modtests pmodhex progtests irqtest asm sim wave trace disasm debug \
	pytools lint docs docs-check difftest difftest-long regress regress-update verilator \
	coverage vlint vlint-top fmt fmt-check fpga fpga-check fpga-repro release-assets formal clean help check

## --- Full local battery: the same as CI runs ---
check: COUNT = 150
check: SEED = 1
check: vlint vlint-top modtests progtests irqtest verilator pytools difftest regress docs-check lint

help:
	@echo "make test                          (modules + demo programs + irq)"
	@echo "make verilator                     (simulates the RTL with Verilator)"
	@echo "make coverage                      (Verilator coverage report of the RTL)"
	@echo "make vlint                         (Verilator -Wall analysis only of the RTL)"
	@echo "make fmt                           (format the Verilog sources with Verible)"
	@echo "make fmt-check                     (report the Verilog files Verible would change)"
	@echo "make fpga FPGA_PROG=<name>         (synthesizes a bitstream for iCEstick)"
	@echo "make fpga-check FPGA_PROG=<name>   (fpga + area/timing budget check)"
	@echo "make fpga-repro                    (fpga-check + committed bitstream SHA-256)"
	@echo "make release-assets                (build top.bin/top_pmod.bin + checksums)"
	@echo "make formal                        (SymbiYosys proofs of the ALU and the FSM)"
	@echo "make sim  PROG=programs/<name>     (assembles and simulates; compares with .ref)"
	@echo "make wave PROG=programs/<name>     (assembles and simulates; opens GTKWave)"
	@echo "make trace PROG=programs/<name>    (trace: one line per instruction)"
	@echo "make disasm PROG=programs/<name>   (disassembles the .hex to a listing)"
	@echo "make debug PROG=programs/<name>    (interactive debugger: step/breakpoints/watch)"
	@echo "make pytools                       (pytest: assembler, ISA table, disassembler, ISS, debugger, reports)"
	@echo "make lint                          (ruff: lint of the Python code)"
	@echo "make docs                          (regenerates docs/OPCODES.md from the ISA table)"
	@echo "make docs-check                    (checks that docs/OPCODES.md is up to date)"
	@echo "make difftest [COUNT=N] [SEED=S]   (differential fuzz: RTL vs reference model)"
	@echo "make difftest-long [COUNT=N] [SEED=S] (long run for the scheduled CI job)"
	@echo "make regress                       (regression: bytes + traces + fuzz)"
	@echo "make regress-update                (regenerates the golden reference)"
	@echo "make check                         (full battery: the same as CI)"
	@echo "make asm  PROG=programs/<name>     (assemble only)"
	@echo "make clean"
