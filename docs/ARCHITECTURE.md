# Arquitectura CPU8

## Visión general

CPU8 es una CPU educativa de **8 bits** con arquitectura **von Neumann** (memoria unificada para código y datos). Bus de direcciones y datos de 8 bits → **256 bytes** de memoria RAM accesible.

- **Palabras de instrucción**: variables (1 byte o 2 bytes)
- **Registros**: A, B, C, D (GPR), PC, SP, IR, operand, flags (Z, C, N, V), registro I (IRQ)
- **ALU**: combinacional con operaciones ADD/SUB/AND/OR/XOR/CMP/SHL/SHR, las variantes inmediatas ADDI/SUBI/CMPI y MUL/DIV
- **Control**: FSM síncrona con 5 estados (`FETCH`, `OPR`, `EXEC`, `IRQ`, `HLT`)
- **Pila**: LIFO con crecimiento hacia direcciones inferiores (ver `docs/ISA.md`)
- **Interrupciones**: IRQ vector configurable (`IRQ_VECTOR`), atendida una única vez por ciclo IRQ
- **Soporte FPGA**: iCEstick/iCE40HX1K (ver `fpga/top.v`); el diseño **cabe** usando 1 BRAM para la memoria (~30 % de las LUTs de la HX1K)

## Datapath

El datapath se encuentra principalmente en `rtl/cpu.v`. Elementos clave:

- **PC** (`rtl/pc.v`): contador de programa síncrono. Soporta `reset`, `inc`, `load`. Se carga con dirección de salto/RET/IRQ.
- **Regfile** (`rtl/regfile.v`): banco con 4 registros A,B,C,D. 2 puertos de lectura combinacionales, 1 puerto de escritura síncrono con `we`.
- **ALU** (`rtl/alu.v`): unidad aritmético-lógica combinacional. Genera resultado y flags `Z`, `C`, `N`, `V`.
- **RAM** (`rtl/ram.v`): memoria 256x8. Escritura **síncrona** con `we` y lectura **registrada en el flanco de bajada** (`mem[addr] → rdata`). Al quedar el dato disponible a mitad de ciclo, el datapath (que registra en `posedge`) lo ve en el mismo ciclo, pero la memoria puede mapearse a **BRAM** (SB_RAM40_4K) en vez de lógica distribuida. Soporta `$readmemh` en simulación e inicialización para síntesis FPGA.
- **Registros internos**: `IR` (instruction register), `operand` (byte auxiliar para instrucciones de 2 bytes), `flags` (Z,C,N,V), `SP` (stack pointer), `OUT` (salida hacia LEDs/monitor; la CPU expone además `out_port`, `in_data` e `in_port` para 4 puertos de E/S seleccionables).
- **Buses**: `addr`, `data_in`, `data_out`, señales de control desde `control.v`.

## Unidad de control (FSM)

`rtl/control.v` implementa una máquina de estados finita síncrona con reloj `clk` y `reset`.

**Estados:**

| Estado | Nombre | Descripción |
|---|---|---|
| `0` | `FETCH` | Leer instrucción desde `ram[PC]` → cargar `IR`. Incrementar `PC`. Decidir la longitud con el byte leído: 1 byte → `EXEC`, 2 bytes → `OPR`. Si `I=1` e `irq=1`, ir a `IRQ`. |
| `1` | `OPR` | Leer operando desde `ram[PC]` → cargar `operand`. Incrementar `PC`. Pasar a `EXEC`. |
| `2` | `EXEC` | Ejecutar operación según decodificación (mover datos, ALU, saltos, stack, I/O). Actualizar flags/registros/RAM según corresponda. |
| `3` | `IRQ` | Atender interrupción: guardar PC en pila (PUSH), bajar `I`, saltar a `IRQ_VECTOR`. Volver a FETCH. |
| `4` | `HLT` | Estado detenido. CPU permanece en HLT hasta `reset`. |

