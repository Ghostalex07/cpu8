# ============================================================================
#  Makefile del proyecto cpu8
#
#  Uso:
#    make test                -> tests de modulo + ensambla y verifica programs/*.asm
#    make irqtest             -> test de interrupciones (irq.asm con irq activo)
#    make sim  PROG=programs/foo  -> ensambla foo.asm y simula la CPU completa
#    make wave PROG=programs/foo  -> igual que sim, y abre GTKWave con la traza
#    make asm  PROG=programs/foo  -> solo ensambla
#    make clean               -> borra los artefactos de build/
#
#  Herramientas (se pueden sobrescribir): iverilog, vvp, gtkwave, python3.
# ============================================================================

IVERILOG ?= iverilog
VVP      ?= vvp
GTKWAVE  ?= gtkwave
PYTHON   ?= python3
# Verilator (Fase 7.6): usa el del PATH o, si no, el instalado en ~/.local/bin.
VERILATOR ?= $(shell command -v verilator 2>/dev/null || echo $(HOME)/.local/bin/verilator)
# Flujo FPGA (Fase 7.6): yosys + nextpnr-ice40 + icepack.  Se pueden usar los del
# PATH o los paquetes YoWASP (pip install yowasp-yosys yowasp-nextpnr-ice40).
YOSYS    ?= $(shell command -v yosys 2>/dev/null || command -v yowasp-yosys 2>/dev/null || echo $(HOME)/.local/bin/yowasp-yosys)
NEXTPNR  ?= $(shell command -v nextpnr-ice40 2>/dev/null || echo $(HOME)/.local/bin/yowasp-nextpnr-ice40)
ICEPACK  ?= $(shell command -v icepack 2>/dev/null || echo $(HOME)/.local/bin/yowasp-icepack)

IVFLAGS  ?= -g2012 -Wall

RTL_DIR  = rtl
TB_DIR   = tb
ASM_DIR  = asm
TOOLS_DIR = tools
PROG_DIR = programs
BUILD    = build
VL_DIR   = $(BUILD)/verilator

