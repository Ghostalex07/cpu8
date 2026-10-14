#!/usr/bin/env python3
"""Simulador de referencia (ISS) de la CPU cpu8.

Modelo *funcional* por instruccion del conjunto de instrucciones descrito en
``docs/ISA.md`` y realizado en ``rtl/`` (control.v + cpu.v + alu.v).  No modela
ciclos: cada instruccion se ejecuta de una vez, pero reproduce exactamente el
**estado arquitectonico** tras cada una (registros A-D, flags Z/C/N/V, I, SP,
PC) y el contenido de la RAM.

Su razon de ser es el **fuzz diferencial** (``tools/difftest.py``): se ejecuta un
programa en el RTL (con ``tb/cpu_dump_tb.v``) y en este modelo y se comparan,
instruccion a instruccion.  Un fallo aqui o un fallo alla significa discrepancia
entre el modelo y el hardware.

Ambos comparten el mismo convenio de entrada que los testbenches:
``in_data = 0x10 + puerto`` (el puerto ``n`` lee ``0x10+n``).

Uso::

    python3 tools/iss.py programs/countdown.hex --trace
"""

from __future__ import annotations

import sys
from pathlib import Path

MASK = 0xFF
REGS = ("A", "B", "C", "D")

# Codigos de operacion de la ALU (coinciden con alu.v y con el opcode de la ISA).
ADD, SUB, AND, OR, XOR, CMP, SHIFT, MUL, DIV = 0x5, 0x6, 0x7, 0x8, 0x9, 0xA, 0xB, 0xC, 0xD

# Estados de la FSM (solo para documentar la deteccion; el ISS no es ciclo a ciclo).
S_FETCH, S_OPR, S_EXEC, S_IRQ, S_HLT = 0, 1, 2, 3, 4


def needs_operand(instr: int) -> bool:
    """True si la instruccion ocupa 2 bytes (misma regla que control.v)."""
    fop = instr >> 4
    return fop in (0x1, 0x3, 0x4, 0xC, 0xD) or instr in (
        0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9)


def alu(op: int, sh: int, a: int, b: int) -> tuple[int, int, int, int, int]:
    """Replica alu.v: devuelve (y, c, v, z, n)."""
    a &= MASK
    b &= MASK
    y, c, v = b, 0, 0
    if op in (ADD, SUB, CMP):
        resta = op in (SUB, CMP)
        b_eff = (~b & MASK) if resta else b
        suma = a + b_eff + (1 if resta else 0)
        y = suma & MASK
        c = (suma >> 8) & 1
        a7, b7, y7 = (a >> 7) & 1, (b >> 7) & 1, (y >> 7) & 1
        v = (((a7 ^ b7) & (a7 ^ y7)) if resta
             else ((~(a7 ^ b7) & 1) & (a7 ^ y7)))
        v &= 1
    elif op == AND:
        y = a & b
    elif op == OR:
        y = a | b
    elif op == XOR:
        y = a ^ b
    elif op == SHIFT:
        y = (a >> 1) if sh else ((a << 1) & MASK)
        c = (a & 1) if sh else ((a >> 7) & 1)
    elif op == MUL:
        prod = a * b
        y = prod & MASK
        c = 1 if (prod >> 8) else 0
    elif op == DIV:
        if b == 0:
            y, c = 0, 1
        else:
            y, c = a // b, 0
    # else: pass-through (LDI/MOV), y = b, c = 0, v = 0
    z = 1 if y == 0 else 0
    n = (y >> 7) & 1
    return y, c, v, z, n


def branch_cond(fam: int, rs: int, fz: int, fc: int, fn: int, fv: int) -> int:
    """Replica la condicion de salto Jcc de control.v."""
    menor = fn ^ fv  # signed_lt (N != V)
    if fam == 0:
        return (fz, 1 - fz, fc, 1 - fc)[rs]
    if fam == 1:
        return (menor, 1 - menor, fz | menor, (1 - fz) & (1 - menor))[rs]
    return (fv, 1 - fv, fn, 1 - fn)[rs]


