; ============================================================================
;  multiply.asm - Multiplication by repeated addition (6 x 7)
;
;  Computes 6*7 by adding the multiplicand A=6 to the accumulator C as many
;  times as indicated by counter B=7, and prints each partial sum:
;      6 12 18 24 30 36 42
;
;  At the start of each pass B is decremented; when B was already 0 the
;  subtraction produces a borrow (C=0) and "JNC" finishes before adding one
;  time too many.
; ============================================================================

        LDI A,6          ; multiplicand
        LDI B,7          ; multiplier -> number of passes
        LDI C,0          ; accumulator (the product)
        LDI D,1          ; constant 1 to decrement the counter

loop:   SUB B,D          ; B = B - 1   (C=1 while B>=1)
        JNC end          ; B was 0 -> we have already added everything
        ADD C,A          ; accumulates 6
        OUT C            ; shows the partial sum
        JMP loop

end:    HLT
