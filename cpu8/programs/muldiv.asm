; ---------------------------------------------------------------------------
;  muldiv.asm - Hardware multiplication and division (Phase 9)
;
;  MUL rd,rs -> rd = (rd*rs)[7:0];  C = 1 if the product does not fit in 8 bits.
;  DIV rd,rs -> rd = rd/rs (unsigned);  C = 1 if the divisor is 0.
;  Both update Z and N.
;
;  Expected output (OUT): 2A 90 C1 1C 21 00 C2 C3
; ---------------------------------------------------------------------------

        ; --- Simple MUL: 7 * 6 = 42 = 0x2A ---
        LDI A, 7
        LDI B, 6
        MUL A, B
        OUT A               ; -> 2A

        ; --- MUL with overflow: 20 * 20 = 400 = 0x0190 (> 0xFF) ---
        LDI A, 20
        LDI B, 20
        MUL A, B            ; A = 0x90, C = 1
        OUT A               ; -> 90
        JC  mul_big
        LDI A, 0xE1         ; should not run
        OUT A
        HLT
mul_big:
        LDI A, 0xC1
        OUT A               ; -> C1

        ; --- DIV: 200 / 7 = 28 = 0x1C ---
        LDI A, 200
        LDI B, 7
        DIV A, B
        OUT A               ; -> 1C

        ; --- DIV: 100 / 3 = 33 = 0x21 ---
        LDI A, 100
        LDI B, 3
        DIV A, B
        OUT A               ; -> 21

        ; --- DIV by zero: 9 / 0 -> A = 0, C = 1 ---
        LDI A, 9
        LDI B, 0
        DIV A, B
        OUT A               ; -> 00
        JC  div_zero
        LDI A, 0xE2         ; should not run
        OUT A
        HLT
div_zero:
        LDI A, 0xC2
        OUT A               ; -> C2

        ; --- MUL that gives 0: 0 * 7 = 0 -> Z = 1 ---
        LDI A, 0
        LDI B, 7
        MUL A, B
        JZ  mul_zero
        LDI A, 0xE3         ; should not run
        OUT A
        HLT
mul_zero:
        LDI A, 0xC3
        OUT A               ; -> C3
        HLT
