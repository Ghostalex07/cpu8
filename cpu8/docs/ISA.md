# ISA — Juego de instrucciones de la CPU de 8 bits (cpu8)

> **Este documento es la fuente de verdad.** Si el diseño cambia, primero se actualiza
> aquí y después el RTL.

## 1. Modelo de máquina

- **Arquitectura von Neumann**: código y datos comparten una única memoria de 256 bytes.
- **Bus de datos**: 8 bits. **Bus de direcciones**: 8 bits → 256 direcciones (0x00–0xFF).
- **Palabra de instrucción**: variable (1 o 2 bytes).

### Registros de propósito general (8 bits cada uno)

| Nombre | Índice (rd/rs) | Descripción            |
|--------|----------------|------------------------|
| A      | `00`           | Acumulador / registro 0|
| B      | `01`           | Registro 1             |
| C      | `10`           | Registro 2             |
| D      | `11`           | Registro 3             |

### Registros internos

| Registro | Ancho | Función                                                        |
|----------|-------|----------------------------------------------------------------|
| PC       | 8     | Contador de programa (dirección de la próxima instrucción).    |
| IR       | 8     | Registro de instrucción (opcode en ejecución).                 |
| MDR/op   | 8     | Registro auxiliar de datos / operando (uso interno del datapath).|
| SP       | 8     | Puntero de pila; apunta a la próxima posición libre (§10.2).        |
| I        | 1     | Habilitación de interrupciones (0 tras reset) (§10.6).             |

### Flags (registro de estado)

| Flag | Nombre   | Significado                                                         |
|------|----------|---------------------------------------------------------------------|
| Z    | Zero     | 1 si el resultado de la última operación con flags es 0x00.         |
| C    | Carry    | Acarreo (suma) / **no-borrow** (resta). Ver §5.                     |
| N    | Negative | Copia del bit 7 (MSB) del resultado. Para aritmética con signo (Ca2).|
| V    | Overflow | Desbordamiento **con signo** (Ca2). Ver §5.                          |

> El flag **V** (Fase 8) permite comparaciones con signo: tras `CMP`/`SUB` (o `ADD`),
> `N ⊕ V` indica "menor que" con signo. Ver las familias de `Jcc` en §4.

### Puerto de salida

- Un (1) registro de salida de 8 bits, sin dirección. La instrucción `OUT rd` lo escribe
  y el testbench lo imprime con `$display`. En una FPGA se mapearía a LEDs.

## 2. Formato de instrucción

Primer byte:

```
 7   6   5   4 | 3   2 | 1   0
[   opcode    ]|[ rd  ]|[ rs  ]
```

- `[7:4]` opcode (4 bits, 16 valores posibles).
- `[3:2]` `rd` — registro destino/fuente (índice de la tabla de registros).
- `[1:0]` `rs` — registro fuente **o** selector (condición de salto, dirección de
  desplazamiento, subtipo). Cuando no se usa, debe valer `00`.

Algunas instrucciones ocupan un **segundo byte** que es un **inmediato** (constante de 8
bits), una **dirección absoluta** de 8 bits, o los **índices de dos registros**. En ese
caso los bits `rd`/`rs` del primer byte se usan según la tabla.

### Codificación de registros

`A=00`, `B=01`, `C=10`, `D=11`.

### Selectores en los campos `rd`/`rs` (según instrucción)

| Instrucción | Campos `rd` / `rs`                                                     |
|-------------|-----------------------------------------------------------------------|
| LDI/ADDI/SUBI/CMPI | `rd`: registro; `rs`: `00`=LDI, `01`=ADDI, `10`=SUBI, `11`=CMPI (§10.7) |
| SHL/SHR     | `rs`: `00` = SHL (izquierda), `01` = SHR (derecha)                    |
| LD/ST rd,[a]| `rs`: `00` = absoluto; `01`/`10`/`11` = indexado con base B/C/D (§10.7) |
| Jcc         | `rd`: familia (`00` sin signo, `01` con signo, `10` estado); `rs`: condición (§4) |
| JMP/CALL    | `rs`: `00` = JMP, `01` = CALL                                         |
| Grupo `0x0` | `rd`: `00` = INC, `01` = DEC, `10` = PUSH, `11` = POP; `rs`: registro |
| Grupo `0xF` | `rd`+`rs` = subcódigo (ver §10.5)                                     |
| resto       | reservado, usar `00`                                                  |

## 3. Tabla de instrucciones

