; ============================================================================
;  primes.asm - Imprime los primos menores que 32 (division por tentativa)
;
;  Para cada n de 2 a 31 se comprueba si algun d (2..n-1) lo divide.  El resto
;  se calcula como  n - (n/d)*d  usando las instrucciones DIV y MUL de hardware.
;
;  Celdas RAM: [NVAL], [DVAL], [LIM]  (0xF8..0xFA), libres porque este programa
;  no usa la pila (SP arranca en 0xF0 y crece hacia abajo).
;
;  Salida esperada (OUT): 02 03 05 07 0B 0D 11 13 17 1D 1F
; ============================================================================

        .equ NVAL, 0xF8
        .equ DVAL, 0xF9
        .equ LIM,  0xFA

inicio:
        LDI A, 2
        ST  A, [NVAL]           ; n = 2
        LDI A, 32
        ST  A, [LIM]            ; limite = 32

bucle_n:
        LD  A, [NVAL]
        LD  B, [LIM]
        CMP A, B
        JC  fin                 ; n >= 32 -> fin

        LDI A, 2
        ST  A, [DVAL]           ; d = 2

bucle_d:
        LD  A, [DVAL]
        LD  B, [NVAL]
        CMP A, B
        JC  es_primo            ; d >= n -> no hubo divisor -> primo

        LD  A, [NVAL]           ; A = n
        LD  B, [DVAL]           ; B = d
        DIV A, B                ; A = n / d
        MUL A, B                ; A = (n/d) * d
        LD  B, [NVAL]           ; B = n
        CMP A, B
        JZ  no_primo            ; (n/d)*d == n -> d divide a n

        LD  A, [DVAL]           ; d++
        INC A
        ST  A, [DVAL]
        JMP bucle_d

es_primo:
        LD  A, [NVAL]
        OUT A                   ; n es primo
no_primo:
        LD  A, [NVAL]           ; n++
        INC A
        ST  A, [NVAL]
        JMP bucle_n

fin:
        HLT
