# Historial de cambios

El formato sigue, de forma aproximada, [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El proyecto aún no publica versiones numeradas, por lo que los cambios se
agrupan bajo *No publicado*.

## [No publicado]

### Añadido

- **Tabla ISA como fuente única de verdad** (`cpu8/asm/isa_table.py`,
  *machine-readable*): descripción declarativa de todas las instrucciones
  (formas de operando, página de opcode, longitud, bytes, banderas y
  descripción). `cpu8/tools/gen_docs.py` genera `cpu8/docs/OPCODES.md` a partir
  de ella, y `cpu8/asm/test_isa_table.py` comprueba que no deriva del
  ensamblador ni del desensamblador reales.
- **Cobertura de interrupciones en el fuzz diferencial**: `tb/cpu_dump_tb.v`
  acepta `+irq=N`, `tools/iss.py` modela la atención de interrupción
  (`irq_at` / `take_irq`) y `tools/difftest.py` ejecuta parte de los programas
  aleatorios con `irq` activa (`--irq-prob`).
- **Programas de ejemplo nuevos**: `euclid.asm` (MCD por el algoritmo de
  Euclides con `DIV`/`MUL`), `factorial.asm` (factorial iterativo con `MUL`),
  `primes.asm` (primos por división por tentativa) y `sort.asm` (*bubble sort*
  con la directiva `.db`), con sus `.ref` y trazas doradas.
- **Herramientas de calidad**: configuración de `ruff` (`cpu8/ruff.toml`) y
  objetivos `make lint`, `make docs`, `make docs-check` y `make check`.
- **CI**: lint de Python (ruff) y comprobación de que la documentación de
  opcodes está al día (`make docs-check`).
- **Documentación**: `README.md` raíz, `CONTRIBUTING.md`, este `CHANGELOG.md`,
  plantillas de *issue* y de *pull request*, y `.gitattributes`.

### Cambios

- `make pytools` incluye ahora los tests de la tabla ISA.

### Corregido

- `tools/regress.py`: se eliminaron nombres ambiguos (`E741`) detectados por
  `ruff`.

## Hitos anteriores

A lo largo del desarrollo, el proyecto ha ido incorporando, por fases:

- El **RTL**: datapath, ALU de un sumador de 9 bits, FSM de control de 5 estados,
  banco de registros, contador de programa y memoria unificada.
- El **ensamblador** de dos pasadas y el **desensamblador** (*round-trip*
  exacto).
- **Pila y subrutinas** (`PUSH`/`POP`, `CALL`/`RET`) e **interrupciones**
  (`EI`/`DI`, vector configurable).
- **Direccionamiento indexado e indirecto** y **flag V** con saltos con signo.
- **`MUL`/`DIV` de hardware** y **E/S por puertos** (`IN`/`OUT`).
- El flujo de **síntesis FPGA** para iCEstick (iCE40HX1K).
- Las **herramientas de verificación**: *debugger* de traza, *harness* de
  regresión y *fuzz* diferencial RTL-vs-modelo.
- **Integración continua** en GitHub Actions.