| Op (hex) | Mnemónico  | Bytes | Encoding (byte 1)          | Byte 2      | Descripción                                  |
|----------|------------|-------|----------------------------|-------------|----------------------------------------------|
| `0`      | INC/DEC/PUSH/POP rd | 1 | `0000 oo ss` (oo=op, ss=reg) | —     | Operación sobre un registro (§10.1).         |
| `1`      | LDI/ADDI/SUBI/CMPI rd,imm | 2 | `0001 rr kk` (kk=00/01/10/11) | `imm` | `LDI`: `rd ← imm`; `ADDI`/`SUBI`: `rd ← rd ± imm` (flags); `CMPI`: solo flags (§10.7). |
| `2`      | MOV rd,rs  | 1     | `0010 rr ss`               | —           | `rd ← rs`. **NOP = MOV A,A = `0x20`**.       |
| `3`      | LD rd,[a]  | 2     | `0011 rr ss`               | `a`/`off`   | `rd ← RAM[a]` (`ss=00`); indexado `rd ← RAM[rs+off]` (`ss≠00`, base B/C/D) (§10.7). |
| `4`      | ST rd,[a]  | 2     | `0100 rr ss`               | `a`/`off`   | `RAM[a] ← rd` (`ss=00`); indexado `RAM[rs+off] ← rd` (`ss≠00`) (§10.7). |
| `5`      | ADD rd,rs  | 1     | `0101 rr ss`               | —           | `rd ← rd + rs` (flags).                      |
| `6`      | SUB rd,rs  | 1     | `0110 rr ss`               | —           | `rd ← rd - rs` (flags).                      |
| `7`      | AND rd,rs  | 1     | `0111 rr ss`               | —           | `rd ← rd & rs` (flags Z,N).                  |
| `8`      | OR  rd,rs  | 1     | `1000 rr ss`               | —           | `rd ← rd \| rs` (flags Z,N).                 |
| `9`      | XOR rd,rs  | 1     | `1001 rr ss`               | —           | `rd ← rd ^ rs` (flags Z,N).                  |
| `A`      | CMP rd,rs  | 1     | `1010 rr ss`               | —           | calcula `rd - rs`, actualiza flags, **no** guarda resultado. |
| `B`      | SHL/SHR rd | 1     | `1011 rr kk` (kk=00/01)    | —           | desplaza `rd` 1 bit (flags).                 |
| `C`      | JMP/CALL a | 2     | `1100 00 kk` (kk=00/01)    | `a`         | `kk=00` JMP: `PC←a`; `kk=01` CALL: `push(PC)`, `PC←a` (§10.3). |
| `D`      | Jcc a      | 2     | `1101 ff cc` (ff=familia)  | `a`         | salto condicional: familia `ff` y condición `cc` (ver §4). |
| `E`      | OUT rd / IN rd | 1 | `1110 rr kk` (kk=00/01)    | —           | `kk=00` OUT: puerto 0 ← `rd`; `kk=01` IN: `rd` ← puerto 0 (§10.9). |
| `F`      | Grupo sistema/memoria | 1–2 | `1111 dddd` (subcódigo) | (según subtipo) | `HLT`, `RET`, `EI`, `DI`, `LD/ST` indirecto, `MUL`/`DIV`, `OUT n,rd`/`IN n,rd` (§10.4, §10.5, §10.8, §10.9). |

`rr` = índice de `rd`, `ss` = índice de `rs`, `oo` = suboperación, `dddd` = subcódigo.
`imm`/`a` = 8 bits.

## 4. Saltos condicionales (Jcc)

`Jcc a` evalúa una condición y, si se cumple, hace `PC ← a`. En caso contrario continúa
en la instrucción siguiente. El byte 1 es `1101 ff cc`, donde `ff` (los bits `rd`,
reservados en el Jcc original) seleccionan la **familia** y `cc` (campo `rs`) la condición
dentro de ella.

**Familia `ff=00` — sin signo** (retrocompatible con la definición original):

| cc (`rs`) | Mnemónico | Condición     |
|-----------|-----------|---------------|
| `00`      | JZ        | `Z == 1`      |
| `01`      | JNZ       | `Z == 0`      |
| `10`      | JC        | `C == 1`      |
| `11`      | JNC       | `C == 0`      |

Alias de lectura para comparaciones sin signo:

| Alias | Equivale a | Salta cuando              |
|-------|-----------|---------------------------|
| JHS   | JC        | `rd >= rs` (no hubo borrow)|
| JLO   | JNC       | `rd <  rs` (hubo borrow)  |

> **Confirmado (Fase 5).** Como adoptamos el convenio de C invertido (§5: `C=1` =
> no borrow), `JC` salta cuando `rd >= rs`, así que el alias adoptado definitivamente es
> `JHS = JC` y `JLO = JNC`. Así *JLO* salta de verdad cuando el primero es *lower*
> (`rd < rs`) y *JHS* cuando es *higher or same* (`rd >= rs`).

**Familia `ff=01` — con signo (Ca2)** (Fase 8). Usan `N` y `V`. Conviene precederlas de
`CMP`/`SUB` (o `ADD`) sobre los dos valores. Sea `menor = N ⊕ V`:

