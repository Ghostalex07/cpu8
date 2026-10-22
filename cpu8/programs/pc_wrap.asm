; ============================================================================
;  pc_wrap.asm - Program-counter wrap-around test
;
;  0x00 jumps to the real start at 0x10.  On the first pass A is 0, so the
;  program jumps to 0xFE, where a 2-byte LDI lives: its operand is fetched from
;  0xFF and PC then wraps 0xFF -> 0x00.  The second pass through the start sees
;  A = 0x2A, prints it and halts.
;
;  This exercises the increment of PC during the operand fetch of a 2-byte
;  instruction placed at the last address of the 256-byte memory.
;
;  Expected output: 2A
; ============================================================================

        .nostack         ; no PUSH/POP/CALL/RET/IRQ in this program
        JMP start
        .org 0x10

start:  CMPI A, 0        ; first pass: A = 0 from reset
        JZ first
        OUT A
        HLT

first:  JMP 0xFE         ; execute the 2-byte instruction at the top of RAM

        .org 0xFE
        LDI A, 0x2A      ; operand at 0xFF; PC wraps to 0x00 afterwards
