# CPU8 — CPU educativa de 8 bits en Verilog

[![CI](https://github.com/Ghostalex07/cpu8/actions/workflows/ci.yml/badge.svg)](https://github.com/Ghostalex07/cpu8/actions/workflows/ci.yml)

CPU8 es una **CPU de 8 bits de arquitectura von Neumann**, escrita en Verilog
sintetizable, pensada como proyecto **didáctico completo**: no solo el procesador
(RTL), sino también su **ensamblador**, su **desensamblador**, un **simulador de
referencia** en Python y un sistema de **verificación** (testbenches, regresión
dorada y *fuzz* diferencial RTL-vs-modelo).

Cabe en una FPGA pequeña (síntesis probada para la **iCEstick / iCE40HX1K**) y se
puede ejecutar por completo **sin hardware**, con `iverilog` y/o `verilator`.

---

## Características

- **Arquitectura von Neumann**: una única memoria de **256 bytes** compartida por
  programa y datos, bus de direcciones de 8 bits y de datos de 8 bits.
- **Registros**: `A`, `B`, `C`, `D` (8 bits) y, en la CPU, `PC`, `SP`, `IR`,
  `operand` y las banderas **Z** (cero), **C** (acarreo/no-*borrow*), **N**
  (negativo), **V** (desbordamiento con signo) e **I** (interrupciones).
- **Unidad de control** implementada como **FSM de 5 estados**
  (`FETCH` → `OPR` → `EXEC`, más `IRQ` y `HLT`). La longitud (1 o 2 bytes) se
  decide en `FETCH`; no hay estado de decodificación.
- **ALU** de un único **sumador de 9 bits** que realiza tanto `ADD` como
  `SUB`/`CMP` (mediante `a + ~b + 1`), con cálculo completo de banderas.
- **Juego de instrucciones** amplio: carga/almacenamiento (absoluto, indexado
  `[rs+off]` e indirecto por registro), aritmética y lógica, desplazamientos,
  `INC`/`DEC`, pila (`PUSH`/`POP`), subrutinas (`CALL`/`RET`), saltos
  condicionales incondicionales y con signo/estado, **`MUL`/`DIV` de hardware**,
  **E/S por puertos** (`IN`/`OUT`) e **interrupciones** (`EI`/`DI`).
- **Ensamblador propio** de dos pasadas con directivas `.org`, `.db` y `.equ`.
- **Verificación**: testbenches de módulo, comparación de la salida de cada
  programa contra una referencia dorada (`.ref`), regresión por *hash* de bytes
  y trazas, *round-trip* ensamblar→desensamblar→ensamblar, y **fuzz diferencial**
  que compara el RTL contra un modelo de referencia **tras cada instrucción**.

---

## Inicio rápido

**Requisitos**: `iverilog` + `vvp`, `python3` (≥ 3.10), `pytest` y `ruff`.
Opcionales: `verilator` (co-simulación) y `yosys` + `nextpnr-ice40` + `icepack`
(síntesis FPGA).

Todo se ejecuta desde la carpeta `cpu8/`:

```bash
cd cpu8

make test        # testbenches de módulos + ensambla/simula/compara programs/*.asm
make pytools     # pytest: ensamblador, tabla ISA, desensamblador y modelo ISS
make vlint       # análisis -Wall del RTL con Verilator (debe estar limpio)
make verilator   # co-simulación C++ del procesador completo
make difftest    # fuzz diferencial RTL vs modelo de referencia
make regress     # regresión de bytes + trazas + fuzz ida/vuelta
make check       # todo lo anterior (lo mismo que corre la CI)

make sim  PROG=programs/countdown   # simula un programa (compara con su .ref)
make wave PROG=programs/countdown   # íd. y abre GTKWave
make trace PROG=programs/countdown  # traza: una línea por instrucción retirada
make disasm PROG=programs/countdown # desensambla el .hex a un listado
```

`make help` muestra la lista completa de objetivos.

---

## Estructura del repositorio

```
.
├── README.md               # este fichero
├── CONTRIBUTING.md         # guía para contribuir
├── CHANGELOG.md            # historial de cambios
├── LICENSE                 # licencia MIT
├── docs/
│   └── ARCHITECTURE.md     # visión general del datapath y la FSM
├── programs/
│   └── README.md           # descripción de los programas de ejemplo
└── cpu8/                   # el proyecto (Makefile y todo lo demás)
    ├── Makefile
    ├── ruff.toml           # configuración del linter de Python
    ├── rtl/                # Verilog sintetizable
    │   ├── cpu.v           # instancia el datapath
    │   ├── control.v       # FSM de control
    │   ├── alu.v           # ALU (sumador de 9 bits)
    │   ├── regfile.v       # banco de registros A-D
    │   ├── pc.v            # contador de programa
    │   └── ram.v           # memoria unificada (BRAM)
    ├── tb/                 # testbenches
    │   ├── cpu_tb.v        # simula un programa y compara con .ref
    │   ├── cpu_dump_tb.v   # volcado por instrucción (fuzz diferencial)
    │   ├── cpu_trace_tb.v  # traza legible por instrucción
    │   ├── irq_tb.v        # test de interrupciones
    │   ├── *_tb.v          # testbenches de módulo
    │   └── verilator/      # co-simulación C++
    ├── asm/
    │   ├── assembler.py    # ensamblador de 2 pasadas
    │   └── isa_table.py    # fuente única (machine-readable) de la ISA
    ├── programs/           # demos .asm (+ .hex y .ref generados)
    ├── tools/
    │   ├── disasm.py       # desensamblador
    │   ├── iss.py          # modelo de referencia (ISS) en Python
    │   ├── difftest.py     # fuzz diferencial RTL vs ISS
    │   ├── regress.py      # regresión dorada
    │   ├── fuzz.py         # generador de programas aleatorios
    │   ├── gen_docs.py     # genera docs/OPCODES.md desde isa_table.py
    │   └── golden/         # referencias doradas (bytes y trazas)
    ├── docs/
    │   ├── ISA.md          # especificación del juego de instrucciones
    │   └── OPCODES.md      # tabla de opcodes (generada)
    └── fpga/               # flujo de síntesis para iCEstick
```

---

## El juego de instrucciones

La ISA incluye:

| Familia | Instrucciones |
|---|---|
| Datos | `LDI`, `MOV`, `LD`, `ST` (absoluto / indexado / indirecto) |
| Aritmética | `ADD`, `ADDI`, `SUB`, `SUBI`, `CMP`, `CMPI`, `INC`, `DEC`, `MUL`, `DIV` |
| Lógica | `AND`, `OR`, `XOR` |
| Desplazamiento | `SHL`, `SHR` |
| Pila y control | `PUSH`, `POP`, `JMP`, `CALL`, `RET`, `HLT` |
| Saltos condicionales | `JZ`/`JNZ`, `JC`/`JNC`, `JLT`/`JGE`/`JLE`/`JGT`, `JVS`/`JVC`/`JMI`/`JPL` |
| Sistema y E/S | `EI`, `DI`, `IN`, `OUT` (registro y puerto `IN n,rd` / `OUT n,rd`) |

- Especificación completa y modo a modo: **[`cpu8/docs/ISA.md`](cpu8/docs/ISA.md)**.
- Tabla de opcodes (con *bytes*, operandos y banderas): **[`cpu8/docs/OPCODES.md`](cpu8/docs/OPCODES.md)**,
  generada automáticamente desde `cpu8/asm/isa_table.py` con `make docs`
  (`make docs-check` verifica que está al día).

---

## Verificación

El proyecto se apoya en varias capas de comprobación, todas ejecutables en local:

- **Testbenches de módulo** (`alu`, `pc`, `ram`, `regfile`), con barridos
  exhaustivos en la ALU.
- **Programas de ejemplo**: cada `programs/*.asm` se ensambla, se simula con
  `cpu_tb.v` y su salida `OUT` se compara con `programs/*.ref`.
- **Interrupciones**: `irq_tb.v` comprueba la atención de IRQ.
- **Co-simulación** con Verilator (`make verilator`).
- **Modelo de referencia (ISS)**: `tools/iss.py` implementa el ISA en Python. El
  **fuzz diferencial** (`make difftest`, `tools/difftest.py` +
  `tb/cpu_dump_tb.v`) ejecuta cada programa en el RTL y en el ISS y compara el
  estado completo **tras cada instrucción** (registros, banderas, `SP`, `PC`,
  secuencia de `OUT` y RAM final). Esto comprueba que el RTL es *correcto*, no
  solo *estable*. Se cubre también el camino de interrupción.
- **Regresión dorada** (`make regress`): *hash* de los bytes ensamblados, trazas
  de referencia y *round-trip* ensamblar→desensamblar→ensamblar de cientos de
  programas aleatorios.
- **Linter**: `make vlint` (Verilator `-Wall` sobre el RTL) y `make lint` (ruff
  sobre el código Python).

Todo ello se ejecuta en **GitHub Actions** en cada push y *pull request*
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

---

## Licencia

Publicado bajo la licencia **MIT** — ver [`LICENSE`](LICENSE).
