; ============================================================================
;  irq.asm - Interrupt test (Phase 7.5)
;
;  The main program counts from 0 to 9 (OUT A each pass) with interrupts
;  enabled (EI).  The IRQ handler (at 0x10, the vector used by tb/irq_tb.v)
;  increments C and returns with RET.
;
;  Since handling the interrupt clears flag I, even if the irq signal stays
;  high only ONE interrupt is handled.  When the loop ends C (=1) is printed to
;  check that the interrupt happened exactly once.
;
;  Expected output:  0 1 2 3 4 5 6 7 8 9 1
; ============================================================================

        LDI A, 0        ; 0x00: 10 00   main counter
        LDI B, 1        ; 0x02: 14 01   increment
        LDI C, 0        ; 0x04: 18 00   interrupt counter
        LDI D, 10       ; 0x06: 1C 0A   loop limit
        EI              ; 0x08: F2      enables interrupts

loop:   OUT A           ; 0x09: E0
        ADD A, B        ; 0x0A: 51
        CMP A, D        ; 0x0B: A3      Z=1 when A reaches 10
        JNZ loop        ; 0x0C: D1 09
        OUT C           ; 0x0E: E8      prints how many interrupts there were
        HLT             ; 0x0F: F0

; --- Interrupt handler (must be at IRQ_VECTOR = 0x10) ---
        INC C           ; 0x10: 02
        RET             ; 0x11: F1
