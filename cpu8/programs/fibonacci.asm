; ============================================================================
;  fibonacci.asm - Fibonacci until the sum overflows 8 bits
;
;  Prints: 1 1 2 3 5 8 13 21 34 55 89 144 233  and stops.
;  The next term (233+144=377) no longer fits in a byte, so the addition sets
;  carry and the program ends just before showing it.
;
;  A and B hold two consecutive terms.  Before computing the new one, A is
;  copied to C so it is not lost (it will be the B of the next pass).  ADD sets
;  C=1 when the result exceeds 255: that is the stopping criterion.
; ============================================================================

        LDI A,1          ; first term
        LDI B,1          ; second term
        OUT A            ; the first two come out as they are
        OUT B

loop:   MOV C,A          ; saves the old term (the future B)
        ADD A,B          ; A = A + B   (C=1 if the 8 bits overflow)
        JC  end          ; if it overflowed, we finish without printing it
        OUT A            ; shows the new term
        MOV B,C          ; advances the window: B becomes the old A
        JMP loop

end:    HLT
