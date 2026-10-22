#!/usr/bin/env python3
"""Reference simulator (ISS) for the cpu8 CPU.

*Functional* per-instruction model of the instruction set described in
``docs/ISA.md`` and implemented in ``rtl/`` (control.v + cpu.v + alu.v).  It does
not model cycles: each instruction executes at once, but it reproduces exactly
the **architectural state** after each one (registers A-D, flags Z/C/N/V, I, SP,
PC) and the contents of RAM.

Its reason for existing is the **differential fuzz** (``tools/difftest.py``): a
program is run on the RTL (with ``tb/cpu_dump_tb.v``) and on this model and they
are compared instruction by instruction.  A failure here or a failure there
means a discrepancy between the model and the hardware.

Both share the same input convention as the testbenches:
``in_data = 0x10 + port`` (port ``n`` reads ``0x10+n``).

Usage::

    python3 tools/iss.py programs/countdown.hex --trace
    python3 tools/iss.py programs/irq.hex --irq 0 --irq-vector 0x10
"""

from __future__ import annotations

import sys
from pathlib import Path

MASK = 0xFF
REGS = ("A", "B", "C", "D")

# ALU operation codes (match alu.v and the ISA opcode).
ADD, SUB, AND, OR, XOR, CMP, SHIFT, MUL, DIV = 0x5, 0x6, 0x7, 0x8, 0x9, 0xA, 0xB, 0xC, 0xD
# Extended ALU operations (prefix 0xFA).  They match the codes used by alu.v
# and control.v and are free of collisions with the opcodes above.
NEG, NOT, ADC_SBC, ROT = 0x0, 0x3, 0x4, 0xE

# Extended (prefixed, 0xFA) sub-operations (byte2[7:4]); see asm/assembler.py.
XOP_NEG, XOP_NOT, XOP_ADC, XOP_SBC = 0x0, 0x1, 0x2, 0x3
XOP_SWAP, XOP_ROL, XOP_ROR = 0x4, 0x5, 0x6
XOP_LDW, XOP_STW = 0x7, 0x8
XOP_TEST, XOP_PUSHF, XOP_POPF = 0x9, 0xA, 0xB
XOP_ADCW, XOP_SUBW = 0xC, 0xD
XOP_RETI = 0xE

# FSM state encodings (same as rtl/control.v; documentation only: the ISS is
# not cycle-accurate).
S_FETCH, S_OPR, S_EXEC, S_IRQ, S_HLT, S_OPR2, S_EXEC2, S_IN = range(8)


def needs_operand(instr: int) -> bool:
    """True if the instruction takes 2 bytes (same rule as control.v).

    The prefix 0xFA is NOT included here: its second byte is the extended
    sub-operation (xop), not the operand, and it can even take a third byte
    (LDW/STW).  ``step`` and ``instruction_length`` handle it explicitly.
    """
    fop = instr >> 4
    return fop in (0x1, 0x3, 0x4, 0xC, 0xD) or instr in (0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9)


def instruction_length(mem: list[int], pc: int) -> int:
    """Length in bytes (1, 2 or 3) of the instruction at ``mem[pc]``.

    Replicates the length decision of control.v, including the prefix 0xFA:
    LDW/STW (subops 7/8) take a third byte (the displacement).
    """
    instr = mem[pc & MASK]
    if instr == 0xFA:
        xb = mem[(pc + 1) & MASK]
        return 3 if (xb >> 4) in (XOP_LDW, XOP_STW) else 2
    return 2 if needs_operand(instr) else 1