class ISS:
    """Simulador de referencia del cpu8."""

    def __init__(self, mem: list[int] | None = None,
                 irq_vector: int = 0x08, in_fn=None, irq_at: int | None = None):
        self.mem = [0] * 256
        if mem:
            for i, b in enumerate(mem[:256]):
                self.mem[i] = b & MASK
        self.irq_vector = irq_vector & MASK
        # Convenio de entrada de los testbenches: puerto n -> 0x10 + n.
        self.in_fn = in_fn or (lambda port: (0x10 + port) & MASK)
        # Modelo del nivel de irq (None = nunca).  Si es un entero, se replica el
        # convenio del testbench diferencial: irq activo cuando ya se han retirado
        # >= irq_at instrucciones (ver tb/cpu_dump_tb.v y run()).
        self.irq_at = irq_at
        self.reset()

    def reset(self) -> None:
        self.regs = [0, 0, 0, 0]
        self.PC = 0
        self.SP = 0xF0
        self.IR = 0
        self.operand = 0
        self.fz = self.fc = self.fn = self.fv = self.fi = 0
        self.out_data = 0
        self.out_port = 0
        self.halted = False
        self.rows: list[tuple] = []
        self.outs: list[tuple[int, int]] = []

    # -- una instruccion -----------------------------------------------------
    def step(self) -> tuple:
        pc0 = self.PC
        instr = self.mem[self.PC]
        self.PC = (self.PC + 1) & MASK
        self.IR = instr
        if needs_operand(instr):
            self.operand = self.mem[self.PC]
            self.PC = (self.PC + 1) & MASK

        op = instr >> 4
        rd = (instr >> 2) & 3
        rs = instr & 3
        opnd = self.operand
        reg = self.regs
        out_valid = 0

        # --- escribir resultado + flags (helpers) ---
        def set_flags(y, c, v, z, n, we=True, c_we=True):
            if we:
                self.fz, self.fn, self.fv = z, n, v
            if c_we:
                self.fc = c

        def do_alu(opc, sh, a, b, dst=None, c_we=True, we=True):
            y, c, v, z, n = alu(opc, sh, a, b)
            if dst is not None:
                reg[dst] = y
            if we:
                set_flags(y, c, v, z, n, we=True, c_we=c_we)
            return y

        if op == 0x0:                       # INC/DEC/PUSH/POP (registro en rs)
            if rd == 0b00:                  # INC rs: Z,N,V si; C no
                do_alu(ADD, 0, reg[rs], 1, dst=rs, c_we=False)
            elif rd == 0b01:                # DEC rs
                do_alu(SUB, 0, reg[rs], 1, dst=rs, c_we=False)
            elif rd == 0b10:                # PUSH rs
                self.mem[self.SP] = reg[rs]
                self.SP = (self.SP - 1) & MASK
            else:                           # POP rs
                self.SP = (self.SP + 1) & MASK
                reg[rs] = self.mem[self.SP]
        elif op == 0x1:                     # LDI / ADDI / SUBI / CMPI
            sub = rs
            if sub == 0b00:                 # LDI rd, imm (sin flags)
                reg[rd] = opnd
            elif sub == 0b01:               # ADDI
                do_alu(ADD, 0, reg[rd], opnd, dst=rd)
            elif sub == 0b10:               # SUBI
                do_alu(SUB, 0, reg[rd], opnd, dst=rd)
            else:                           # CMPI (solo flags)
                do_alu(CMP, 0, reg[rd], opnd, dst=None)
        elif op == 0x2:                     # MOV rd,rs
            reg[rd] = reg[rs]
        elif op == 0x3:                     # LD rd,[a] / LD rd,[rs+off]
            addr = opnd if rs == 0 else (reg[rs] + opnd) & MASK
            reg[rd] = self.mem[addr]
        elif op == 0x4:                     # ST rd,[a] / ST rd,[rs+off]
            addr = opnd if rs == 0 else (reg[rs] + opnd) & MASK
            self.mem[addr] = reg[rd]
        elif op in (ADD, SUB, AND, OR, XOR):  # ALU registro-registro
            do_alu(op, 0, reg[rd], reg[rs], dst=rd)
        elif op == CMP:
            do_alu(CMP, 0, reg[rd], reg[rs], dst=None)
        elif op == SHIFT:                   # SHL/SHR rd (sh = rs[0])
            do_alu(SHIFT, rs & 1, reg[rd], 0, dst=rd)
        elif op == 0xC:                     # JMP / CALL
            if rs == 0b01:                  # CALL: push direccion de retorno
                self.mem[self.SP] = self.PC
                self.SP = (self.SP - 1) & MASK
            self.PC = opnd                  # JMP (y reservados 10/11) saltan
        elif op == 0xD:                     # Jcc <<familia rd>>
            if branch_cond(rd, rs, self.fz, self.fc, self.fn, self.fv):
                self.PC = opnd
        elif op == 0xE:                     # OUT rd / IN rd (puerto 0)
            if rs == 0b00:                  # OUT rd
                out_valid = 1
                self.out_data, self.out_port = reg[rd], 0
                self.outs.append((reg[rd], 0))
            elif rs == 0b01:                # IN rd
                reg[rd] = self.in_fn(0)
            # rs=10/11: reservados (no-op)
        elif op == 0xF:
            if instr == 0xF0:               # HLT
                self.halted = True
            elif instr == 0xF1:             # RET
                self.SP = (self.SP + 1) & MASK
                self.PC = self.mem[self.SP]
            elif instr == 0xF2:             # EI
                self.fi = 1
            elif instr == 0xF3:             # DI
                self.fi = 0
            elif instr == 0xF4:             # LD rd,[rs] (indirecto)
                d, s = (opnd >> 2) & 3, opnd & 3
                reg[d] = self.mem[reg[s]]
            elif instr == 0xF5:             # ST rd,[rs] (indirecto)
                d, s = (opnd >> 2) & 3, opnd & 3
                self.mem[reg[s]] = reg[d]
            elif instr == 0xF6:             # MUL rd,rs
                d, s = (opnd >> 2) & 3, opnd & 3
                do_alu(MUL, 0, reg[d], reg[s], dst=d)
            elif instr == 0xF7:             # DIV rd,rs
                d, s = (opnd >> 2) & 3, opnd & 3
                do_alu(DIV, 0, reg[d], reg[s], dst=d)
            elif instr == 0xF8:             # OUT n,rd (puerto n)
                d, n = (opnd >> 2) & 3, opnd & 3
                out_valid = 1
                self.out_data, self.out_port = reg[d], n
                self.outs.append((reg[d], n))
            elif instr == 0xF9:             # IN n,rd (puerto n)
                d, n = (opnd >> 2) & 3, opnd & 3
                reg[d] = self.in_fn(n)
            # 0xFA..0xFF: no-op de 1 byte (fop=0xF no exige operando)

        row = (pc0, instr, self.regs[0], self.regs[1], self.regs[2], self.regs[3],
               self.fz, self.fc, self.fn, self.fv, self.SP, self.PC,
               out_valid, self.out_data, self.out_port)
        return row

    def take_irq(self) -> None:
        """Atiende una interrupcion (estado S_IRQ): apila PC, baja I y salta al vector.

        No genera fila de traza: en el RTL el estado S_IRQ no pasa por S_EXEC, de
        modo que no se retira ninguna instruccion.  Hay que replicarlo igual.
        """
        self.mem[self.SP] = self.PC
        self.SP = (self.SP - 1) & MASK
        self.fi = 0
        self.PC = self.irq_vector

    def run(self, max_steps: int = 5000) -> list[tuple]:
        """Ejecuta hasta HLT o ``max_steps``; devuelve las filas de traza.

        Si ``irq_at`` no es None, el nivel de irq se modela como en el testbench
        diferencial (``irq = (n_retiradas >= irq_at)``).  Al comienzo de cada
        instruccion, si el flag I esta activo y hay irq pendiente, se atiende la
        interrupcion (sin retirar instruccion, como el estado S_IRQ del RTL).
        """
        self.rows = []
        guard = 0
        limite = 10 * max_steps + 1000
        while not self.halted and len(self.rows) < max_steps:
            guard += 1
            if guard > limite:      # red de seguridad ante bucles patologicos
                break
            if self.irq_at is not None and self.fi and len(self.rows) >= self.irq_at:
                self.take_irq()
                continue
            self.rows.append(self.step())
        return self.rows

    # -- salida en el mismo formato que tb/cpu_dump_tb.v ---------------------
    @staticmethod
    def _row_line(r: tuple) -> str:
        pc, ir, a, b, c, d, z, cf, n, v, sp, pcn, ov, od, op = r
        return (f"I {pc:02X} {ir:02X} {a:02X} {b:02X} {c:02X} {d:02X} "
                f"{z} {cf} {n} {v} {sp:02X} {pcn:02X} {ov} {od:02X} {op:02X}")

    def dump(self) -> list[str]:
        # Mismo orden que tb/cpu_dump_tb.v: filas, luego END, luego la RAM.
        lineas = [self._row_line(r) for r in self.rows]
        lineas.append(f"END {len(self.rows)}")
        lineas.append("M " + " ".join(f"{b:02X}" for b in self.mem))
        return lineas


def _leer_hex(path: Path) -> list[int]:
    datos = []
    for tok in path.read_text().split():
        datos.append(int(tok, 16))
    return datos


def main(argv: list[str]) -> int:
    args = argv[1:]
    trace = "--trace" in args
    args = [a for a in args if a != "--trace"]
    max_steps = 5000
    if "--max" in args:
        k = args.index("--max")
        max_steps = int(args[k + 1])
        del args[k:k + 2]
    if not args:
        print(__doc__)
        return 2
    iss = ISS(_leer_hex(Path(args[0])))
    iss.run(max_steps)
    if trace:
        for line in iss.dump():
            print(line)
    else:
        print(f"{len(iss.rows)} instrucciones; OUT = "
              + " ".join(f"{v:02X}/{p}" for v, p in iss.outs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
