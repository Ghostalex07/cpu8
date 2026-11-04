; ============================================================================
;  timer.asm - Programmable timer demo for the iCEstick
;
;  Arms the timer with a 50 ms period and enables interrupts.  The handler at
;  0x08 increments a counter (shown on the 5 LEDs) and re-arms the timer, so
;  the LEDs count up roughly 20 times per second.  Writing 0 to port 2 (not
;  done here) would disable the timer and clear its pending interrupt.
;
;  This program never halts on purpose: it is a hardware demo, not part of the
;  halt-based program regression.
; ============================================================================

        JMP main

        .org 0x08
handler:
        LDI A, 50
        OUT 2, A
        ADDI B, 1
        EI
        RETI

        .org 0x20
main:
        LDI B, 0
        LDI A, 50
        OUT 2, A
        EI
loop:
        OUT 0, B
        JMP loop
