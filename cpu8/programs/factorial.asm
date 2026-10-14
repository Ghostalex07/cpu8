; ============================================================================
;  factorial.asm - Iterative factorial (5! = 120) using the hardware MUL
;
;  A = accumulator (starts at 1), B = n.  On each pass A = A*B and B-- ; the
;  loop ends when B reaches 0 (DEC sets Z).
;
;  Expected output (OUT): 78   (5! = 120 = 0x78)
; ============================================================================

        LDI A, 1                ; accumulator = 1
        LDI B, 5                ; n = 5

loop:
        MUL A, B                ; A = A * B
        DEC B
        JNZ loop                ; while B != 0

        OUT A                   ; 120 = 0x78
        HLT
