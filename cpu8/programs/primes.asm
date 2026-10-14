; ============================================================================
;  primes.asm - Prints the primes below 32 (trial division)
;
;  For each n from 2 to 31 it checks whether some d (2..n-1) divides it.  The
;  remainder is computed as  n - (n/d)*d  using the hardware DIV and MUL
;  instructions.
;
;  RAM cells: [NVAL], [DVAL], [LIM]  (0xF8..0xFA), free because this program
;  does not use the stack (SP starts at 0xF0 and grows downwards).
;
;  Expected output (OUT): 02 03 05 07 0B 0D 11 13 17 1D 1F
; ============================================================================

        .equ NVAL, 0xF8
        .equ DVAL, 0xF9
        .equ LIM,  0xFA

start:
        LDI A, 2
        ST  A, [NVAL]           ; n = 2
        LDI A, 32
        ST  A, [LIM]            ; limit = 32

loop_n:
        LD  A, [NVAL]
        LD  B, [LIM]
        CMP A, B
        JC  end                 ; n >= 32 -> end

        LDI A, 2
        ST  A, [DVAL]           ; d = 2

loop_d:
        LD  A, [DVAL]
        LD  B, [NVAL]
        CMP A, B
        JC  is_prime            ; d >= n -> no divisor found -> prime

        LD  A, [NVAL]           ; A = n
        LD  B, [DVAL]           ; B = d
        DIV A, B                ; A = n / d
        MUL A, B                ; A = (n/d) * d
        LD  B, [NVAL]           ; B = n
        CMP A, B
        JZ  not_prime           ; (n/d)*d == n -> d divides n

        LD  A, [DVAL]           ; d++
        INC A
        ST  A, [DVAL]
        JMP loop_d

is_prime:
        LD  A, [NVAL]
        OUT A                   ; n is prime
not_prime:
        LD  A, [NVAL]           ; n++
        INC A
        ST  A, [NVAL]
        JMP loop_n

end:
        HLT
