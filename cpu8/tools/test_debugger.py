#!/usr/bin/env python3
"""Tests for the interactive debugger ``tools/debugger.py``.

They drive the :class:`debugger.Debugger` programmatically (no stdin): they
check the execution primitives, the cycle accounting that models ``control.v``,
the breakpoints/watchpoints and the command parser.

Run with ``make pytools`` or ``python3 -m pytest tools/test_debugger.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "asm"))

import assembler  # noqa: E402
import debugger  # noqa: E402

PROG_DIR = ROOT / "programs"

# Fixture program (addresses in the comment):
#   0: 10 03  LDI A, 0x03   (2 bytes, 3 cycles)
#   2: 14 01  LDI B, 0x01   (2 bytes, 3 cycles)
#   4: E0     OUT A         (1 byte,  2 cycles)
#   5: 61     SUB A, B      (1 byte,  2 cycles)
#   6: D1 04  JNZ 0x04      (2 bytes, 3 cycles)
#   8: F0     HLT
COUNT = """\
    LDI A, 0x03
    LDI B, 0x01
loop:
    OUT A
    SUB A, B
    JNZ loop
    HLT
"""


def build(source: str, **kw):
    mem, labels, _ = assembler.ensamblar(source)
    logs: list[str] = []
    return debugger.Debugger(mem, labels, out=logs.append, **kw), logs


# ---- loading ---------------------------------------------------------------
def test_load_asm_has_labels_and_hex_does_not():
    mem, labels = debugger.load_program(PROG_DIR / "countdown.asm")
    assert len(mem) == 9
    assert labels["loop"] == 0x04

    mem_hex, labels_hex = debugger.load_program(PROG_DIR / "countdown.hex")
    assert mem_hex == mem
    assert labels_hex == {}


# ---- execution and cycles --------------------------------------------------
def test_step_advances_and_counts_cycles():
    dbg, _ = build(COUNT)
    dbg.step()  # LDI A (2 bytes -> 3 cycles)
    assert (dbg.iss.PC, dbg.cycles, dbg.retired) == (2, 3, 1)
    dbg.step()  # LDI B (2 bytes -> 3 cycles)
    assert (dbg.iss.PC, dbg.cycles, dbg.retired) == (4, 6, 2)
    dbg.step()  # OUT A (1 byte -> 2 cycles)
    assert (dbg.iss.PC, dbg.cycles, dbg.retired) == (5, 8, 3)
    assert dbg.iss.outs == [(3, 0)]


def test_in_waits_one_extra_cycle():
    dbg, _ = build("IN A\nIN 2, B\nHLT\n")
    dbg.step()  # IN A: 1 byte + S_IN wait state = 3 cycles
    assert (dbg.iss.PC, dbg.cycles) == (1, 3)
    dbg.step()  # IN 2,B: 2 bytes + S_IN wait state = 4 cycles
    assert (dbg.iss.PC, dbg.cycles) == (3, 7)


def test_hlt_halts_and_warns_on_further_steps():
    dbg, logs = build(COUNT)
    dbg.run()
    assert dbg.iss.halted
    assert dbg.iss.outs == [(3, 0), (2, 0), (1, 0)]
    dbg.step()
    assert any("halted" in line for line in logs)


def test_run_cycle_total_matches_instruction_lengths():
    dbg, _ = build(COUNT)
    dbg.run()
    # LDI,LDI (2B each -> 3) = 6; the loop body OUT,SUB (1B -> 2) + JNZ (2B -> 3)
    # runs 3 times = 3 * (2 + 2 + 3) = 21; HLT (1B -> 2).  Total = 6 + 21 + 2 = 29.
    assert dbg.cycles == 29
    assert dbg.retired == 12
    assert dbg.irqs == 0


# ---- breakpoints -----------------------------------------------------------
def test_breakpoint_stops_run_before_executing():
    dbg, _ = build(COUNT)
    dbg.breakpoints.add(0x04)
    dbg.run()
    assert not dbg.iss.halted
    assert dbg.hit_break == 0x04
    assert dbg.iss.PC == 0x04


def test_clear_removes_breakpoints():
    dbg, _ = build(COUNT)
    dbg.handle("break 0x04")
    dbg.handle("break loop")
    assert dbg.breakpoints == {0x04}
    dbg.handle("clear")
    assert dbg.breakpoints == set()


def test_until_reaches_a_label():
    dbg, logs = build(COUNT)
    dbg.handle("until loop")  # LDI A, LDI B -> lands on the loop head
    assert dbg.iss.PC == 0x04
    assert dbg.retired == 2
    assert any("(reached 0x04 (loop)" in line for line in logs)


def test_until_always_steps_at_least_once():
    dbg, logs = build(COUNT)
    dbg.step(2)  # at the loop head, A = 3
    dbg.handle("until loop")  # OUT, SUB, JNZ -> back on the loop head
    assert dbg.iss.PC == 0x04
    assert dbg.iss.regs[0] == 2  # one pass of the loop ran
    assert any("3 instructions" in line for line in logs)


def test_until_stops_on_a_breakpoint_before_the_target():
    dbg, logs = build(COUNT)
    dbg.breakpoints.add(0x05)
    dbg.handle("until 0x08")  # the HLT, past the breakpoint
    assert not dbg.iss.halted
    assert dbg.hit_break == 0x05
    assert dbg.iss.PC == 0x05


def test_until_halts_when_the_target_is_never_reached():
    dbg, logs = build(COUNT)
    dbg.handle("until 0x40")  # no such address: runs down to the HLT
    assert dbg.iss.halted
    assert any("(halted after" in line for line in logs)


def test_until_without_argument_prints_the_usage():
    dbg, logs = build(COUNT)
    dbg.handle("until")
    assert any("usage: until <address|label>" in line for line in logs)


def test_simbolos_junto_a_las_direcciones():
    dbg, logs = build(COUNT)
    dbg.handle("break loop")
    assert any("0x04 (loop)" in line for line in logs)
    dbg.handle("bl")
    assert any("0x04 (loop)" in line for line in logs)
    dbg.run()
    assert dbg.hit_break == 0x04
    assert any("(loop)" in line for line in logs)


# ---- conditional breakpoints -----------------------------------------------
def test_conditional_breakpoint_stops_when_the_condition_is_true():
    dbg, logs = build(COUNT)
    dbg.handle("break loop if A == 3")
    assert dbg.breakpoints == {0x04}
    assert dbg.conditions == {0x04: "A == 3"}
    dbg.run()
    assert not dbg.iss.halted
    assert dbg.hit_break == 0x04
    assert dbg.iss.regs[0] == 3
    assert any("0x04 (loop) if A == 3" in line for line in logs)


def test_conditional_breakpoint_false_runs_to_hlt():
    dbg, logs = build(COUNT)
    dbg.handle("break loop if A == 0")  # A is 3, 2, 1 at the loop head
    dbg.run()
    assert dbg.iss.halted
    assert dbg.hit_break is None
    assert any("(halted after" in line for line in logs)


def test_conditional_breakpoint_false_continues_to_the_next_breakpoint():
    dbg, _ = build(COUNT)
    dbg.handle("break loop if A == 0")
    dbg.handle("break 0x08")  # the HLT
    dbg.run()
    assert not dbg.iss.halted
    assert dbg.hit_break == 0x08
    assert dbg.iss.PC == 0x08


def test_until_stops_on_a_true_conditional_breakpoint():
    dbg, _ = build(COUNT)
    dbg.handle("break 0x05 if A == 3")  # first pass: A = 3
    dbg.handle("until 0x08")
    assert dbg.hit_break == 0x05
    assert dbg.iss.PC == 0x05


def test_until_continues_past_a_false_conditional_breakpoint():
    dbg, _ = build(COUNT)
    dbg.handle("break 0x05 if A == 0")  # A is 3, 2, 1 at 0x05
    dbg.handle("until 0x08")
    assert dbg.hit_break is None
    assert dbg.iss.PC == 0x08


def test_next_steps_over_a_call_with_a_false_conditional_breakpoint():
    src = "LDI A, 1\nCALL sub\nOUT A\nHLT\nsub: ADD A, A\nRET\n"
    dbg, _ = build(src)
    dbg.handle("break sub if A == 9")
    dbg.step()  # LDI
    dbg.next()  # the condition is false: the CALL runs to its RET
    assert dbg.iss.PC == 4
    assert dbg.iss.regs[0] == 2


def test_condition_logical_and_has_higher_precedence_than_or():
    dbg, _ = build(COUNT)
    # The && binds first: true || (false && false) -> true.
    dbg.handle("break loop if A == 3 || B == 9 && C == 9")
    dbg.run()
    assert dbg.hit_break == 0x04


@pytest.mark.parametrize(
    "expr",
    ["A ==", "BOGUS == 1", "A == 1 &&", "@0x100 == 0", "A < B < C", "A = 1"],
)
def test_invalid_conditions_are_rejected(expr):
    dbg, logs = build(COUNT)
    dbg.handle(f"break loop if {expr}")
    assert dbg.breakpoints == set()
    assert dbg.conditions == {}
    assert dbg.last_error
    assert any(line.startswith("error:") for line in logs)


def test_invalid_condition_keeps_the_existing_breakpoint():
    dbg, _ = build(COUNT)
    dbg.handle("break loop if A == 3")
    dbg.handle("break loop if A ==")  # rejected: the old condition survives
    assert dbg.breakpoints == {0x04}
    assert dbg.conditions == {0x04: "A == 3"}


def test_delete_removes_the_condition_too():
    dbg, _ = build(COUNT)
    dbg.handle("break loop if A == 99")
    assert dbg.conditions == {0x04: "A == 99"}
    dbg.handle("delete loop")
    assert dbg.breakpoints == set()
    assert dbg.conditions == {}
    dbg.handle("break loop")  # unconditional again, no stale condition
    assert dbg.conditions == {}
    dbg.run()
    assert dbg.hit_break == 0x04


def test_break_without_arguments_lists_the_condition():
    dbg, logs = build(COUNT)
    dbg.handle("break loop if A == 3")
    logs.clear()
    dbg.handle("break")
    assert any("0x04 (loop) if A == 3" in line for line in logs)


@pytest.mark.parametrize(
    "expr",
    [
        "A == 0",
        "ZF == 1",
        "CF == 1",  # carry is CF; C is the register below
        "C == 0",
        "SP == 0xF0",
        "PC == 0x05",  # `here` in this fixture program
        "@0x40 == 0x2A",  # RAM read when the breakpoint is reached
    ],
)
def test_condition_reads_the_current_register_flag_and_memory(expr):
    source = """\
        LDI A, 0x2A
        ST A, [0x40]
        SUB A, A
    here:
        HLT
    """
    dbg, _ = build(source)
    dbg.handle(f"break here if {expr}")
    assert dbg.conditions[dbg.labels["here"]] == expr
    assert dbg.iss.mem[0x40] == 0  # still zero when the breakpoint is set
    dbg.run()
    assert not dbg.iss.halted
    assert dbg.hit_break == dbg.labels["here"]


def test_state_y_trace_muestran_el_simbolo_de_pc():
    dbg, logs = build(COUNT)
    dbg.step(2)  # PC = 0x04 (loop)
    assert "PC=0x04 (loop)" in dbg.state()
    dbg.step()  # executes OUT A at `loop` -> trace row PC=04
    dbg.handle("trace")
    assert any("PC=04 (loop)" in line for line in logs)


# ---- watchpoints -----------------------------------------------------------
def test_watch_reports_register_change():
    dbg, logs = build(COUNT)
    dbg.handle("watch A")
    dbg.step()  # LDI A, 3
    dbg.step()  # LDI B, 1
    dbg.step()  # OUT A
    dbg.step()  # SUB A, B -> A changes 3 -> 2
    assert any("watch: A 03 -> 02" in line for line in logs)


def test_watch_memory_cell():
    dbg, _ = build("LDI A, 0x2A\nST A, [0x40]\nHLT\n")
    dbg.handle("watch @0x40")
    dbg.run()
    assert dbg.watches["@0x40"] == 0x2A


def test_unwatch_and_unknown_target():
    dbg, logs = build(COUNT)
    dbg.handle("watch PC")
    assert "PC" in dbg.watches
    dbg.handle("unwatch PC")
    assert "PC" not in dbg.watches
    dbg.handle("watch bogus")
    assert any("cannot watch" in line for line in logs)


def test_watch_and_unwatch_are_case_insensitive():
    dbg, _ = build(COUNT)
    dbg.handle("watch a")
    dbg.handle("watch fz")
    assert dbg.watches == {"A": 0, "fZ": 0}
    dbg.handle("unwatch a")
    assert set(dbg.watches) == {"fZ"}


def test_disasm_and_delete_validate_their_arguments():
    dbg, logs = build(COUNT)
    dbg.handle("disasm 0x100")
    dbg.handle("delete")
    assert dbg.last_error
    assert any("outside the 256-byte memory" in line for line in logs)
    assert any("usage: delete" in line for line in logs)


# ---- next steps over CALL --------------------------------------------------
def test_next_steps_over_call():
    src = "LDI A, 1\nCALL sub\nOUT A\nHLT\nsub: ADD A, A\nRET\n"
    dbg, _ = build(src)
    dbg.step()  # LDI
    assert dbg.iss.PC == 2
    dbg.next()  # steps over CALL, runs the subroutine
    assert dbg.iss.PC == 4
    assert dbg.iss.regs[0] == 2  # 1 + 1 inside `sub`


def test_next_steps_over_nested_calls():
    src = "LDI A, 1\nCALL one\nOUT A\nHLT\none: CALL two\nRET\ntwo: ADD A, A\nRET\n"
    dbg, _ = build(src)
    dbg.step()  # LDI
    dbg.next()
    assert dbg.iss.PC == 4
    assert dbg.iss.regs[0] == 2


def test_next_stops_at_a_breakpoint_inside_the_call_and_reports_it():
    src = "LDI A, 1\nCALL sub\nOUT A\nHLT\nsub: ADD A, A\nRET\n"
    dbg, _ = build(src)
    dbg.step()  # LDI
    dbg.handle("break sub")
    dbg.next()
    assert dbg.iss.PC == 6
    assert dbg.hit_break == 6
    assert dbg.iss.regs[0] == 1  # the CALL was executed, `sub` was not


# ---- interrupts ------------------------------------------------------------
def test_irq_counts_cycles_and_interrupts():
    dbg, _ = build("EI\nHLT\n", irq_at=1)
    dbg.step()  # EI
    assert dbg.iss.fi == 1
    dbg.step()  # services the interrupt (no instruction retired)
    assert dbg.irqs == 1
    assert dbg.retired == 1
    assert dbg.cycles == 4  # 2 (EI is 1 byte) + 2 (FETCH that detects irq + S_IRQ)
    assert dbg.iss.PC == 0x08  # jumped to the vector


# ---- command parser / formatting ------------------------------------------
def test_unknown_command_is_harmless():
    dbg, logs = build(COUNT)
    assert dbg.handle("frobnicate") is True
    assert any("unknown command" in line for line in logs)


def test_quit_returns_false():
    dbg, _ = build(COUNT)
    assert dbg.handle("quit") is False
    assert dbg.handle("q") is False


def test_reset_clears_counters():
    dbg, _ = build(COUNT)
    dbg.step()
    dbg.run()
    dbg.handle("reset")
    assert (dbg.cycles, dbg.retired, dbg.irqs) == (0, 0, 0)
    assert dbg.iss.PC == 0 and not dbg.iss.halted


def test_disasm_and_mem_produce_output():
    dbg, logs = build(COUNT)
    dbg.handle("disasm 0 3")
    assert any("LDI A, 0x03" in line for line in logs)
    logs.clear()
    dbg.handle("mem 0 4")
    assert any(line.startswith("00: 10 03 14 01") for line in logs)


def test_to_int_accepts_several_forms():
    labels = {"loop": 0x04}
    assert debugger._to_int("loop", labels) == 4
    assert debugger._to_int("0x10", labels) == 0x10
    assert debugger._to_int("$1F", labels) == 0x1F
    assert debugger._to_int("L_0ABC", labels) == 0x0ABC
    assert debugger._to_int("12", labels) == 12


def test_invalid_argument_reports_error_without_crashing():
    dbg, logs = build(COUNT)
    assert dbg.handle("break") is True
    assert any("usage" in line for line in logs)
    dbg.handle("delete 0x04")  # removing a non-existent breakpoint is fine
    assert dbg.breakpoints == set()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# ---- address parsing and command failures ----------------------------------
def test_until_accepts_a_decimal_address_with_a_leading_zero():
    dbg, logs = build(COUNT)
    dbg.handle("until 08")  # the HLT is at address 8
    assert any("reached 0x08" in line for line in logs)


def test_break_rejects_an_address_outside_the_memory():
    dbg, logs = build(COUNT)
    dbg.handle("break 300")
    assert dbg.breakpoints == set()
    assert any("outside the 256-byte memory" in line for line in logs)


def test_negative_memory_count_is_rejected():
    dbg, logs = build(COUNT)
    dbg.handle("mem 0 -4")
    assert any("count must be positive" in line for line in logs)


def test_exec_commands_return_nonzero_when_one_fails(tmp_path, capsys):
    source = tmp_path / "p.asm"
    source.write_text(COUNT)
    rc = debugger.main([str(source), "-e", "frobnicate"])
    assert rc == 1


def test_exec_commands_return_zero_when_all_succeed(tmp_path):
    source = tmp_path / "p.asm"
    source.write_text(COUNT)
    assert debugger.main([str(source), "-e", "regs; step 2"]) == 0


def test_watchpoints_fire_on_the_interrupt_cycle():
    # take_irq pushes the return PC (SP 0xF0 -> 0xEF) in its own cycle; the SP
    # watch must report that change instead of skipping to the next instruction.
    source = """\
        LDI A, 0
        EI
    loop:
        JMP loop
    """
    dbg, logs = build(source, irq_at=0, irq_vector=0x03)
    dbg.handle("watch SP")
    dbg.handle("step 3")  # LDI, EI, then the interrupt cycle
    assert any(line.startswith("watch: SP F0 -> EF") for line in logs)


def test_mem_accepts_a_count_with_a_leading_zero() -> None:
    dbg, logs = build(COUNT)
    dbg.handle("mem 0 08")
    assert not dbg.last_error
    assert any(line.startswith("00:") for line in logs)


def test_invalid_hex_file_is_reported_without_a_traceback(tmp_path, capsys) -> None:
    bad = tmp_path / "bad.hex"
    bad.write_text("ZZ\n")
    assert debugger.main([str(bad), "-e", "step"]) == 1
    assert "cannot read" in capsys.readouterr().err