def alu(op: int, sh: int, a: int, b: int, cin: int = 0) -> tuple[int, int, int, int, int]:
    """Replicates alu.v: returns (y, c, v, z, n).

    ``cin`` is the carry/borrow input for ADC/SBC and the bit rotated in by
    ROL/ROR (it is flag C, like in the RTL).
    """
    a &= MASK
    b &= MASK
    cin &= 1
    y, c, v = b, 0, 0
    if op in (ADD, SUB, CMP):
        resta = op in (SUB, CMP)
        b_eff = (~b & MASK) if resta else b
        suma = a + b_eff + (1 if resta else 0)
        y = suma & MASK
        c = (suma >> 8) & 1
        a7, b7, y7 = (a >> 7) & 1, (b >> 7) & 1, (y >> 7) & 1
        v = ((a7 ^ b7) & (a7 ^ y7)) if resta else ((~(a7 ^ b7) & 1) & (a7 ^ y7))
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
    elif op == NEG:  # NEG rd: y = 0 - a
        suma = 256 - a  # 0 + ~a + 1
        y = suma & MASK
        c = (suma >> 8) & 1  # 1 only when a == 0 (no borrow)
        v = 1 if a == 0x80 else 0  # a[7] & y[7]
    elif op == NOT:  # NOT rd: y = ~a (C=0, V=0)
        y = ~a & MASK
    elif op == ADC_SBC:  # sh=0 ADC: a+b+cin ; sh=1 SBC: a-b-cin
        if sh:
            suma = a + (~b & MASK) + ((1 - cin) & 1)
        else:
            suma = a + b + cin
        y = suma & MASK
        c = (suma >> 8) & 1
        a7, b7, y7 = (a >> 7) & 1, (b >> 7) & 1, (y >> 7) & 1
        v = (
            ((a7 ^ b7) & (a7 ^ y7))
            if sh  # SBC (like SUB)
            else ((~(a7 ^ b7) & 1) & (a7 ^ y7))
        )  # ADC (like ADD)
        v &= 1
    elif op == ROT:  # sh=0 ROL, sh=1 ROR (through carry)
        if sh:
            y = ((cin << 7) | (a >> 1)) & MASK
            c = a & 1
        else:
            y = ((a << 1) | cin) & MASK
            c = (a >> 7) & 1
    # else: pass-through (LDI/MOV), y = b, c = 0, v = 0
    z = 1 if y == 0 else 0
    n = (y >> 7) & 1
    return y, c, v, z, n


def branch_cond(fam: int, rs: int, fz: int, fc: int, fn: int, fv: int) -> int:
    """Replicates the Jcc branch condition of control.v."""
    menor = fn ^ fv  # signed_lt (N != V)
    if fam == 0:
        return (fz, 1 - fz, fc, 1 - fc)[rs]
    if fam == 1:
        return (menor, 1 - menor, fz | menor, (1 - fz) & (1 - menor))[rs]
    return (fv, 1 - fv, fn, 1 - fn)[rs]


