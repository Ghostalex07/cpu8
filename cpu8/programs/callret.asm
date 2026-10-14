; callret.asm - Subroutines with CALL/RET (Phase 7.4)
;
; calls a "sum" subroutine twice that performs A = A + B.
; CALL saves the return address on the stack; RET recovers it.

        LDI A, 3
        LDI B, 4
        CALL sum        ; A = 3 + 4 = 7
        OUT A           ; prints 7
        LDI A, 10
        CALL sum        ; A = 10 + 4 = 14
        OUT A           ; prints 14
        HLT

sum:    ADD A, B        ; subroutine
        RET
