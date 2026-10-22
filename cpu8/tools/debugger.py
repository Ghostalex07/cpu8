#!/usr/bin/env python3
"""Interactive debugger for the cpu8 CPU, built on the reference model (ISS).

It loads a program (``.asm`` or ``.hex``), runs it instruction by instruction on
``tools/iss.py`` and lets you control and inspect it like a small ``gdb``:
breakpoints, watchpoints, register/memory dumps and on-the-fly disassembly.

It also reports the **cycle** count: it models the 8-state FSM of
``rtl/control.v`` (FETCH + EXEC = 2 cycles for 1-byte instructions,
FETCH + OPR + EXEC = 3 for 2-byte ones, one extra S_IN wait state for ``IN``,
and 2 cycles per interrupt serviced), so it can be used to measure the CPI of
a program.

Usage::

    python3 tools/debugger.py programs/fibonacci.asm
    python3 tools/debugger.py programs/fibonacci.hex --irq 5
    python3 tools/debugger.py programs/countdown.asm --exec "break loop; run; regs"

Type ``help`` inside the debugger for the list of commands.
"""

from __future__ import annotations

import argparse
import operator
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

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
# Case-insensitive watch names -> canonical spelling (registers and flags).
_WATCH_NAMES = {k.upper(): k for k in (*_REG_ATTRS, *_FLAG_ATTRS)}
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
    return _dec(s)


def _dec(tok: str) -> int:
    """Parses a count: decimal, ``0x``/``0b``, tolerating a leading zero ("08")."""
    try:
        return int(tok, 0)
    except ValueError:
        return int(tok, 10)


def _addr(tok: str, labels: dict[str, int]) -> int:
    """Parses an address and checks that it fits the 256-byte memory."""
    value = _to_int(tok, labels)
    if not 0 <= value <= 0xFF:
        raise ValueError(f"address 0x{value:X} is outside the 256-byte memory")
    return value