| cc (`rs`) | Mnemónico | Condición          | Significado              |
|-----------|-----------|--------------------|--------------------------|
| `00`      | JLT       | `N ⊕ V == 1`       | salta si `rd <  rs`      |
| `01`      | JGE       | `N ⊕ V == 0`       | salta si `rd >= rs`      |
| `10`      | JLE       | `Z == 1` o `N ⊕ V` | salta si `rd <= rs`      |
| `11`      | JGT       | `Z == 0` y `N ⊕ V == 0` | salta si `rd > rs`  |

**Familia `ff=10` — estado** (Fase 8): prueba directamente `V` o `N`.

| cc (`rs`) | Mnemónico | Condición     |
|-----------|-----------|---------------|
| `00`      | JVS       | `V == 1`      |
| `01`      | JVC       | `V == 0`      |
| `10`      | JMI       | `N == 1`      |
| `11`      | JPL       | `N == 0`      |

Codificación: byte 1 = `0xD0 | (familia << 2) | condición`. Así `JZ`=`0xD0`, `JNZ`=`0xD1`,
`JC`=`0xD2`, `JNC`=`0xD3`, `JLT`=`0xD4`, `JGE`=`0xD5`, `JLE`=`0xD6`, `JGT`=`0xD7`,
`JVS`=`0xD8`, `JVC`=`0xD9`, `JMI`=`0xDA`, `JPL`=`0xDB`.

## 5. Convenio del flag C (acarreo / borrow)

El acarreo se define a partir del **sumador de 8 bits** de la ALU, que siempre calcula
`op1 + op2 + cin`:

- **ADD rd,rs** y **ADDI rd,imm**: `op1 = rd`, `op2 = rs` (o `imm`), `cin = 0`.
  `C` = acarreo de salida del bit 7. `C=1` significa desbordamiento **sin signo** (el
  resultado no cabe en 8 bits).

- **SUB rd,rs**, **SUBI rd,imm**, **CMP rd,rs** y **CMPI rd,imm**: la resta se hace como
  `rd - rs = rd + (~rs) + 1`, es decir `op1 = rd`, `op2 = ~rs` (o `~imm`), `cin = 1`.
  Entonces `C` = acarreo de salida del bit 7 del sumador, que en este montaje significa:

  | Situación (sin signo) | `C` |
  |-----------------------|-----|
  | `rd >= rs` (no borrow)|  1  |
  | `rd <  rs` (borrow)   |  0  |

  **Convención elegida (invertida, tipo 6502/AVR/ARM): `C=1` ⇒ NO hubo borrow; `C=0` ⇒
  sí hubo borrow.** Por eso `JC` = "saltar si `rd >= rs`" y `JNC` = "saltar si `rd < rs`".
  La ventaja es que la resta **reutiliza físicamente el mismo sumador** de la suma, sin
  lógica extra.

- **AND / OR / XOR**: `C = 0`.
- **SHL**: `C` = bit 7 **anterior** al desplazamiento (el bit que sale por la izquierda).
- **SHR**: `C` = bit 0 **anterior** al desplazamiento (el bit que sale por la derecha).
- **MUL rd,rs**: `C = 1` si el producto no cabe en 8 bits (byte alto ≠ 0); `V = 0`.
- **DIV rd,rs**: `C = 1` si el divisor era 0 (y entonces `rd = 0`); `V = 0`.
- **LDI / MOV / LD / ST / OUT / IN / NOP / JMP / Jcc / HLT / PUSH / POP / CALL / RET / EI / DI**: **no** modifican flags.

### Flag Z y N

