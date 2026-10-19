; ============================================================================
;  logic.asm - Exercises the bitwise and shift instructions
;
;  OR / XOR write to the register file and set Z/N from the result (C and V
;  are cleared).  SHL / SHR move one bit and report the bit that fell off in
;  C.  ROL / ROR rotate *through* the carry flag, so the demo pins C first
;  with TEST (clears C) or with an overflowing ADD (sets C) and then shows
;  the round trip 0x40 -> 0x81 -> 0x40.
;
;  The expected outputs live in programs/logic.ref.
; ============================================================================

        ; --- OR / XOR on A ----------------------------------------------
        LDI A, 0xF0
        LDI B, 0x0F
        OR  A, B          ; A = 0xFF
        OUT A             ; FF

        LDI B, 0xFF
        XOR A, B          ; A = 0x00 (Z=1)
        OUT A             ; 00

        LDI A, 0x80
        LDI B, 0x01
        OR  A, B          ; A = 0x81 (N=1)
        OUT A             ; 81

        ; --- the same on the other registers -----------------------------
        LDI C, 0xA5
        LDI D, 0x0F
        OR  C, D          ; C = 0xAF
        OUT C             ; AF

        LDI D, 0xF0
        XOR C, D          ; C = 0x5F
        OUT C             ; 5F

        ; --- shifts: the displaced bit lands in C ------------------------
        LDI A, 0x81
        SHL A             ; A = 0x02, C = 1
        OUT A             ; 02

        LDI A, 0x40
        SHL A             ; A = 0x80, C = 0
        OUT A             ; 80

        LDI A, 0x81
        SHR A             ; A = 0x40, C = 1
        OUT A             ; 40

        LDI A, 0x01
        SHR A             ; A = 0x00, C = 1 (Z=1)
        OUT A             ; 00

        ; --- ROL / ROR rotate through C, so C is known first -------------
        LDI A, 0x80
        TEST A, A         ; C = 0 (flags only, A keeps 0x80)
        ROL A             ; A <- {A[6:0],C} = 0x00 ; C <- A[7] = 1
        OUT A             ; 00
        ROL A             ; A <- {0x00,1} = 0x01 ; C <- 0
        OUT A             ; 01

        LDI A, 0x01
        TEST A, A         ; C = 0
        ROR A             ; A <- {C,A[7:1]} = 0x00 ; C <- A[0] = 1
        OUT A             ; 00
        ROR A             ; A <- {1,0x00} = 0x80 ; C <- 0
        OUT A             ; 80

        ; --- the round trip 0x40 -> 0x81 -> 0x40 -------------------------
        LDI A, 0xFF
        LDI B, 0x01
        ADD A, B          ; A = 0x00 with C = 1 (overflow sets the carry)
        LDI A, 0x40       ; A = 0x40, C is not touched
        ROL A             ; A <- {0x40,1} = 0x81 ; C <- 0
        OUT A             ; 81
        ROR A             ; A <- {0,0x40} = 0x40 ; C <- 1
        OUT A             ; 40

        HLT