class ISS:
    """Reference simulator for cpu8."""

    def __init__(
        self,
        mem: list[int] | None = None,
        irq_vector: int = 0x08,
        in_fn=None,
        irq_at: int | None = None,
    ):
        self.mem = [0] * 256
        if mem:
            for i, b in enumerate(mem[:256]):
                self.mem[i] = b & MASK
        self.irq_vector = irq_vector & MASK
        # Testbench input convention: port n -> 0x10 + n.
        self.in_fn = in_fn or (lambda port: (0x10 + port) & MASK)
        # irq level model (None = never).  If it is an integer, the differential
        # testbench convention is replicated: irq active once >= irq_at
        # instructions have been retired (see tb/cpu_dump_tb.v and run()).
        self.irq_at = irq_at
        self.reset()

    def reset(self) -> None:
        self.regs = [0, 0, 0, 0]
        self.PC = 0
        self.SP = 0xF0
        self.IR = 0
        self.operand = 0
        self.xop = 0
        self.fz = self.fc = self.fn = self.fv = self.fi = 0
        self.flags_saved = (0, 0, 0, 0)  # C,Z,N,V captured on IRQ entry
        self.out_data = 0
        self.out_port = 0
        self.halted = False
        self.rows: list[tuple] = []
        self.outs: list[tuple[int, int]] = []
        self.irqs = 0
        self.limit_reached = False

    # -- one instruction -----------------------------------------------------
    def step(self) -> tuple:
        pc0 = self.PC
        instr = self.mem[self.PC]
        self.PC = (self.PC + 1) & MASK
        self.IR = instr
        ext = instr == 0xFA
        if ext:
            # byte2 is the extended sub-operation, not the operand.
            self.xop = self.mem[self.PC]
            self.PC = (self.PC + 1) & MASK
            if (self.xop >> 4) in (XOP_LDW, XOP_STW):
                self.operand = self.mem[self.PC]  # byte3 = displacement
                self.PC = (self.PC + 1) & MASK
        elif needs_operand(instr):
            self.operand = self.mem[self.PC]
            self.PC = (self.PC + 1) & MASK

        op = instr >> 4
        rd = (instr >> 2) & 3
        rs = instr & 3
        opnd = self.operand
        reg = self.regs
        out_valid = 0

        # --- write result + flags (helpers) ---
        def set_flags(y, c, v, z, n, we=True, c_we=True):
            if we:
                self.fz, self.fn, self.fv = z, n, v
            if c_we:
                self.fc = c

        def do_alu(opc, sh, a, b, dst=None, c_we=True, we=True, cin=0):
            y, c, v, z, n = alu(opc, sh, a, b, cin)
            if dst is not None:
                reg[dst] = y
            if we:
                set_flags(y, c, v, z, n, we=True, c_we=c_we)
            return y

        if ext:  # extended (prefixed 0xFA) instruction
            xop, xd, xs = self.xop >> 4, (self.xop >> 2) & 3, self.xop & 3
            if xop == XOP_NEG:  # NEG rd
                do_alu(NEG, 0, reg[xd], 0, dst=xd)
            elif xop == XOP_NOT:  # NOT rd
                do_alu(NOT, 0, reg[xd], 0, dst=xd)
            elif xop == XOP_ADC:  # ADC rd,rs: rd + rs + C
                do_alu(ADC_SBC, 0, reg[xd], reg[xs], dst=xd, cin=self.fc)
            elif xop == XOP_SBC:  # SBC rd,rs: rd - rs - C
                do_alu(ADC_SBC, 1, reg[xd], reg[xs], dst=xd, cin=self.fc)
            elif xop == XOP_SWAP:  # SWAP rd,rs (no flags)
                reg[xd], reg[xs] = reg[xs], reg[xd]
            elif xop == XOP_ROL:  # ROL rd (through C)
                do_alu(ROT, 0, reg[xd], 0, dst=xd, cin=self.fc)
            elif xop == XOP_ROR:  # ROR rd (through C)
                do_alu(ROT, 1, reg[xd], 0, dst=xd, cin=self.fc)
            elif xop == XOP_LDW:  # LDW rd,[rs+off]: C only
                ea = reg[xs] + opnd  # 9 bits
                reg[xd] = self.mem[ea & MASK]
                self.fc = (ea >> 8) & 1
            elif xop == XOP_STW:  # STW rd,[rs+off]: C only
                ea = reg[xs] + opnd  # 9 bits
                self.mem[ea & MASK] = reg[xd]
                self.fc = (ea >> 8) & 1
            elif xop == XOP_TEST:  # TEST rd,rs: flags only, rd untouched
                do_alu(AND, 0, reg[xd], reg[xs], dst=None)
            elif xop == XOP_PUSHF:  # PUSHF: flags byte -> stack
                fb = (
                    (int(self.fi) << 4)
                    | (int(self.fv) << 3)
                    | (int(self.fn) << 2)
                    | (int(self.fz) << 1)
                    | int(self.fc)
                )
                self.mem[self.SP] = fb
                self.SP = (self.SP - 1) & MASK
            elif xop == XOP_POPF:  # POPF: stack -> flags (C,Z,N,V,I)
                self.SP = (self.SP + 1) & MASK
                fb = self.mem[self.SP]
                self.fc, self.fz = fb & 1, (fb >> 1) & 1
                self.fn, self.fv = (fb >> 2) & 1, (fb >> 3) & 1
                self.fi = (fb >> 4) & 1
            elif xop == XOP_RETI:  # RETI: RET + restore the flags saved on entry
                self.SP = (self.SP + 1) & MASK
                self.PC = self.mem[self.SP]
                self.fc, self.fz, self.fn, self.fv = self.flags_saved
            elif xop in (XOP_ADCW, XOP_SUBW):
                # 16-bit pair op in two steps, mirroring S_EXEC + S_EXEC2:
                # low byte first (carry captured in c), then the high bytes
                # (xd|1, xs|1).  SUBW passes the inverted carry because the
                # ALU subtracts its cin and c means "no borrow".
                sh = 0 if xop == XOP_ADCW else 1
                y, c, v, z, n = alu(ADC_SBC, sh, reg[xd], reg[xs], self.fc)
                reg[xd] = y
                z_lo = int(y == 0)
                cin = c if sh == 0 else 1 - c
                y2, c2, v2, z2, n2 = alu(ADC_SBC, sh, reg[xd | 1], reg[xs | 1], cin)
                reg[xd | 1] = y2
                self.fz = z_lo & z2  # 16-bit zero
                self.fn, self.fv, self.fc = n2, v2, c2
            # other xop: reserved (2-byte no-op)
        elif op == 0x0:  # INC/DEC/PUSH/POP (register in rs)
            if rd == 0b00:  # INC rs: Z,N,V yes; C no
                do_alu(ADD, 0, reg[rs], 1, dst=rs, c_we=False)
            elif rd == 0b01:  # DEC rs
                do_alu(SUB, 0, reg[rs], 1, dst=rs, c_we=False)
            elif rd == 0b10:  # PUSH rs
                self.mem[self.SP] = reg[rs]
                self.SP = (self.SP - 1) & MASK
            else:  # POP rs
                self.SP = (self.SP + 1) & MASK
                reg[rs] = self.mem[self.SP]
        elif op == 0x1:  # LDI / ADDI / SUBI / CMPI
            sub = rs
            if sub == 0b00:  # LDI rd, imm (no flags)
                reg[rd] = opnd
            elif sub == 0b01:  # ADDI
                do_alu(ADD, 0, reg[rd], opnd, dst=rd)
            elif sub == 0b10:  # SUBI
                do_alu(SUB, 0, reg[rd], opnd, dst=rd)
            else:  # CMPI (flags only)
                do_alu(CMP, 0, reg[rd], opnd, dst=None)
        elif op == 0x2:  # MOV rd,rs
            reg[rd] = reg[rs]
        elif op == 0x3:  # LD rd,[a] / LD rd,[rs+off]
            addr = opnd if rs == 0 else (reg[rs] + opnd) & MASK
            reg[rd] = self.mem[addr]
        elif op == 0x4:  # ST rd,[a] / ST rd,[rs+off]
            addr = opnd if rs == 0 else (reg[rs] + opnd) & MASK
            self.mem[addr] = reg[rd]
        elif op in (ADD, SUB, AND, OR, XOR):  # ALU register-register
            do_alu(op, 0, reg[rd], reg[rs], dst=rd)
        elif op == CMP:
            do_alu(CMP, 0, reg[rd], reg[rs], dst=None)
        elif op == SHIFT:  # SHL/SHR rd (sh = rs[0])
            do_alu(SHIFT, rs & 1, reg[rd], 0, dst=rd)
        elif op == 0xC:  # JMP / CALL
            if rs == 0b01:  # CALL: push return address
                self.mem[self.SP] = self.PC
                self.SP = (self.SP - 1) & MASK
            self.PC = opnd  # JMP (and reserved 10/11) jump
        elif op == 0xD:  # Jcc <<family rd>>
            if branch_cond(rd, rs, self.fz, self.fc, self.fn, self.fv):
                self.PC = opnd
        elif op == 0xE:  # OUT rd / IN rd (port 0)
            if rs == 0b00:  # OUT rd
                out_valid = 1
                self.out_data, self.out_port = reg[rd], 0
                self.outs.append((reg[rd], 0))
            elif rs == 0b01:  # IN rd
                reg[rd] = self.in_fn(0)
            # rs=10/11: reserved (no-op)
        elif op == 0xF:
            if instr == 0xF0:  # HLT
                self.halted = True
            elif instr == 0xF1:  # RET
                self.SP = (self.SP + 1) & MASK
                self.PC = self.mem[self.SP]
            elif instr == 0xF2:  # EI
                self.fi = 1
            elif instr == 0xF3:  # DI
                self.fi = 0
            elif instr == 0xF4:  # LD rd,[rs] (indirect)
                d, s = (opnd >> 2) & 3, opnd & 3
                reg[d] = self.mem[reg[s]]
            elif instr == 0xF5:  # ST rd,[rs] (indirect)
                d, s = (opnd >> 2) & 3, opnd & 3
                self.mem[reg[s]] = reg[d]
            elif instr == 0xF6:  # MUL rd,rs
                d, s = (opnd >> 2) & 3, opnd & 3
                do_alu(MUL, 0, reg[d], reg[s], dst=d)
            elif instr == 0xF7:  # DIV rd,rs
                d, s = (opnd >> 2) & 3, opnd & 3
                do_alu(DIV, 0, reg[d], reg[s], dst=d)
            elif instr == 0xF8:  # OUT n,rd (port n)
                d, n = (opnd >> 2) & 3, opnd & 3
                out_valid = 1
                self.out_data, self.out_port = reg[d], n
                self.outs.append((reg[d], n))
            elif instr == 0xF9:  # IN n,rd (port n)
                d, n = (opnd >> 2) & 3, opnd & 3
                reg[d] = self.in_fn(n)
            # 0xFB..0xFF (and reserved 0xFA subops): no-op
            # 0xFA itself is decoded above, in the `if ext:` branch.

        row = (
            pc0,
            instr,
            self.regs[0],
            self.regs[1],
            self.regs[2],
            self.regs[3],
            self.fz,
            self.fc,
            self.fn,
            self.fv,
            self.SP,
            self.PC,
            out_valid,
            self.out_data,
            self.out_port,
            self.fi,
            self._saved_bits(),
        )
        return row

    def _saved_bits(self) -> int:
        """C/Z/N/V snapshot as the RTL's 4-bit flags_saved (V,N,Z,C)."""
        c, z, n, v = self.flags_saved
        return (v << 3) | (n << 2) | (z << 1) | c

    def take_irq(self) -> None:
        """Services an interrupt (S_IRQ state): pushes PC, clears I and jumps to the vector.

        It does not generate a trace row: in the RTL the S_IRQ state does not go
        through S_EXEC, so no instruction is retired.  This has to be replicated
        the same way.
        """
        self.mem[self.SP] = self.PC
        self.SP = (self.SP - 1) & MASK
        self.flags_saved = (self.fc, self.fz, self.fn, self.fv)
        self.fi = 0
        self.PC = self.irq_vector
        self.irqs += 1

    def run(self, max_steps: int = 5000) -> list[tuple]:
        """Runs until HLT or ``max_steps``; returns the trace rows.

        If ``irq_at`` is not None, the irq level is modeled as in the
        differential testbench (``irq = (n_retired >= irq_at)``).  At the
        beginning of each instruction, if the I flag is set and there is a
        pending irq, the interrupt is serviced (without retiring an instruction,
        like the RTL's S_IRQ state).
        """
        self.rows = []
        self.limit_reached = False
        guard = 0
        limite = 10 * max_steps + 1000
        while not self.halted and len(self.rows) < max_steps:
            guard += 1
            if guard > limite:  # safety net against pathological loops
                break
            if self.irq_at is not None and self.fi and len(self.rows) >= self.irq_at:
                self.take_irq()
                continue
            self.rows.append(self.step())
        self.limit_reached = not self.halted and len(self.rows) >= max_steps
        return self.rows

    # -- output in the same format as tb/cpu_dump_tb.v -----------------------
    @staticmethod
    def _row_line(r: tuple) -> str:
        pc, ir, a, b, c, d, z, cf, n, v, sp, pcn, ov, od, op, fi, sv = r
        return (
            f"I {pc:02X} {ir:02X} {a:02X} {b:02X} {c:02X} {d:02X} "
            f"{z} {cf} {n} {v} {sp:02X} {pcn:02X} {ov} {od:02X} {op:02X} "
            f"{fi} {sv:04b}"
        )

    def dump(self) -> list[str]:
        # Same order as tb/cpu_dump_tb.v: rows, then END, then RAM.
        lineas = [self._row_line(r) for r in self.rows]
        lineas.append(f"END {len(self.rows)}")
        lineas.append("M " + " ".join(f"{b:02X}" for b in self.mem))
        return lineas