> La longitud de la instrucción se decide en el propio `FETCH` con `fetched`
> (el byte recién leído de `RAM[PC]`), por lo que no existe un estado `DECODE`
> aparte. `fetched` solo alimenta la transición de estado (registrada), nunca
> `ram_addr`, así que no se forma un lazo combinacional control↔RAM.


**Prioridades** (implícitas en FSM):
- `reset` fuerza estados iniciales
- Si `irq` activo **y** no se está atendiendo ya, transita a `IRQ` (tras completar ciclo adecuado según diseño)
- `HLT` detiene la CPU (permanece en `HLT` hasta `reset`)

## Flujo típico de instrucción

1. **FETCH**: `IR = RAM[PC]; PC = PC+1`; decide la longitud (1 byte → `EXEC`, 2 bytes → `OPR`)
2. **OPR** (si 2 bytes): `operand = RAM[PC]; PC = PC+1`
3. **EXEC**: realizar operación, escribir resultados, actualizar flags
4. Siguiente ciclo vuelve a **FETCH**

## ALU

Implementada en `rtl/alu.v`. Flags:

- **Z (Zero)**: resultado == 0
- **N (Negative)**: bit 7 del resultado a 1 (interpretado con signo)
- **C (Carry)**: acarreo/salida de suma/resta de 8 bits según operación
- **V (Overflow)**: desbordamiento **con signo** (Ca2); solo para ADD/ADDI/SUB/SUBI/CMP/CMPI e INC/DEC

Operaciones soportadas: `ADD`, `SUB`, `AND`, `OR`, `XOR`, `CMP`, `SHL`, `SHR`, `MUL`, `DIV` (`MUL`/`DIV` en la fase 9).

> `CMP` es resta sin guardar resultado (solo actualiza flags).
> Con `N` y `V` se implementan las comparaciones con signo (`JLT/JGE/JLE/JGT`).

## Pila y subrutinas

- **SP** apunta al tope de pila. Comportamiento definido en `docs/ISA.md`.
- **PUSH** decrementa SP y escribe valor
- **POP** lee valor y incrementa SP
- **CALL** guarda dirección de retorno y salta
- **RET** recupera dirección de retorno desde pila

Ver `programs/callret.asm`, `programs/stack.asm` con sus `.ref`.

## Interrupciones (IRQ)

- Señal externa `irq` activa solicitud
- Vector configurable por parámetro: `cpu #(.IRQ_VECTOR(0x10))` (usado en `irq_tb.v`)
- Al atenderse: se guarda PC actual en pila y se carga PC con `IRQ_VECTOR`
- La implementación evita atender IRQ de forma recurrente (atención única por evento según test `irq_tb.v`)
- Ver `programs/irq.asm` y `tb/irq_tb.v`

## Ensamblador

`asm/assembler.py` es un ensamblador **2 pasadas**:

- **Pasada 1**: recolecta etiquetas/símbolos
- **Pasada 2**: genera bytes con codificación según `docs/ISA.md`
- Soporta mnemonics, inmediatos (`LDI`/`ADDI`/`SUBI`/`CMPI`), registros, direccionamiento directo `[a]`, indirecto por registro `[r]`, **indexado** `[r+off]`, etiquetas, comentarios `;` y saltos sin signo/`Jcc` con signo (`JLT/JGE/JLE/JGT`, `JVS/JVC/JMI/JPL`)
- Genera `.hex` con bytes hexadecimales (una instrucción por línea o secuencia)

## Verificación

