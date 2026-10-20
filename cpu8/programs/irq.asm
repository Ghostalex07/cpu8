; ============================================================================
;  irq.asm - Interrupt test (Phase 7.5; RETI added in Phase 12e)
;
;  The main program counts with a carry chain: C is set to 1 with `CMP A, A`
;  before enabling interrupts, and each iteration does `ADC A, B` (A += B + C).
;  The first iteration adds 2 (0 -> 2) because the carry survives the
;  interrupt; later iterations add 1.
;
;  The handler (at 0x10, the vector used by tb/irq_tb.v) increments C and
;  clobbers the flags.  It returns with RETI, which restores C, Z, N and V
;  from the values saved when the interrupt was taken.  I stays cleared, so
;  with a level-high IRQ only ONE interrupt is handled.
;
;  Expected output:  1 0 2 3 4 5 6 7 8 9 10
;  (1 = interrupt counter, printed by the handler, then the A sequence)
; ============================================================================

        LDI A, 0        ; main counter
        LDI B, 1        ; increment
        MOV C, A        ; interrupt counter = 0
        LDI D, 10       ; loop count
        CMP A, A        ; C=1 (no borrow), Z=1
        EI              ; enables interrupts

loop:   OUT A
        ADC A, B        ; A <- A + B + C
        DEC D
        JNZ loop

        HLT

; --- Interrupt handler (must be at IRQ_VECTOR = 0x10) ---
        ADD C, B        ; C++ (clobbers the flags)
        OUT C           ; prints the interrupt counter
        RETI            ; return and restore C, Z, N, V