# Todos los testbenches: tb/<modulo>_tb.v
TB_SRCS  = $(wildcard $(TB_DIR)/*_tb.v)
# cpu_tb.v es especial: necesita un programa (+hex) y su lista esperada (+exp),
# asi que no se ejecuta en el bucle de tests de modulo sino con los programas.
CPU_TB   = $(TB_DIR)/cpu_tb.v
# irq_tb.v tambien es especial: instancia la CPU con IRQ_VECTOR=0x10 y activa la
# senal irq; se ejecuta con su propio programa irq.asm en la diana irqtest.
IRQ_TB   = $(TB_DIR)/irq_tb.v
# cpu_trace_tb.v es una herramienta (debugger de traza): necesita un +hex y no
# forma parte del bucle de tests de modulo.
TRACE_TB = $(TB_DIR)/cpu_trace_tb.v
# cpu_dump_tb.v es el volcado maquina-legible que usa el fuzz diferencial
# (tools/difftest.py): necesita un +hex y no va en el bucle de tests de modulo.
DUMP_TB  = $(TB_DIR)/cpu_dump_tb.v
MOD_TB   = $(filter-out $(CPU_TB) $(IRQ_TB) $(TRACE_TB) $(DUMP_TB),$(TB_SRCS))

# Programas demo: cada programs/<nombre>.asm con su programs/<nombre>.ref.
# irq.asm se excluye: necesita la senal irq, que solo maneja irq_tb (irqtest).
PROGS    = $(filter-out $(PROG_DIR)/irq.asm,$(wildcard $(PROG_DIR)/*.asm))

# Programa por defecto para sim/wave (sin extensión .asm)
PROG ?= $(PROG_DIR)/countdown

# FPGA: carpeta con el top y las constraints; programa a sintetizar.
FPGA_DIR  = fpga
FPGA_PROG ?= countdown

.PHONY: all test modtests progtests irqtest sim wave asm verilator vlint fpga clean dirs help trace disasm pytools regress regress-update difftest

all: test

dirs:
	@mkdir -p $(BUILD)

## --- Suite completa: tests de modulo + tests de programa + interrupciones ---
test: modtests progtests irqtest

## --- Tests de modulos individuales (ALU, RAM, PC, registros) ---
## Cada testbench se compila junto con TODO el RTL y se ejecuta.
modtests: dirs
	@if [ -z "$(MOD_TB)" ]; then \
	  echo "No hay testbenches de modulo en $(TB_DIR)/ todavia."; \
	else \
	  set -e; \
	  for tb in $(MOD_TB); do \
	    name=$$(basename $$tb .v); \
	    echo "=== $$name ==="; \
	    $(IVERILOG) $(IVFLAGS) -s $$name -o $(BUILD)/$$name.vvp $$tb $(RTL_DIR)/*.v; \
	    $(VVP) $(BUILD)/$$name.vvp; \
	    echo ""; \
	  done; \
	fi

## --- Test de interrupciones: ensambla irq.asm y lo ejecuta con irq activo ---
irqtest: dirs
	@set -e; \
	echo "=== irq_tb (interrupciones) ==="; \
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG_DIR)/irq.asm; \
	$(IVERILOG) $(IVFLAGS) -s irq_tb -o $(BUILD)/irq_tb.vvp $(IRQ_TB) $(RTL_DIR)/*.v; \
	$(VVP) $(BUILD)/irq_tb.vvp +hex=$(PROG_DIR)/irq.hex +exp=$(PROG_DIR)/irq.ref

## --- Tests de programa: ensambla cada .asm y lo ejecuta comparando la salida ---
## Cada programa necesita un programs/<nombre>.ref con las salidas esperadas.
progtests: dirs
	@set -e; \
	$(IVERILOG) $(IVFLAGS) -s cpu_tb -o $(BUILD)/cpu_prog.vvp $(CPU_TB) $(RTL_DIR)/*.v; \
	for p in $(PROGS); do \
	  base=$${p%.asm}; ref=$$base.ref; \
	  echo "=== programa $$(basename $$base) ==="; \
	  if [ ! -f $$ref ]; then echo "FALTA $$ref (salida esperada)"; exit 1; fi; \
	  $(PYTHON) $(ASM_DIR)/assembler.py $$p -o $$base.hex; \
	  $(VVP) $(BUILD)/cpu_prog.vvp +hex=$$base.hex +exp=$$ref; \
	  echo ""; \
	done

## --- Ensamblar un programa .asm -> .hex ---
asm: dirs
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG).asm -o $(PROG).hex

## --- Simular la CPU completa con un programa ---
## Si existe asm/assembler.py se ensambla el .asm -> .hex; si no (Fase 4),
## se usa el .hex ya presente en disco.
sim: dirs
	@if [ -f $(ASM_DIR)/assembler.py ]; then \
	  $(PYTHON) $(ASM_DIR)/assembler.py $(PROG).asm -o $(PROG).hex; \
	else \
	  test -f $(PROG).hex || { echo "Falta $(PROG).hex (y aun no hay ensamblador)"; exit 1; }; \
	fi
	$(IVERILOG) $(IVFLAGS) -s cpu_tb -o $(BUILD)/cpu_sim.vvp $(TB_DIR)/cpu_tb.v $(RTL_DIR)/*.v
	@if [ -f $(PROG).ref ]; then \
	  $(VVP) $(BUILD)/cpu_sim.vvp +hex=$(PROG).hex +exp=$(PROG).ref; \
	else \
	  $(VVP) $(BUILD)/cpu_sim.vvp +hex=$(PROG).hex; \
	fi

## --- Simular y ver formas de onda (abre GTKWave con las señales ya puestas) ---
wave: sim
	$(GTKWAVE) cpu.gtkw &

## --- Debugger de traza: una linea por instruccion retirada (estado de la CPU) ---
## Uso: make trace PROG=programs/foo   (acepta IN=<byte> para fijar la entrada)
trace: dirs
	@if [ -f $(ASM_DIR)/assembler.py ] && [ -f $(PROG).asm ]; then \
	  $(PYTHON) $(ASM_DIR)/assembler.py $(PROG).asm -o $(PROG).hex; \
	fi
	$(IVERILOG) $(IVFLAGS) -s cpu_trace_tb -o $(BUILD)/trace.vvp $(TRACE_TB) $(RTL_DIR)/*.v
	$(VVP) $(BUILD)/trace.vvp +hex=$(PROG).hex $(if $(IN),+in=$(IN),)

## --- Desensamblar un programa .hex a un listado legible ---
## Uso: make disasm PROG=programs/foo   (o FICHERO=programs/foo.hex)
disasm:
	$(PYTHON) $(TOOLS_DIR)/disasm.py $(if $(FICHERO),$(FICHERO),$(PROG).hex)

## --- Tests de las herramientas Python (ensamblador + desensamblador + ISS) ---
pytools:
	$(PYTHON) -m pytest $(ASM_DIR)/test_assembler.py $(TOOLS_DIR)/test_disasm.py $(TOOLS_DIR)/test_iss.py -q

## --- Fuzz diferencial: RTL (tb/cpu_dump_tb.v) contra el modelo tools/iss.py ---
## Ejecuta cada programa en el RTL y en el modelo de referencia y compara el
## estado tras cada instruccion (registros, flags, SP, PC, RAM, OUT).
## Uso: make difftest                 (100 aleatorios + los programs/*.asm)
##      make difftest COUNT=500 SEED=7
##      make difftest ONLYPROGS=1     (solo los programs/*.asm)
difftest: dirs
	$(PYTHON) $(TOOLS_DIR)/difftest.py --count $(if $(COUNT),$(COUNT),100) \
	  --seed $(if $(SEED),$(SEED),1) $(if $(ONLYPROGS),--progs,)

## --- Harness de regresion: bytes + trazas doradas + fuzz de ida y vuelta ---
regress: dirs
	$(PYTHON) $(TOOLS_DIR)/regress.py

## --- (Re)genera la referencia dorada de regresion (usar tras cambios validados) ---
regress-update: dirs
	$(PYTHON) $(TOOLS_DIR)/regress.py --update

## --- Simulacion con Verilator (Fase 7.6) ---
## Compila el RTL con Verilator a un modelo C++ y lo ejecuta sobre los mismos
## programas que la simulacion con iverilog, comparando con los .ref.
$(VL_DIR)/Vcpu_sim: $(TB_DIR)/verilator/sim_main.cpp $(TB_DIR)/verilator/cpu_sim.v $(RTL_DIR)/*.v
	$(VERILATOR) --cc --exe --build -j -O3 \
	  --top-module cpu_sim -Wno-UNOPTFLAT \
	  -Mdir $(VL_DIR) \
	  $(TB_DIR)/verilator/sim_main.cpp $(TB_DIR)/verilator/cpu_sim.v $(RTL_DIR)/*.v

verilator: dirs $(VL_DIR)/Vcpu_sim
	@set -e; \
	for p in $(PROGS); do \
	  base=$${p%.asm}; \
	  echo "=== verilator: $$(basename $$base) ==="; \
	  $(PYTHON) $(ASM_DIR)/assembler.py $$p; \
	  if [ -f $$base.ref ]; then $(VL_DIR)/Vcpu_sim +hex=$$base.hex +exp=$$base.ref; \
	  else $(VL_DIR)/Vcpu_sim +hex=$$base.hex; fi; \
	  echo ""; \
	done; \
	echo "=== verilator: irq ==="; \
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG_DIR)/irq.asm; \
	$(VL_DIR)/Vcpu_sim +hex=$(PROG_DIR)/irq.hex +exp=$(PROG_DIR)/irq.ref +irq=1

## --- Solo analisis (lint) de Verilator sobre el RTL ---
vlint:
	$(VERILATOR) --lint-only -Wall --top-module cpu $(RTL_DIR)/*.v

## --- FPGA (Fase 7.6): sintesis para iCEstick (iCE40HX1K, TQ144) ---
## Ensambla FPGA_PROG, carga su .hex en la RAM (via -DRAM_INIT) y genera el
## bitstream build/top.bin con yosys + nextpnr-ice40 + icepack.
##   make fpga                    (usa programs/countdown.asm)
##   make fpga FPGA_PROG=fibonacci
fpga: dirs
	@set -e; \
	echo "=== FPGA: ensamblar $(FPGA_PROG) y preparar imagen de memoria ==="; \
	$(PYTHON) $(ASM_DIR)/assembler.py $(PROG_DIR)/$(FPGA_PROG).asm; \
	cp $(PROG_DIR)/$(FPGA_PROG).hex $(FPGA_DIR)/program.hex; \
	echo "=== FPGA: sintesis (yosys) ==="; \
	$(YOSYS) -p "read_verilog -DRAM_INIT -DFPGA_RAM64 $(wildcard $(RTL_DIR)/*.v) $(FPGA_DIR)/top.v; synth_ice40 -top top -json $(BUILD)/top.json"; \
	echo "=== FPGA: place & route (nextpnr) ==="; \
	$(NEXTPNR) --hx1k --package tq144 --json $(BUILD)/top.json \
	  --pcf $(FPGA_DIR)/icestick.pcf --asc $(BUILD)/top.asc; \
	echo "=== FPGA: bitstream (icepack) ==="; \
	$(ICEPACK) $(BUILD)/top.asc $(BUILD)/top.bin; \
	ls -l $(BUILD)/top.bin $(BUILD)/top.asc $(BUILD)/top.json

clean:
	rm -rf $(BUILD)

help:
	@echo "make test                          (modulos + programas demo + irq)"
	@echo "make verilator                     (simula el RTL con Verilator)"
	@echo "make vlint                         (solo analisis -Wall del RTL con Verilator)"
	@echo "make fpga FPGA_PROG=<nombre>       (sintetiza un bitstream para iCEstick)"
	@echo "make sim  PROG=programs/<nombre>   (ensambla y simula; compara con .ref)"
	@echo "make wave PROG=programs/<nombre>   (ensambla y simula; abre GTKWave)"
	@echo "make trace PROG=programs/<nombre>  (traza: una linea por instruccion)"
	@echo "make disasm PROG=programs/<nombre> (desensambla el .hex a un listado)"
	@echo "make pytools                       (pytest de ensamblador, desensamblador e ISS)"
	@echo "make difftest [COUNT=N] [SEED=S]   (fuzz diferencial: RTL vs modelo de referencia)"
	@echo "make regress                       (regresion: bytes + trazas + fuzz)"
	@echo "make regress-update                (regenera la referencia dorada)"
	@echo "make asm  PROG=programs/<nombre>   (solo ensambla)"
	@echo "make clean"