def _leer_hex(path: Path) -> list[int]:
    """Reads bytes from a ``.hex``; ``;`` and ``//`` comments are ignored."""
    datos = []
    for linea in path.read_text().splitlines():
        linea = linea.split(";", 1)[0].split("//", 1)[0]
        for tok in linea.split():
            datos.append(int(tok, 16))
    return datos


def _opcion_entera(
    args: list[str], nombre: str, defecto: int | None
) -> tuple[int | None, int | None]:
    """Extracts ``--name VALUE`` from ``args``; returns ``(value, error)``.

    ``error`` is the exit code when parsing fails (2), else None.  The option and
    its value are removed from ``args``.
    """
    if nombre not in args:
        return defecto, None
    k = args.index(nombre)
    if k + 1 >= len(args):
        print(f"iss: {nombre} expects a number", file=sys.stderr)
        return None, 2
    try:
        valor = int(args[k + 1], 0)
    except ValueError:
        print(f"iss: invalid {nombre} value '{args[k + 1]}'", file=sys.stderr)
        return None, 2
    del args[k : k + 2]
    return valor, None


def main(argv: list[str]) -> int:
    args = argv[1:]
    trace = "--trace" in args
    args = [a for a in args if a != "--trace"]
    max_steps, err = _opcion_entera(args, "--max", 5000)
    if err:
        return err
    irq_at, err = _opcion_entera(args, "--irq", None)
    if err:
        return err
    irq_vector, err = _opcion_entera(args, "--irq-vector", 0x08)
    if err:
        return err
    if not 0 <= irq_vector <= 0xFF:
        print(f"iss: --irq-vector 0x{irq_vector:X} out of range 0x00..0xFF", file=sys.stderr)
        return 2
    if irq_at is not None and irq_at < 0:
        print("iss: --irq expects a non-negative instruction count", file=sys.stderr)
        return 2
    if not args:
        print(__doc__)
        return 2
    try:
        memoria = _leer_hex(Path(args[0]))
    except OSError as exc:
        print(f"iss: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"iss: invalid hex file: {exc}", file=sys.stderr)
        return 2
    iss = ISS(memoria, irq_vector=irq_vector, irq_at=irq_at)
    iss.run(max_steps)
    if iss.limit_reached:
        print(f"iss: (step limit reached) after {max_steps} instructions", file=sys.stderr)
    if trace:
        for line in iss.dump():
            print(line)
    else:
        print(
            f"{len(iss.rows)} instructions; OUT = " + " ".join(f"{v:02X}/{p}" for v, p in iss.outs)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
