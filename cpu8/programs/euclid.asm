; ============================================================================
;  euclid.asm - Greatest common divisor (GCD) by Euclid's algorithm
;
;  Computes gcd(144, 60) with the remainder form  r = a - (a/b)*b  (uses the
;  hardware DIV and MUL instructions).  It iterates (a,b) <- (b, a mod b) until
;  b = 0; then the gcd is a.
;
;  Registers: A = a, B = b, C = temporary, D = 0 (comparison constant).
;
;  Expected output (OUT): 0C   (gcd(144,60) = 12)
; ============================================================================

        LDI A, 144              ; a
        LDI B, 60               ; b
        LDI D, 0                ; D = 0 (to compare with b)

loop:
        CMP B, D
        JZ  end                 ; b == 0 -> the gcd is a
        MOV C, A                ; C = a
        DIV C, B                ; C = a / b
        MUL C, B                ; C = (a/b) * b
        SUB A, C                ; A = a - (a/b)*b = a mod b
        MOV C, A                ; C = r
        MOV A, B                ; A = b
        MOV B, C                ; B = r
        JMP loop

end:
        OUT A                   ; gcd
        HLT
