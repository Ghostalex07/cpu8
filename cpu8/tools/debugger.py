#!/usr/bin/env python3
"""Interactive debugger for the cpu8 CPU, built on the reference model (ISS).

It loads a program (``.asm`` or ``.hex``), runs it instruction by instruction on
``tools/iss.py`` and lets you control and inspect it like a small ``gdb``:
breakpoints, watchpoints, register/memory dumps and on-the-fly disassembly.

It also reports the **cycle** count: it models the 5-state FSM of
``rtl/control.v`` (FETCH + EXEC = 2 cycles for 1-byte instructions,
FETCH + OPR + EXEC = 3 for 2-byte ones, and 1 cycle per interrupt serviced), so
it can be used to measure the CPI of a program.

Usage::

    python3 tools/debugger.py programs/fibonacci.asm
    python3 tools/debugger.py programs/fibonacci.hex --irq 5
    python3 tools/debugger.py programs/countdown.asm --exec "break loop; run; regs"

Type ``help`` inside the debugger for the list of commands.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _sub in ("tools", "asm"):
    if str(_ROOT / _sub) not in sys.path:
        sys.path.insert(0, str(_ROOT / _sub))

import assembler  # noqa: E402
import disasm  # noqa: E402
import iss as iss_mod  # noqa: E402

REGS = ("A", "B", "C", "D")
# Watchable flags (fC is the flag, C is register C).
_FLAG_ATTRS = {"fZ": "fz", "fC": "fc", "fN": "fn", "fV": "fv", "fI": "fi"}
# Watchable registers: name -> (attribute, index | None).
_REG_ATTRS = {
    "A": ("regs", 0),
    "B": ("regs", 1),
    "C": ("regs", 2),
    "D": ("regs", 3),
    "SP": ("SP", None),
    "PC": ("PC", None),
    "IR": ("IR", None),
    "OP": ("operand", None),
}
# Instruction length in bytes (1/2/3), for the cycle model and hints.
_LENGTH = iss_mod.instruction_length


def load_program(path: Path) -> tuple[list[int], dict[str, int]]:
    """Loads a ``.asm`` (assembled on the fly) or ``.hex`` program.

    Returns ``(bytes, labels)``; for a ``.hex`` there are no labels.
    """
    if path.suffix.lower() == ".asm":
        mem, labels, _ = assembler.ensamblar(path.read_text(encoding="utf-8-sig"))
        return list(mem), dict(labels)
    return disasm.leer_hex(path), {}


def _to_int(tok: str, labels: dict[str, int]) -> int:
    """Parses an address/operand: label, ``L_xxxx``, ``$20``, ``0x20`` or decimal."""
    s = tok.strip()
    if s in labels:
        return labels[s]
    if s.upper().startswith("L_") and len(s) > 2:
        return int(s[2:], 16)
    if s.startswith("$"):
        s = "0x" + s[1:]
    return int(s, 0)


class Debugger:
    """State and command handling of the interactive debugger."""

    def __init__(
        self,
        mem: list[int],
        labels: dict[str, int] | None = None,
        *,
        irq_vector: int = 0x08,
        irq_at: int | None = None,
        max_steps: int = 100000,
        out=print,
    ) -> None:
        self.program = list(mem)
        self.labels = dict(labels or {})
        self.inv_labels = {v: k for k, v in self.labels.items()}
        self.irq_vector = irq_vector
        self.irq_at = irq_at
        self.max_steps = max_steps
        self.out = out
        self.breakpoints: set[int] = set()
        self.watches: dict[str, int] = {}
        self.reset()

    # ---- lifecycle --------------------------------------------------------
    def reset(self) -> None:
        self.iss = iss_mod.ISS(self.program, irq_vector=self.irq_vector, irq_at=self.irq_at)
        self.cycles = 0
        self.retired = 0
        self.irqs = 0
        self.rows: list[tuple] = []
        self.hit_break: int | None = None
        self.watches = {t: self._read(t) for t in self.watches}

    # ---- low-level access -------------------------------------------------
    def _read(self, target: str) -> int:
        t = target.strip()
        if t.startswith("@"):
            return self.iss.mem[_to_int(t[1:], self.labels) & 0xFF]
        if t in _FLAG_ATTRS:
            return getattr(self.iss, _FLAG_ATTRS[t])
        if t in _REG_ATTRS:
            attr, idx = _REG_ATTRS[t]
            return getattr(self.iss, attr)[idx] if idx is not None else getattr(self.iss, attr)
        raise ValueError(f"unknown watch target '{target}'")

    def _valid_target(self, target: str) -> bool:
        try:
            self._read(target)
            return True
        except (ValueError, TypeError):
            return False

    def _cycles(self) -> int:
        # Cycles model control.v's FSM: one byte = 2 cycles (FETCH+EXEC) and
        # each additional fetched byte adds one (S_OPR, S_OPR2).  ADCW/SUBW
        # add a 2nd EXEC cycle (S_EXEC2) for the high byte of the pair.
        n = _LENGTH(self.iss.mem, self.iss.PC) + 1
        mem, pc = self.iss.mem, self.iss.PC
        if (
            mem[pc] == 0xFA
            and pc + 1 < len(mem)
            and ((mem[pc + 1] >> 4) in (iss_mod.XOP_ADCW, iss_mod.XOP_SUBW))
        ):
            n += 1
        return n

    def _step_one(self) -> None:
        """Executes exactly one instruction (and one interrupt cycle if pending)."""
        if self.iss.irq_at is not None and self.iss.fi and self.retired >= self.iss.irq_at:
            self.iss.take_irq()
            self.irqs += 1
            self.cycles += 1
            return
        n = self._cycles()
        self.rows.append(self.iss.step())
        self.retired += 1
        self.cycles += n
        self._check_watches()

    def _check_watches(self) -> None:
        for target in list(self.watches):
            val = self._read(target)
            if val != self.watches[target]:
                self.out(f"watch: {target} {self.watches[target]:02X} -> {val:02X}")
                self.watches[target] = val

    # ---- execution primitives --------------------------------------------
    def step(self, n: int = 1) -> None:
        for _ in range(max(1, n)):
            if self.iss.halted:
                self.out("(the CPU is halted; use 'reset')")
                break
            self._step_one()
        self.out(self.state())

    def next(self, n: int = 1) -> None:
        """Steps one instruction, but *over* a ``CALL`` (it runs until it returns)."""
        for _ in range(max(1, n)):
            if self.iss.halted:
                self.out("(the CPU is halted; use 'reset')")
                break
            b = self.iss.mem[self.iss.PC]
            if (b >> 4) == 0xC and (b & 3) == 1:  # CALL: run until it returns
                ret = (self.iss.PC + 2) & 0xFF
                self._step_one()
                guard = 0
                while (
                    not self.iss.halted
                    and self.iss.PC != ret
                    and self.iss.PC not in self.breakpoints
                    and guard < self.max_steps
                ):
                    self._step_one()
                    guard += 1
            else:
                self._step_one()
        self.out(self.state())

    def run(self, max_steps: int | None = None) -> None:
        """Runs until a breakpoint, HLT or the step limit."""
        limit = self.max_steps if max_steps is None else max_steps
        start = self.iss.PC
        self.hit_break = None
        steps = 0
        while not self.iss.halted and steps < limit:
            if self.iss.PC in self.breakpoints and not (steps == 0 and start == self.iss.PC):
                self.hit_break = self.iss.PC
                break
            self._step_one()
            steps += 1
        if self.iss.halted:
            self.out(f"(halted after {self.retired} instructions)")
        elif self.hit_break is not None:
            self.out(f"(breakpoint at 0x{self.hit_break:02X}{self._sym(self.hit_break)})")
        else:
            self.out(f"(stopped at the step limit: {limit})")
        self.out(self.state())

    # ---- formatting -------------------------------------------------------
    def _sym(self, addr: int) -> str:
        """`` (label)`` annotation for an address that has a symbol."""
        name = self.inv_labels.get(addr)
        return f" ({name})" if name else ""

    def state(self) -> str:
        r = self.iss.regs
        cpi = f"{self.cycles / self.retired:.2f}" if self.retired else "-"
        return (
            f"PC=0x{self.iss.PC:02X}{self._sym(self.iss.PC)} IR=0x{self.iss.IR:02X} "
            f"A={r[0]:02X} B={r[1]:02X} C={r[2]:02X} D={r[3]:02X} "
            f"Z={self.iss.fz} C={self.iss.fc} N={self.iss.fn} V={self.iss.fv} "
            f"I={self.iss.fi} SP=0x{self.iss.SP:02X} "
            f"| cyc={self.cycles} insn={self.retired} cpi={cpi}"
        )

    def cmd_disasm(self, addr: int | None = None, count: int = 8) -> None:
        i = self.iss.PC if addr is None else addr
        for _ in range(max(1, count)):
            if i > 0xFF:
                break
            if i in self.inv_labels:
                self.out(f"{self.inv_labels[i]}:")
            text, ln = disasm.decodificar(self.iss.mem, i)
            bs = " ".join(f"{x:02X}" for x in self.iss.mem[i : i + ln])
            marker = ">" if i == self.iss.PC else " "
            self.out(f"{marker} {i:04X}: {bs:<8} {text}")
            i += ln

    def cmd_mem(self, addr: int, count: int = 64) -> None:
        end = min(256, addr + max(1, count))
        base = addr & ~0xF
        while base < end:
            cells = " ".join(f"{self.iss.mem[base + j]:02X}" for j in range(16) if base + j < 256)
            self.out(f"{base:02X}: {cells}")
            base += 16

    # ---- command dispatch -------------------------------------------------
    def handle(self, line: str) -> bool:
        """Runs one command line. Returns False when it is time to quit."""
        line = line.split("#", 1)[0].strip()
        if not line:
            return True
        parts = line.split()
        cmd, args = parts[0].lower(), parts[1:]
        try:
            return self._dispatch(cmd, args)
        except (ValueError, IndexError) as e:
            self.out(f"error: {e}")
            return True

    def _dispatch(self, cmd: str, args: list[str]) -> bool:
        if cmd in ("q", "quit", "exit"):
            return False
        if cmd in ("h", "help", "?"):
            self.out(HELP)
        elif cmd in ("s", "step"):
            self.step(int(args[0], 0) if args else 1)
        elif cmd in ("n", "next"):
            self.next(int(args[0], 0) if args else 1)
        elif cmd in ("c", "cont", "continue", "r", "run"):
            self.run()
        elif cmd in ("b", "break"):
            if not args:
                self.out("usage: break <address|label>")
            else:
                a = _to_int(args[0], self.labels) & 0xFF
                self.breakpoints.add(a)
                self.out(f"breakpoint at 0x{a:02X}{self._sym(a)}")
        elif cmd in ("d", "delete"):
            a = _to_int(args[0], self.labels) & 0xFF
            self.breakpoints.discard(a)
            self.out(f"breakpoint removed at 0x{a:02X}{self._sym(a)}")
        elif cmd in ("clear",):
            self.breakpoints.clear()
            self.out("all breakpoints removed")
        elif cmd in ("bl", "breakpoints"):
            if not self.breakpoints:
                self.out("(no breakpoints)")
            for a in sorted(self.breakpoints):
                self.out(f"breakpoint at 0x{a:02X}{self._sym(a)}")
        elif cmd in ("w", "watch"):
            if not args:
                self._list_watches()
            else:
                self._add_watch(args[0])
        elif cmd in ("unwatch",):
            if args and args[0] in self.watches:
                del self.watches[args[0]]
                self.out(f"watch removed: {args[0]}")
            else:
                self.out(f"not watching '{args[0] if args else ''}'")
        elif cmd in ("regs", "info", "i"):
            self.out(self.state())
        elif cmd in ("m", "mem"):
            if not args:
                self.out("usage: mem <address> [count]")
            else:
                cnt = int(args[1], 0) if len(args) > 1 else 64
                self.cmd_mem(_to_int(args[0], self.labels) & 0xFF, cnt)
        elif cmd in ("l", "list", "disasm"):
            addr = _to_int(args[0], self.labels) if args else None
            cnt = int(args[1], 0) if len(args) > 1 else 8
            self.cmd_disasm(addr, cnt)
        elif cmd in ("trace",):
            n = int(args[0], 0) if args else 20
            for row in self.rows[-n:]:
                self.out(_format_row(row, self.inv_labels))
        elif cmd in ("out", "outs"):
            if not self.iss.outs:
                self.out("(no OUT yet)")
            else:
                self.out("OUT: " + " ".join(f"{v:02X}/{p}" for v, p in self.iss.outs))
        elif cmd in ("cycles",):
            cpi = f"{self.cycles / self.retired:.2f}" if self.retired else "-"
            self.out(
                f"cycles={self.cycles} instructions={self.retired} interrupts={self.irqs} cpi={cpi}"
            )
        elif cmd in ("reset",):
            self.reset()
            self.out("(reset)")
        elif cmd in ("labels",):
            if not self.labels:
                self.out("(no labels: the program was loaded from a .hex)")
            for name, a in sorted(self.labels.items(), key=lambda kv: kv[1]):
                self.out(f"  {name:<12} = 0x{a:02X}")
        else:
            self.out(f"unknown command '{cmd}'; type 'help'")
        return True

    def _add_watch(self, target: str) -> None:
        if not self._valid_target(target):
            self.out(
                f"error: cannot watch '{target}' "
                f"(registers A-D/SP/PC/IR/OP, flags fZ/fC/fN/fV/fI, or @address)"
            )
            return
        self.watches[target] = self._read(target)
        self.out(f"watching {target} (now 0x{self.watches[target]:02X})")

    def _list_watches(self) -> None:
        if not self.watches:
            self.out("(no watchpoints)")
        for target, val in self.watches.items():
            self.out(f"  {target} = 0x{val:02X}")


def _format_row(row: tuple, labels: dict[str, int] | None = None) -> str:
    (pc, ir, a, b, c, d, z, cf, n, v, sp, pcn, ov, od, op) = row
    sym = f" ({labels[pc]})" if labels and pc in labels else ""
    return (
        f"  PC={pc:02X}{sym} IR={ir:02X} A={a:02X} B={b:02X} C={c:02X} D={d:02X} "
        f"Z{z}C{cf}N{n}V{v} SP={sp:02X} -> {pcn:02X}" + (f"  OUT {od:02X}/{op}" if ov else "")
    )


HELP = """\
commands:
  s, step [n]        run n instructions (default 1)
  n, next [n]        like step, but steps over a CALL
  c, continue        run until a breakpoint, HLT or the step limit
  b, break <addr>    set a breakpoint (address, label or L_xxxx)
  d, delete <addr>   remove a breakpoint        clear   remove all
  bl, breakpoints    list the breakpoints (with their symbol, if any)
  w, watch <target>  watch a register (A-D/SP/PC/IR/OP), a flag (fZ/fC/fN/fV/fI)
                     or a memory cell (@0x20, @label); no arg lists them
  unwatch <target>   stop watching
  r/info, regs       show the CPU state
  m, mem <addr> [n]  dump n memory bytes (default 64)
  l, disasm [addr] [n]  disassemble n instructions (default 8)
  trace [n]          show the last n executed instructions
  out                show the OUT sequence
  cycles             cycle count, instructions and CPI
  labels             list the symbols (labels; .hex programs have none)
  reset              reset the CPU and the counters
  q, quit            exit
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Interactive debugger for cpu8 (over tools/iss.py)")
    ap.add_argument("program", help="program .asm or .hex to debug")
    ap.add_argument(
        "--irq",
        type=int,
        default=None,
        metavar="N",
        help="assert the irq signal after N retired instructions",
    )
    ap.add_argument(
        "--irq-vector",
        type=lambda s: int(s, 0),
        default=0x08,
        help="interrupt vector (default 0x08)",
    )
    ap.add_argument(
        "--max-steps",
        type=int,
        default=100000,
        help="instruction limit for 'continue' (default 100000)",
    )
    ap.add_argument(
        "-e",
        "--exec",
        dest="exec_cmds",
        action="append",
        default=[],
        metavar="CMDS",
        help="run these commands (';'-separated) and exit",
    )
    ap.add_argument(
        "--script", type=Path, default=None, help="read the commands from a file and exit"
    )
    args = ap.parse_args(argv)

    path = Path(args.program)
    if not path.exists():
        print(f"Error: cannot open '{path}'", file=sys.stderr)
        return 1
    try:
        mem, labels = load_program(path)
    except assembler.AssemblerError as e:
        print(f"Assembly error in {path}: {e}", file=sys.stderr)
        return 1

    dbg = Debugger(
        mem, labels, irq_vector=args.irq_vector, irq_at=args.irq, max_steps=args.max_steps
    )
    dbg.out(f"cpu8 debugger - {path} ({len(mem)} bytes)")
    if labels:
        dbg.out(
            "labels: "
            + ", ".join(f"{k}=0x{v:02X}" for k, v in sorted(labels.items(), key=lambda kv: kv[1]))
        )

    commands: list[str] = []
    for chunk in args.exec_cmds:
        commands.extend(c for c in chunk.split(";") if c.strip())
    if args.script is not None:
        commands.extend(args.script.read_text().splitlines())
    if commands:
        for cmd in commands:
            if not dbg.handle(cmd):
                break
        return 0

    return _repl(dbg)


def _repl(dbg: Debugger) -> int:
    while True:
        try:
            line = input("cpu8> ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            continue
        if not dbg.handle(line):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
