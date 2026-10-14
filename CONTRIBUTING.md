# Guía para contribuir

¡Gracias por tu interés en CPU8! Este documento explica cómo montar el entorno,
cómo ejecutar las comprobaciones y las convenciones del proyecto.

## Puesta en marcha

Requisitos:

- `iverilog` + `vvp` (simulación)
- `python3` (≥ 3.10) con `pytest` y `ruff`
- Opcionales: `verilator` (co-simulación) y
  `yosys` + `nextpnr-ice40` + `icepack` (síntesis FPGA)

```bash
git clone https://github.com/Ghostalex07/cpu8.git
cd cpu8
pip install pytest ruff        # o: python3 -m pip install pytest ruff
```

El `Makefile` está en `cpu8/`; ejecuta los comandos desde esa carpeta.

## Ejecutar las comprobaciones

Antes de enviar cambios, ejecuta la **batería completa** (es lo mismo que corre
la CI):

```bash
cd cpu8
make check
```

Por partes:

```bash
make test          # testbenches de módulo + programas demo + interrupciones
make vlint         # lint del RTL con Verilator -Wall (debe quedar limpio)
make pytools       # pytest: ensamblador, tabla ISA, desensamblador e ISS
make lint          # ruff sobre el código Python
make difftest      # fuzz diferencial RTL vs modelo de referencia
make regress       # regresión de bytes + trazas + fuzz ida/vuelta
make verilator     # co-simulación C++ (requiere verilator)
```

Si tu cambio toca el ensamblado (intencionadamente) tendrás que regenerar la
referencia dorada:

```bash
make regress-update
```

> `programs/*.hex` se regeneran de forma determinista en cada ejecución; **no**
> compares por fecha de modificación, usa los `.ref` / las trazas doradas.

## Convenciones

- **Idioma**: el proyecto está comentado y documentado en **español** (los
  identificadores del código pueden estar en español o inglés, sé coherente con
  el fichero que toques).
- **Estilo Python**: línea de 100 columnas, reglas de `ruff` configuradas en
  `cpu8/ruff.toml`. `make lint` debe pasar sin avisos.
- **Estilo Verilog**: sigue el estilo de los ficheros de `rtl/` (nombres de
  señales en minúsculas, comentarios de bloque con líneas `====`). `make vlint`
  debe quedar **sin warnings**.
- **Compatibilidad**: los cambios en el ISA deben ser **retrocompatibles**: los
  `.hex` de los programas existentes no deben cambiar de bytes. Si algo debe
  cambiar, actualiza también `tools/golden/` con `make regress-update` y
  documenta la decisión.

## Añadir un programa de ejemplo

1. Crea `cpu8/programs/<nombre>.asm` con el código (comentado, en español).
2. Añádelo a las tablas de `programs/README.md` y de `cpu8/docs/ISA.md` (§9).
3. Ensámblalo y genera la salida esperada `.ref`:

   ```bash
   cd cpu8
   python3 asm/assembler.py programs/<nombre>.asm
   python3 tools/iss.py programs/<nombre>.hex          # revisa la secuencia OUT
   ```

   El fichero `.ref` contiene un byte `OUT` por línea, en hexadecimal (2 dígitos).
   Genera el `.ref` a partir del **modelo de referencia** (ya verificado contra el
   RTL) para evitar errores.
4. Comprueba que RTL y modelo coinciden y actualiza la referencia dorada:

   ```bash
   python3 tools/difftest.py --progs        # debe decir DIFERENCIAL: TODO OK
   make test
   make regress-update
   make regress
   ```

## Añadir o cambiar instrucciones

La **fuente única de la ISA** es `cpu8/asm/isa_table.py`. Si tocas el juego de
instrucciones:

1. Actualiza el RTL (`rtl/alu.v`, `rtl/control.v`, `rtl/cpu.v`).
2. Actualiza el ensamblador (`asm/assembler.py`) y el desensamblador
   (`tools/disasm.py`).
3. Actualiza `asm/isa_table.py` y regenera la documentación: `make docs`.
4. Amplía el modelo de referencia (`tools/iss.py`) — el fuzz diferencial lo
   exige para seguir siendo útil.
5. Pasa `make check` (incluye `make docs-check`, que falla si la tabla generada
   no está al día).

## Pull requests

- Crea una rama descriptiva (`feature/...`, `fix/...`).
- Deja la CI en **verde**.
- Rellena la plantilla de PR (incluida una lista de comprobación con
  `make test`, `make vlint`, `make pytools` y `make regress`).
