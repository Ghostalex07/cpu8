# Programas de ejemplo

Cada programa `.asm` se ensambla a `.hex` y se simula con `cpu_tb.v`. Si existe `.ref`, el testbench compara el valor final de `OUT[7:0]` con el contenido de ese fichero.

## Cómo ejecutar un programa

```bash
cd /home/vaca/proyectos/cpu/cpu8
make sim PROG=programs/countdown
make wave PROG=programs/countdown  # Abre GTKWave
```

## Descripción de programas

| Programa | Propósito | Lo que comprueba |
|---|---|---|
| `callret.asm` | Llamadas/subrutinas con `CALL`/`RET` | Flujo de retorno correcto tras subrutina. |
| `countdown.asm` | Cuenta regresiva con bucle | Saltos condicionales/incondicionales, bucles. |
| `extensions.asm` | Extensiones del ISA (Fase 8) | Inmediatos `ADDI`/`SUBI`/`CMPI`, indexado `LD/ST [rs+off]` (incl. offset negativo) y saltos con signo (`JLT/JGE/JLE/JGT`) y de estado (`JVS/JVC/JMI/JPL`). |
| `fase4.asm` | Programa histórico de desarrollo | Ruta funcional básica consolidada. |
| `fibonacci.asm` | Genera secuencia Fibonacci | Cálculo aritmético, bucles, registros. |
| `incdec.asm` | `INC`/`DEC` sobre registros | Flags `Z,N` (INC/DEC **no** modifican `C`). |
| `indirect.asm` | Direccionamiento indirecto `[rs]` | Carga/almacenamiento indirecto por registro. |
| `irq.asm` | Interrupción hardware | Atención IRQ con `IRQ_VECTOR=0x10`. Verifica que se atiende **una vez**. |
| `multiply.asm` | Multiplicación por suma repetida | Algoritmo con bucles y acumulador. |
| `muldiv.asm` | `MUL`/`DIV` hardware (Fase 9) | Multiplicación, desbordamiento (`C=1`), división y división por cero (`C=1`). |
| `inout.asm` | Entrada `IN` y salida por puerto `OUT n, rd` (Fase 9) | Lectura del puerto de entrada y escritura en puertos 0/1/2. |
| `stack.asm` | Operaciones `PUSH`/`POP` + `RET` | Correcto uso de pila y recuperación de dirección. |

## Archivos asociados

- `.asm` – Código fuente ensamblador
- `.hex` – Código máquina generado por `asm/assembler.py`
- `.ref` – Valor esperado de `OUT` al finalizar simulación (bytes hex)

## Ensamblar todo manualmente

```bash
for f in programs/*.asm; do
  python3 asm/assembler.py "$f" -o "${f%.asm}.hex"
done
```

## Notas

- `cpu_tb.v` detiene la simulación al alcanzar `HLT` o tras un número razonable de ciclos.
- El valor de `OUT` es el observado en `cpu.OUT` al final de la simulación y se compara byte a byte con `.ref`.

Todo añadido sin modificar RTL, testbenches existentes ni `Makefile`. 