- **Módulos**: `alu_tb.v`, `pc_tb.v`, `ram_tb.v`, `regfile_tb.v` (incluye barridos exhaustivos en ALU)
- **Programas**: cada `programs/*.asm` se ensambla, simula con `cpu_tb.v` y compara `OUT` con `programs/*.ref`
- **IRQ**: `irq_tb.v` verifica atención correcta
- **Verilator**: `tb/verilator/cpu_sim.v` + `sim_main.cpp` carga `.hex` y compara con `.ref`
- **Dirigido**: `cpu_directed_tb.v` cubre casos límite (CALL/RET, pila, E/S portada, etc.)
- **Ensamblador**: `asm/test_assembler.py` (pytest) verifica la codificación instrucción a instrucción; `asm/test_isa_table.py` comprueba que la tabla ISA no deriva del ensamblador ni del desensamblador.
- **Diferencial**: `tools/iss.py` (modelo de referencia) se contrasta instrucción a
  instrucción con el RTL a través de `tb/cpu_dump_tb.v` (`make difftest`); los
  `.ref` dorados de `programs/` también se reproducen desde el modelo
  (`tools/test_iss.py`). El fuzz diferencial cubre además la atención de
  interrupciones: parte de los programas aleatorios se ejecutan con la señal `irq`
  activa y el ISS modela `S_IRQ` igual que el RTL.
- **Lint / docs**: `make lint` (ruff) revisa el código Python y `make docs-check`
  verifica que `docs/OPCODES.md` está al día respecto a `asm/isa_table.py`.

## Herramientas (`tools/`)

- **Desensamblador** (`tools/disasm.py`): `.hex` → listado en ensamblador legible
  (`make disasm PROG=programs/<nombre>`). Su salida es sintaxis válida del
  ensamblador, así que se puede reensamblar (propiedad *round-trip* que se prueba
  en `tools/test_disasm.py`).
- **Debugger de traza** (`tb/cpu_trace_tb.v`): ejecuta un programa y muestra una
  línea por instrucción retirada con `PC`, `IR`, `A`, `B`, `C`, `D`, `Z`, `C`, `N`,
  `V` y `SP` (`make trace PROG=programs/<nombre>`).
- **Harness de regresión** (`tools/regress.py`): comprueba que (1) el ensamblado
  produce los mismos bytes que la referencia dorada (`tools/golden/hex.sha256`),
  (2) la traza de cada programa coincide con la dorada
  (`tools/golden/traces/*.trace`) y (3) 200 programas aleatorios sobreviven al
  *round-trip* ensamblar→desensamblar→ensamblar (`make regress`). Regenera la
  referencia con `make regress-update`.
- **Fuzz** (`tools/fuzz.py`): generador de programas aleatorios válidos usado por
  el harness y los tests.
- **Modelo de referencia / ISS** (`tools/iss.py`): simulador funcional del ISA en
  Python (estado arquitectónico completo: registros, flags, `SP`, `PC`, RAM y
  puertos de E/S). No es ciclo a ciclo, pero replica exactamente la semántica de
  `rtl/`. Se puede usar directamente:
  `python3 tools/iss.py programs/countdown.hex --trace`.
- **Fuzz diferencial** (`tools/difftest.py` + `tb/cpu_dump_tb.v`): ejecuta cada
  programa (los `programs/*.asm` y programas aleatorios de `tools/fuzz.py`) en el
  RTL y en el ISS y compara el estado **tras cada instrucción** (A-D, Z/C/N/V,
  SP, PC, la secuencia de `OUT` y la RAM final). Es la verificación que caza bugs
  que las trazas doradas no ven (estas solo prueban *estabilidad*, no
  *corrección*). Uso: `make difftest [COUNT=N] [SEED=S] [ONLYPROGS=1]`.
- **Tests del ISS** (`tools/test_iss.py`): micro-tests dirigidos de la ALU/flags/
  pila/indexado/`Jcc`/puertos/IRQ y contraste del ISS con los `.ref` dorados
  (`make pytools`).
- **Tabla ISA y documentación de opcodes** (`asm/isa_table.py` + `tools/gen_docs.py`):
  la tabla es la fuente única de la ISA; `make docs` regenera `docs/OPCODES.md` y
  `make docs-check` comprueba que está al día.

## Referencias

- `docs/ISA.md` – Especificación completa (opcode map, modos, flags, stack, IRQ)
- `rtl/` – Implementación RTL
- `tb/` – Testbenches
- `tools/` – Ensamblador (desensamblador), traza, regresión, ISS y fuzz diferencial
- `programs/` – Ejemplos con referencias
- `programs/README.md` – Descripción de los programas de ejemplo