- `Z = 1` si el resultado de la operación con flags es `0x00`.
- `N = resultado[7]` (copia del MSB).
- **Solo** actualizan flags estas instrucciones: **ADD, ADDI, SUB, SUBI, AND, OR, XOR, CMP,
  CMPI, SHL, SHR, MUL, DIV**, y también **INC**/**DEC** (cambian `Z`, `N` y `V` pero **no**
  `C`).
  En **SHL/SHR**, `Z` y `N` se recalculan sobre el valor desplazado y `C` guarda el bit que
  sale (ver arriba). Las cargas (`LDI/MOV/LD`) **no** tocan los flags.

### Flag V (desbordamiento con signo, Fase 8)

`V` indica que el resultado **con signo** (complemento a dos sobre 8 bits) no cabe:

- **ADD / ADDI**: `V = 1` si ambos operandos tienen el mismo signo y el resultado tiene otro
  (p. ej. `0x7F + 0x01 = 0x80` → `V=1`).
- **SUB / SUBI / CMP / CMPI**: `V = 1` si los operandos tienen signos distintos y el
  resultado no coincide en signo con el primero (p. ej. `0x80 - 0x01 = 0x7F` → `V=1`).
- **INC / DEC**: también actualizan `V` (p. ej. `INC` de `0x7F` da `0x80` con `V=1`).
- **AND / OR / XOR / SHL / SHR** y el resto de instrucciones: `V = 0` (no significativo).

Con `N` y `V` se implementa la comparación con signo: **"rd < rs" ⇔ `N ⊕ V == 1`**. Las
familias `JLT/JGE/JLE/JGT` de `Jcc` (§4) lo usan directamente.

## 6. Notas de diseño y limitaciones (a revisar más adelante)

1. **Espacio de opcode saturado → solución adoptada (Fase 7).** Los 16 códigos originales
   (`0`–`F`) estaban ocupados, así que se aprovechan los huecos ya previstos: `NOP` es un
   **alias de `MOV A,A` (`0x20`)**; el **opcode `0x0`** pasa a ser la página de
   **operaciones sobre un registro** (`INC`/`DEC`/`PUSH`/`POP`, 16 subcódigos); el **opcode
   `0xF`** es la página de **sistema/memoria** (`HLT`/`RET`/`EI`/`DI` y `LD`/`ST`
   indirectos); y la familia de salto `0xC` incorpora `CALL` (`0xC1`) junto a `JMP`
   (`0xC0`). Todo lo anterior es **retrocompatible**: ningún byte existente cambia de
   significado. Detalle en §10.
2. **`ADDI`/`SUBI`/`CMPI` (Fase 8)**: implementados en la página del `LDI`
   (`0001 rr kk`, ver §10.7) de forma **retrocompatible** (`kk=00` sigue siendo `LDI`).
   Para sumar una constante ya no hace falta `LDI` a un registro libre + `ADD`.
3. **Direccionamiento indirecto por registro**: **implementado en la Fase 7** como
   `LD rd,[rs]` / `ST rd,[rs]` (`0xF4`/`0xF5`, ver §10.4), con un registro como puntero.
   **Direccionamiento indexado** (base + desplazamiento) **implementado en la Fase 8** como
   `LD/ST rd,[rs+off]` (`ss≠00`, base B/C/D; ver §10.7). Sigue **sin** haber `(indirect)` a
   través de memoria (doble indirección: `RAM[RAM[a]]`).
4. **Flag V (Fase 8)**: implementado; habilita las comparaciones con signo `JLT/JGE/JLE/JGT`
   y los saltos de estado `JVS/JVC/JMI/JPL` (ver §4 y §5).
5. **E/S**: hay 4 puertos de E/S seleccionables (`OUT n, rd` / `IN n, rd`, §10.9). El
   primer puerto (0) sigue funcionando con la forma corta `OUT rd`.
6. **Direcciones de 8 bits** compartidas con código y datos en von Neumann: ojo con no
   pisar el programa al escribir datos. Además, la **pila** ocupa RAM creciendo hacia abajo
   desde `0xF0`, así que hay que dejar ese espacio libre (ver §10.2).
7. **`MUL`/`DIV` (Fase 9)**: implementados como hardware combinacional en la ALU
   (subcódigos `0xF6`/`0xF7`). El multiplicador y el divisor añaden área de LUTs, pero el
   diseño sigue cabiendo con holgura en la iCE40HX1K. `DIV` por cero da `0` y `C=1`.

## 7. Ejemplos

```asm
; Suma 5 + 3 y muestra el resultado por el puerto de salida
        LDI A, 5        ; A = 0x05
        LDI B, 3        ; B = 0x03
        ADD A, B        ; A = A + B = 0x08, Z=0 C=0 N=0
        OUT A           ; imprime 0x08
        HLT
```

Codificado como `.hex` para `$readmemh` (cada línea = 1 byte):

```
10
05
11
03
51
E0
F0
```

> Aquí `ADD A,B` = `0101 rr ss` con `rd=A=00`, `rs=B=01` → `0101 0001` = `0x51`.

```asm
; Cuenta atrás desde 3 hasta 0, imprime cada valor
        LDI A, 3
bucle:  OUT A
        LDI B, 1
        SUB A, B
        JNZ bucle       ; repite mientras A != 0
        HLT
```

> `SUB A,B` = `0110 0001` = `0x61`. `JNZ bucle` = `1101 00 cc` con `cc=JNZ=01` → `0xD1`.

## 8. Ensamblador (`asm/assembler.py`, Fase 5)

Traduce un fichero `.asm` a un `.hex` (un byte hexadecimal por línea) que el
testbench carga con `$readmemh`.

**Uso**

```sh
python3 asm/assembler.py programa.asm -o programa.hex   # ensamblar
python3 asm/assembler.py programa.asm -l                # + listado y etiquetas
make asm  PROG=programs/demo                            # atajo del Makefile
make sim  PROG=programs/demo                            # ensambla y simula
```

**Sintaxis**

- Comentarios con `;` hasta el final de la línea.
- Etiquetas: `nombre:` al principio de una línea, solas o antes de una instrucción.
  Ej: `bucle: OUT A`. Referenciables como destino de `JMP`/`Jcc` o como dirección
  en `LD`/`ST`.
- Mnemónicos y registros insensibles a mayúsculas (`ldi A, 5` = `LDI A, 5`).
- Registros: `A`, `B`, `C`, `D`.
- Números: decimal (`7`, `255`), hexadecimal (`0x20` o `$20`) y binario (`0b1010`).
- `LD`/`ST` directos admiten la dirección entre corchetes o sin ellos: `LD A, [0x20]` o
  `LD A, 0x20`. El destino puede ser una etiqueta: `LD A, [bucle]`.
- `LD`/`ST` **indirectos** (por registro) usan el nombre de un registro dentro de los
  corchetes: `LD A, [B]` = `A ← RAM[B]`; `ST A, [B]` = `RAM[B] ← A` (ver §10.4).
- `LD`/`ST` **indexados** (base + desplazamiento, Fase 8): `LD A, [B+3]` = `A ← RAM[B+3]`;
  `ST A, [C+tabla]`. La base debe ser `B`, `C` o `D` (con `A` se usaría el modo absoluto);
  el desplazamiento admite signo (`[B-1]`) y etiquetas.
- Inmediatos con la ALU (Fase 8): `ADDI`, `SUBI`, `CMPI` (p. ej. `ADDI A, 5`).

**Mnemónicos admitidos**: `NOP`, `LDI`, `ADDI`, `SUBI`, `CMPI`, `MOV`, `LD`, `ST`, `ADD`,
`SUB`, `AND`, `OR`, `XOR`, `CMP`, `SHL`, `SHR`, `MUL`, `DIV`, `IN`, `OUT`, `INC`, `DEC`,
`PUSH`, `POP`, `JMP`, `CALL`, `RET`, `JZ`, `JNZ`, `JC`, `JNC`, `JHS`, `JLO`, `JLT`, `JGE`,
`JLE`, `JGT`, `JVS`, `JVC`, `JMI`, `JPL`, `EI`, `DI`, `HLT`. (`NOP` se codifica como
`MOV A,A` = `0x20`; `JHS`/`JLO` son alias de `JC`/`JNC`, ver §4.)

**Directivas** (empiezan por `.`, insensibles a mayúsculas; Fase 9)

| Directiva          | Efecto                                                                |
|--------------------|-----------------------------------------------------------------------|
| `.equ NOMBRE, expr`| Define una constante reutilizable (número o constante previa).        |
| `.org expr`        | Fija la dirección actual. Si avanza, rellena con `00`; retroceder es error. |
| `.db item, ...`    | Emite bytes: números, etiquetas o cadenas `"..."` (ASCII).            |

Ejemplo:

```asm
.equ LEDS, 0xE0
tabla: .db 10, 20, 30, "Hola", 0   ; bytes de datos en RAM
.org 0x20                          ; el código empieza en 0x20
inicio: LDI A, LEDS                ; A = constante
        OUT A
        HLT
```

Dentro de una cadena `.db` se admiten los escapes `\n`, `\t`, `\r`, `\0`, `\\` y `\"`;
las comas dentro de las comillas no separan campos.

**Funcionamiento (dos pasadas + constantes)**

0. *Pase 0*: recoge todas las `.equ` en la tabla de constantes (permite usarlas
   aunque se definan más abajo).
1. *Pase 1*: recorre el fuente y asigna a cada etiqueta su dirección. Para ello
   necesita el tamaño de cada instrucción: **2 bytes** para `LDI`, `ADDI`, `SUBI`, `CMPI`,
   `LD`/`ST` (directos, indirectos e indexados), `JMP`, `CALL`, `MUL`, `DIV` y `Jcc`;
   **1 byte** para el resto (`OUT`/`IN` son de 1 byte en su forma de registro y de 2 en la
   portada `OUT n, rd`/`IN n, rd`); `.org` fija el PC y `.db` aporta tantos bytes como items.
2. *Pase 2*: emite los bytes (`.org` rellena con ceros) y resuelve las referencias a
   etiquetas y constantes (ya conocidas, aunque se definan más abajo).

**Errores**: se informan con el número de línea y un mensaje claro (mnemónico
desconocido, registro inválido, número fuera de rango `0..255`, etiqueta no
definida o duplicada, número incorrecto de operandos, programa mayor de 256
bytes). El ensamblador termina con código de salida distinto de cero si hay error.

## 9. Programas demo y verificación automática (Fase 6)

En `programs/` hay varios programas de ejemplo escritos a mano con el ISA:

| Programa        | Qué hace                                                        | Salida (por `OUT`)                          |
|-----------------|-----------------------------------------------------------------|---------------------------------------------|
| `countdown.asm` | Cuenta atrás de 9 a 0                                           | `9 8 7 6 5 4 3 2 1 0`                        |
| `fibonacci.asm` | Fibonacci hasta que la suma desborda los 8 bits                 | `1 1 2 3 5 8 13 21 34 55 89 144 233`         |
| `multiply.asm`  | Multiplicación por sumas sucesivas (`6 x 7`), muestra parciales | `6 12 18 24 30 36 42`                        |
| `fase4.asm`     | Cuenta atrás con paso por memoria (programa de la Fase 4)       | `7 6 5 4 3 2 1`                              |
| `incdec.asm`    | `INC`/`DEC` y comprueba que no alteran el flag C (Fase 7.2)     | `1 2 3 4 5 4`                                |
| `stack.asm`     | `PUSH`/`POP` (LIFO) y `RET` a una dirección empujada (Fase 7.3) | `2 1 1`                                      |
| `callret.asm`   | Subrutina `suma` llamada con `CALL`/`RET` (Fase 7.4)            | `7 14`                                       |
| `indirect.asm`  | Direccionamiento indirecto `LD/ST rd,[rs]` con puntero (Fase 7.4) | `7 42`                                     |
| `extensions.asm`| Inmediatos `ADDI`/`SUBI`/`CMPI`, indexado `[rs+off]` y saltos con signo/estado (Fase 8) | `0A 0F 08 22 33 11 44 A1 A2 A3 B1 B2` (hex) |
| `muldiv.asm`    | `MUL`/`DIV` hardware, incluido desbordamiento y división por cero (Fase 9) | `2A 90 C1 1C 21 00 C2 C3` (hex) |
| `inout.asm`     | Entrada `IN` y salida por puerto `OUT n, rd` (Fase 9) | `10 12 AB 55` (hex) |
| `irq.asm`       | Interrupción: `EI`, contador 0..9 y manejador que cuenta 1 (Fase 7.5) | `0 1 2 3 4 5 6 7 8 9 1`                 |

**Cómo se verifican.** Cada programa tiene un fichero hermano `programs/<nombre>.ref`
con la lista de salidas esperadas en hexadecimal (un valor por línea, sin
comentarios). El testbench `tb/cpu_tb.v`:

- Carga el programa con `+hex=<ruta>` y las salidas esperadas con `+exp=<ruta>`.
- Ejecuta hasta `HLT`, imprime cada `OUT` y lo compara con el `.ref`; cuenta las
  salidas y falla si el número o algún valor no coincide. Sin `+exp` solo imprime.
- Genera `build/cpu_tb.vcd` para GTKWave.

`make test` ejecuta los testbenches de módulo (`alu`, `pc`, `ram`, `regfile`) y
después, para cada `programs/*.asm`, lo ensambla, lo simula y lo compara con su
`.ref`. `make sim PROG=programs/<nombre>` hace lo mismo para un único programa
(compara automáticamente si existe el `.ref`).

`irq.asm` se verifica aparte con `make irqtest`: `tb/irq_tb.v` instancia la CPU
con `IRQ_VECTOR = 0x10` y activa la señal `irq` tras el reset (el `cpu_tb`
normal la deja a `0`, así que `irq.asm` se excluye del bucle de `progtests`).

**Verificación diferencial.** Además de los `.ref` (que comprueban que la salida
*no cambia*), `tools/iss.py` es un modelo de referencia del ISA en Python y
`make difftest` lo ejecuta en paralelo con el RTL (`tb/cpu_dump_tb.v`) sobre los
programas demo y cientos de programas aleatorios, comparando el estado completo
(registros, flags, `SP`, `PC`, RAM y `OUT`) **tras cada instrucción**. Esto
comprueba que el RTL es *correcto*, no solo estable. `tools/test_iss.py` añade
micro-tests dirigidos y contrasta el modelo con los `.ref`.

## 10. Extensiones de la Fase 7

### 10.1 Grupo `0x0` — operaciones sobre un registro (1 byte)

Formato `byte1 = 0000 oo ss`, donde `oo` = suboperación (bits `[3:2]`) y `ss` = registro
(bits `[1:0]`).

| `oo` | Mnemónico | Efecto                                        |
|------|-----------|-----------------------------------------------|
| `00` | INC rd    | `rd ← rd + 1`; actualiza `Z`,`N` (no `C`).    |
| `01` | DEC rd    | `rd ← rd - 1`; actualiza `Z`,`N` (no `C`).    |
| `10` | PUSH rd   | `RAM[SP] ← rd`; luego `SP ← SP - 1` (§10.2).  |
| `11` | POP rd    | `SP ← SP + 1`; luego `rd ← RAM[SP]` (§10.2).  |

Codificación: `INC A..D = 0x00..0x03`, `DEC A..D = 0x04..0x07`, `PUSH A..D = 0x08..0x0B`,
`POP A..D = 0x0C..0x0F`.

### 10.2 Pila y puntero de pila (SP)

- `SP` es un registro interno de 8 bits. Tras el reset vale `0xF0`.
- La pila es **descendente** (crece hacia direcciones menores) y vive en la misma RAM.
- `SP` apunta a la **próxima posición libre** (pila vacía descendente, modelo 6502):
  - `PUSH rd`: `RAM[SP] ← rd`; `SP ← SP - 1`.
  - `POP rd` : `SP ← SP + 1`; `rd ← RAM[SP]`.
- **Colisión**: el programa y los datos deben dejarse por debajo de `0xF0`; la pila baja
  desde ahí hacia `0x00`.

### 10.3 Subrutinas: CALL / RET

- `CALL a` (`0xC1` + `a`, 2 bytes): guarda la dirección de retorno (**la instrucción
  siguiente**, es decir `dir_CALL + 2`) con un `PUSH` interno y hace `PC ← a`.
- `RET` (`0xF1`): `PC ← POP` (recupera la dirección guardada).
- Se apoyan en `SP` y en la pila, así que no pueden anidarse más allá del espacio de pila
  disponible. No modifican flags.

### 10.4 Direccionamiento indirecto por registro

| Mnemónico    | Bytes | Byte 1 | Byte 2        | Efecto          |
|--------------|-------|--------|---------------|-----------------|
| `LD rd,[rs]` | 2     | `0xF4` | `(rd<<2)\|rs` | `rd ← RAM[rs]`  |
| `ST rd,[rs]` | 2     | `0xF5` | `(rd<<2)\|rs` | `RAM[rs] ← rd`  |

Permite usar un registro como **puntero** (p. ej. recorrer un array incrementando el
registro de dirección con `INC`). El byte 2 empaqueta los índices `rd` y `rs`.

### 10.5 Grupo `0xF` — sistema y memoria

`byte1 = 1111 dddd`, con `dddd` = `rd`+`rs` (subcódigo):

| Subcódigo | Byte1 | Mnemónico   | Bytes | Efecto                          |
|-----------|-------|-------------|-------|---------------------------------|
| `0000`    | `0xF0`| HLT         | 1     | detiene la CPU (sin cambios).   |
| `0001`    | `0xF1`| RET         | 1     | `PC ← POP` (§10.3).             |
| `0010`    | `0xF2`| EI          | 1     | `I ← 1` (habilita IRQ) (§10.6). |
| `0011`    | `0xF3`| DI          | 1     | `I ← 0` (deshabilita IRQ).      |
| `0100`    | `0xF4`| LD rd,[rs]  | 2     | `rd ← RAM[rs]` (§10.4).         |
| `0101`    | `0xF5`| ST rd,[rs]  | 2     | `RAM[rs] ← rd` (§10.4).         |
| resto     | —     | *(reservado)* | —   | —                               |

### 10.6 Interrupciones

- Señal de entrada `IRQ` (nivel, activo alto) y bit de habilitación `I` (0 tras reset):
  `EI` pone `I=1`; `DI` pone `I=0`.
- Si `I=1` y `IRQ=1` **al comienzo de una instrucción**, en vez de buscar la siguiente la
  CPU:
  1. hace `PUSH` de la dirección de retorno (el `PC` actual),
  2. pone `I ← 0` (evita reentrada),
  3. salta al vector **`IRQ_VECTOR`** (parámetro de `cpu.v`, por defecto `0x08`).
- El manejador termina con `RET`, que restaura el `PC`.
- **Limitación**: al atender la interrupción solo se salva el `PC`; los flags no se
  restauran. El manejador debe salvar/restaurar con `PUSH`/`POP` los registros que use, y
  debe reservarse en el programa la dirección del vector.

**Implementación (Fase 7.5).** La atención ocupa un ciclo en un estado propio de la FSM
(`S_IRQ`): al entrar desde `S_FETCH` (sin buscar instrucción) se apila el `PC`, se baja `I`
y el `PC` carga `IRQ_VECTOR`. Como `I` se pone a `0` automáticamente, basta con hacer `EI`
una vez: aunque `IRQ` siga alto, la interrupción no se repite hasta el siguiente `EI`. `EI`
surte efecto inmediato (el propio ciclo de `FETCH` siguiente ya puede atender la IRQ).

### 10.7 Extensiones de la Fase 8 (inmediatos, indexado y flag V)

Todas son **retrocompatibles**: reutilizan campos reservados que valían `00`, así que ningún
byte ya existente cambia de significado (los `programs/*.hex` son byte a byte idénticos).

**a) Inmediatos con la ALU** — página 0x1, con la suboperación en el campo `rs`
(`byte1 = 0001 rr kk`):

| `kk` (`rs`) | Mnemónico    | Byte 1 | Byte 2 | Efecto                              |
|-------------|--------------|--------|--------|-------------------------------------|
| `00`        | LDI rd,imm   | `0x1r` | `imm`  | `rd ← imm` (retrocompatible).       |
| `01`        | ADDI rd,imm  | `0x1r+1`| `imm` | `rd ← rd + imm` (flags Z,C,N,V).    |
| `10`        | SUBI rd,imm  | `0x1r+2`| `imm` | `rd ← rd - imm` (flags Z,C,N,V).    |
| `11`        | CMPI rd,imm  | `0x1r+3`| `imm` | calcula `rd - imm`, flags, no guarda.|

Ej.: `LDI A,10`=`10 0A`, `ADDI A,5`=`11 05`, `SUBI A,6`=`12 06`, `CMPI A,9`=`13 09`.

**b) Direccionamiento indexado** — `LD`/`ST` con base en el campo `rs`
(`byte1 = 0011/0100 rr ss`, `byte2 = off`):

| `ss` (`rs`) | Modo                                            |
|-------------|-------------------------------------------------|
| `00`        | absoluto (retrocompatible): `RAM[a]`            |
| `01`/`10`/`11` | indexado con base `B`/`C`/`D`: `RAM[rs+off]` |

Ej.: `LD D,[C+3]`=`3E 03`, `ST A,[B+3]`=`41 03`. La base `A` no está disponible porque
`ss=00` codifica el modo absoluto (para indexar con `A`, cópialo antes a otro registro).

**c) Saltos con signo y de estado** — ver §4. El campo `rd` del `Jcc` selecciona la familia:
`JLT/JGE/JLE/JGT` (con signo, usando `N` y `V`) y `JVS/JVC/JMI/JPL` (estado).

### 10.8 Multiplicación y división (Fase 9)

Se añaden al grupo `0xF` dos instrucciones de **2 bytes** en los subcódigos aún
libres. El segundo byte lleva los dos registros, `(rd<<2)|rs`, igual que el modo
indirecto:

| Byte 1 | Mnemónico   | Byte 2     | Efecto                                            |
|--------|-------------|------------|---------------------------------------------------|
| `0xF6` | MUL rd,rs   | `(rd<<2)\|rs` | `rd ← (rd × rs)[7:0]`. `C=1` si el producto no cabe en 8 bits. |
| `0xF7` | DIV rd,rs   | `(rd<<2)\|rs` | `rd ← rd / rs` (sin signo). `C=1` si `rs = 0`.  |

Ambas actualizan `Z` y `N`; `V = 0`. En `DIV`, dividir por cero da `rd = 0` y `C = 1`
(resultado determinista, no `x` en simulación).

Ej.: `MUL A,B`=`F6 01` (7×6 → `0x2A`), `DIV A,B`=`F7 01` (200/7 → `0x1C`).
Programa de ejemplo: `programs/muldiv.asm`.

### 10.9 Entrada/salida con puertos (Fase 9)

La CPU expone cuatro **puertos** de 8 bits (0..3). La forma de 1 byte usa
siempre el puerto 0; la forma portada, de **2 bytes**, elige el puerto en los
2 bits bajos del segundo byte:

| Byte 1 | Mnemónico   | Bytes | Byte 2        | Efecto                                     |
|--------|-------------|-------|---------------|--------------------------------------------|
| `0xE0\|(rd<<2)` | OUT rd | 1 | —          | puerto 0 ← `rd` (retrocompatible).         |
| `0xE0\|(rd<<2)\|01` | IN rd | 1 | —       | `rd` ← puerto 0.                           |
| `0xF8` | OUT n, rd   | 2     | `(rd<<2)\|n`  | puerto `n` ← `rd`.                         |
| `0xF9` | IN n, rd    | 2     | `(rd<<2)\|n`  | `rd` ← puerto `n`.                         |

`n` es un número 0..3 (error si se sale). La CPU **saca** la señal `out_port`
(2 bits, el puerto del último `OUT`) y **recibe** `in_data` (8 bits); para que el
entorno sepa qué puerto debe presentar en `in_data`, saca también `in_port`
(2 bits) durante la instrucción `IN` (véase `rtl/cpu.v`).

Ej.: `OUT A`=`E0`, `IN A`=`E1`, `OUT 2, B`=`F8 06`, `IN 3, D`=`F9 0F`.
Programa de ejemplo: `programs/inout.asm` (el testbench presenta `0x10+n` en
`in_data` para el puerto `n`).