# ---- conditional breakpoints ----------------------------------------------
# Names accepted in an `if <expr>` clause.  `C` is register C (as in `watch C`);
# the carry flag is spelled `CF` (the `fC` form of `watch` is accepted too).
_COND_REGS = {"A": 0, "B": 1, "C": 2, "D": 3}
_COND_ATTRS = {"SP": "SP", "PC": "PC"}
_COND_FLAGS = {
    "CF": "fc",
    "ZF": "fz",
    "NF": "fn",
    "VF": "fv",
    "IF": "fi",
    "fC": "fc",
    "fZ": "fz",
    "fN": "fn",
    "fV": "fv",
    "fI": "fi",
}
_CMP_OPS: dict[str, Callable[[int, int], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}
_NUM_RE = re.compile(r"0[xX][0-9A-Fa-f]+|\d+")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Condition AST: ("num", value), ("reg", index), ("attr", name), ("flag", attr),
# ("mem", addr), ("cmp", op, left, right), ("and", left, right) or
# ("or", left, right).
_Node = tuple[object, ...]


def _tokenize_condition(text: str) -> list[str]:
    """Splits a condition into tokens; raises ValueError on an invalid character."""
    tokens: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        pair = text[i : i + 2]
        if pair in ("&&", "||", "==", "!=", "<=", ">="):
            tokens.append(pair)
            i += 2
            continue
        match = _NUM_RE.match(text, i) or _IDENT_RE.match(text, i)
        if match is not None:
            tokens.append(match.group())
            i = match.end()
            continue
        if ch in "<>()@":
            tokens.append(ch)
            i += 1
            continue
        raise ValueError(f"invalid character '{ch}' in condition")
    return tokens


class _ConditionParser:
    """Recursive-descent parser for the (safe, Python-free) condition grammar.

    Precedence, from lowest to highest: ``||``, ``&&``, comparisons, values.
    Parentheses group sub-expressions.
    """

    def __init__(self, text: str, labels: dict[str, int]) -> None:
        self.tokens = _tokenize_condition(text)
        self.labels = labels
        self.pos = 0

    def parse(self) -> _Node:
        if not self.tokens:
            raise ValueError("empty condition")
        node = self._or()
        if self._peek() is not None:
            raise ValueError(f"unexpected '{self._peek()}' in condition")
        return node

    def _peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _take(self) -> str:
        tok = self._peek()
        if tok is None:
            raise ValueError("incomplete condition: expected a value")
        self.pos += 1
        return tok

    def _accept(self, tok: str) -> bool:
        if self._peek() == tok:
            self.pos += 1
            return True
        return False

    def _or(self) -> _Node:
        node = self._and()
        while self._accept("||"):
            node = ("or", node, self._and())
        return node

    def _and(self) -> _Node:
        node = self._comparison()
        while self._accept("&&"):
            node = ("and", node, self._comparison())
        return node

    def _comparison(self) -> _Node:
        node = self._primary()
        tok = self._peek()
        if tok in _CMP_OPS:
            self.pos += 1
            node = ("cmp", tok, node, self._primary())
            if self._peek() in _CMP_OPS:
                raise ValueError("comparison operators cannot be chained")
        return node

    def _primary(self) -> _Node:
        tok = self._take()
        if tok == "(":
            node = self._or()
            if not self._accept(")"):
                raise ValueError("missing ')' in condition")
            return node
        if tok == "@":
            return self._memory()
        if _NUM_RE.fullmatch(tok):
            return ("num", _dec(tok))
        if _IDENT_RE.fullmatch(tok):
            known = tok in _COND_REGS or tok in _COND_ATTRS or tok in _COND_FLAGS
            name = tok if known else tok.upper()
            if name in _COND_REGS:
                return ("reg", _COND_REGS[name])
            if name in _COND_ATTRS:
                return ("attr", _COND_ATTRS[name])
            if name in _COND_FLAGS:
                return ("flag", _COND_FLAGS[name])
            raise ValueError(
                f"unknown name '{tok}' in condition (use A-D, SP, PC, CF/ZF/NF/VF/IF or @address)"
            )
        raise ValueError(f"unexpected '{tok}' in condition")

    def _memory(self) -> _Node:
        tok = self._peek()
        if tok is None or not (_NUM_RE.fullmatch(tok) or _IDENT_RE.fullmatch(tok)):
            raise ValueError("expected an address after '@' in condition")
        self.pos += 1
        if _IDENT_RE.fullmatch(tok) and tok not in self.labels:
            if not tok.upper().startswith("L_"):
                raise ValueError(f"unknown label '{tok}' in condition")
        try:
            addr = _addr(tok, self.labels)
        except ValueError as e:
            raise ValueError(f"invalid memory address '@{tok}' in condition: {e}") from e
        return ("mem", addr)


def _eval_condition(node: _Node, dbg: Debugger) -> int:
    """Evaluates a compiled condition against the current CPU state."""
    kind = node[0]
    if kind == "num":
        return cast(int, node[1])
    if kind == "reg":
        return dbg.iss.regs[cast(int, node[1])]
    if kind == "attr":
        return cast(int, getattr(dbg.iss, cast(str, node[1])))
    if kind == "flag":
        return cast(int, getattr(dbg.iss, cast(str, node[1])))
    if kind == "mem":
        return dbg.iss.mem[cast(int, node[1])]
    if kind == "cmp":
        left = _eval_condition(cast(_Node, node[2]), dbg)
        right = _eval_condition(cast(_Node, node[3]), dbg)
        return int(_CMP_OPS[cast(str, node[1])](left, right))
    left = _eval_condition(cast(_Node, node[1]), dbg)
    right = _eval_condition(cast(_Node, node[2]), dbg)
    if kind == "and":
        return int(bool(left) and bool(right))
    if kind == "or":
        return int(bool(left) or bool(right))
    raise ValueError(f"invalid compiled condition node {kind!r}")


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
        # Address -> expression source.  The compiled AST lives in a private
        # dict so `breakpoints` stays a simple set of addresses.
        self.conditions: dict[int, str] = {}
        self._condition_nodes: dict[int, _Node] = {}
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
        self.last_error = False
        self.watches = {t: self._read(t) for t in self.watches}

    # ---- low-level access -------------------------------------------------
    @staticmethod
    def _norm_watch(target: str) -> str:
        """Registers/flags are case-insensitive; memory cells keep their label."""
        t = target.strip()
        if t.startswith("@"):
            return t
        return _WATCH_NAMES.get(t.upper(), t)

    def _read(self, target: str) -> int:
        t = self._norm_watch(target)
        if t.startswith("@"):
            return self.iss.mem[_addr(t[1:], self.labels)]
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
        # add a 2nd EXEC cycle (S_EXEC2) for the high byte of the pair, and IN
        # adds the S_IN wait state used for the input-port handshake.
        n = _LENGTH(self.iss.mem, self.iss.PC) + 1
        mem, pc = self.iss.mem, self.iss.PC
        first = mem[pc]
        if first == 0xF9 or ((first >> 4) == 0xE and (first & 3) == 1):
            n += 1
        if (
            first == 0xFA
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
            # The RTL spends two states on an interrupt: the FETCH that detects
            # it (and does not fetch) and S_IRQ, which pushes the return PC.
            self.cycles += 2
            self._check_watches()
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

    def _breakpoint_hit(self, addr: int) -> bool:
        """True when ``addr`` is a breakpoint and its condition (if any) holds.

        Conditions are evaluated here, at the moment the PC reaches the
        breakpoint, never on every step.
        """
        if addr not in self.breakpoints:
            return False
        node = self._condition_nodes.get(addr)
        return node is None or _eval_condition(node, self) != 0

    # ---- execution primitives --------------------------------------------
    def step(self, n: int = 1) -> None:
        if n < 1:
            raise ValueError("count must be positive")
        for _ in range(n):
            if self.iss.halted:
                self.out("(the CPU is halted; use 'reset')")
                break
            self._step_one()
        self.out(self.state())

    def next(self, n: int = 1) -> None:
        """Steps one instruction, but *over* a ``CALL`` (it runs until it returns)."""
        if n < 1:
            raise ValueError("count must be positive")
        for _ in range(n):
            if self.iss.halted:
                self.out("(the CPU is halted; use 'reset')")
                break
            b = self.iss.mem[self.iss.PC]
            if (b >> 4) == 0xC and (b & 3) == 1:  # CALL: run until it returns
                ret = (self.iss.PC + 2) & 0xFF
                self._step_one()
                guard = 0
                while not self.iss.halted and self.iss.PC != ret and guard < self.max_steps:
                    if self._breakpoint_hit(self.iss.PC):
                        self.hit_break = self.iss.PC
                        break
                    self._step_one()
                    guard += 1
                if guard >= self.max_steps and not self.iss.halted and self.iss.PC != ret:
                    self.out(f"(next stopped at the step limit: {self.max_steps})")
            else:
                self._step_one()
        self.out(self.state())

    def cmd_until(self, target: int) -> None:
        """Runs until the PC reaches ``target`` (or HLT / a breakpoint / the limit).

        Always steps at least once, so ``until loop`` from the loop head stops
        on the *next* visit, not on the current one.
        """
        limit = self.max_steps
        self.hit_break = None
        steps = 0
        while not self.iss.halted and steps < limit:
            self._step_one()
            steps += 1
            if self.iss.PC == target:
                break
            if self._breakpoint_hit(self.iss.PC):
                self.hit_break = self.iss.PC
                break
        if self.iss.PC == target:
            self.out(f"(reached 0x{target:02X}{self._sym(target)} after {steps} instructions)")
        elif self.iss.halted:
            self.out(f"(halted after {self.retired} instructions)")
        elif self.hit_break is not None:
            self.out(f"(breakpoint at 0x{self.hit_break:02X}{self._sym(self.hit_break)})")
        else:
            self.out(f"(stopped at the step limit: {limit})")
        self.out(self.state())

    def run(self, max_steps: int | None = None) -> None:
        """Runs until a breakpoint, HLT or the step limit."""
        limit = self.max_steps if max_steps is None else max_steps
        start = self.iss.PC
        self.hit_break = None
        steps = 0
        while not self.iss.halted and steps < limit:
            if not (steps == 0 and start == self.iss.PC) and self._breakpoint_hit(self.iss.PC):
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
        if not 0 <= i <= 0xFF:
            raise ValueError(f"address 0x{i:X} is outside the 256-byte memory")
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
        self.last_error = False
        try:
            return self._dispatch(cmd, args)
        except (ValueError, IndexError) as e:
            self.last_error = True
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
        elif cmd in ("u", "until"):
            if not args:
                self.out("usage: until <address|label>")
            else:
                self.cmd_until(_addr(args[0], self.labels))
        elif cmd in ("b", "break"):
            if not args:
                self._list_breakpoints()
                if not self.breakpoints:
                    self.out("usage: break <address|label> [if <expression>]")
            else:
                self._add_breakpoint(args)
        elif cmd in ("d", "delete"):
            if not args:
                raise ValueError("usage: delete <address|label>")
            a = _addr(args[0], self.labels)
            self.breakpoints.discard(a)
            self.conditions.pop(a, None)
            self._condition_nodes.pop(a, None)
            self.out(f"breakpoint removed at 0x{a:02X}{self._sym(a)}")
        elif cmd in ("clear",):
            self.breakpoints.clear()
            self.conditions.clear()
            self._condition_nodes.clear()
            self.out("all breakpoints removed")
        elif cmd in ("bl", "breakpoints"):
            self._list_breakpoints()
        elif cmd in ("w", "watch"):
            if not args:
                self._list_watches()
            else:
                self._add_watch(args[0])
        elif cmd in ("unwatch",):
            objetivo = self._norm_watch(args[0]) if args else ""
            if objetivo in self.watches:
                del self.watches[objetivo]
                self.out(f"watch removed: {objetivo}")
            else:
                self.out(f"not watching '{args[0] if args else ''}'")
        elif cmd in ("regs", "info", "i"):
            self.out(self.state())
        elif cmd in ("m", "mem"):
            if not args:
                self.out("usage: mem <address> [count]")
            else:
                cnt = _dec(args[1]) if len(args) > 1 else 64
                if cnt <= 0:
                    raise ValueError("count must be positive")
                self.cmd_mem(_addr(args[0], self.labels), cnt)
        elif cmd in ("l", "list", "disasm"):
            addr = _addr(args[0], self.labels) if args else None
            cnt = _dec(args[1]) if len(args) > 1 else 8
            if cnt <= 0:
                raise ValueError("count must be positive")
            self.cmd_disasm(addr, cnt)
        elif cmd in ("trace",):
            n = _dec(args[0]) if args else 20
            if n <= 0:
                raise ValueError("count must be positive")
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
            self.last_error = True
            self.out(f"unknown command '{cmd}'; type 'help'")
        return True

    def _add_breakpoint(self, args: list[str]) -> None:
        """Adds (or replaces) a breakpoint from ``<addr> [if <expr>]`` arguments.

        The condition is parsed before anything is modified, so an invalid
        expression leaves the breakpoint table untouched.
        """
        addr = _addr(args[0], self.labels)
        if len(args) == 1:
            self.breakpoints.add(addr)
            self.conditions.pop(addr, None)
            self._condition_nodes.pop(addr, None)
            self.out(f"breakpoint at 0x{addr:02X}{self._sym(addr)}")
            return
        if args[1].lower() != "if":
            raise ValueError("usage: break <address|label> [if <expression>]")
        source = " ".join(args[2:]).strip()
        if not source:
            raise ValueError("missing expression after 'if'")
        node = _ConditionParser(source, self.labels).parse()
        self.breakpoints.add(addr)
        self.conditions[addr] = source
        self._condition_nodes[addr] = node
        self.out(f"breakpoint at 0x{addr:02X}{self._sym(addr)} if {source}")

    def _list_breakpoints(self) -> None:
        if not self.breakpoints:
            self.out("(no breakpoints)")
            return
        for a in sorted(self.breakpoints):
            cond = f" if {self.conditions[a]}" if a in self.conditions else ""
            self.out(f"breakpoint at 0x{a:02X}{self._sym(a)}{cond}")

    def _add_watch(self, target: str) -> None:
        clave = self._norm_watch(target)
        if not self._valid_target(clave):
            self.out(
                f"error: cannot watch '{target}' "
                f"(registers A-D/SP/PC/IR/OP, flags fZ/fC/fN/fV/fI, or @address)"
            )
            return
        self.watches[clave] = self._read(clave)
        self.out(f"watching {clave} (now 0x{self.watches[clave]:02X})")

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
  u, until <addr>    run until the PC reaches an address or label
  b, break [addr [if <expr>]]
                     set a breakpoint (address, label or L_xxxx); without
                     arguments, list them.  <expr>: A-D/SP/PC, flags
                     CF/ZF/NF/VF/IF (C is register C), @0xNN/@label (RAM),
                     literals, == != < <= > >=, && and ||, and parentheses.
                     e.g. break loop if A == 3 && @0x40 < 0x10
  d, delete <addr>   remove a breakpoint (and its condition)   clear  all
  bl, breakpoints    list the breakpoints (with their symbol and condition)
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
    except (ValueError, OSError) as e:
        print(f"Error: cannot read '{path}': {e}", file=sys.stderr)
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
        failed = False
        for cmd in commands:
            if not dbg.handle(cmd):
                break
            failed = failed or dbg.last_error
        return 1 if failed else 0

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
