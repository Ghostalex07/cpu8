; ============================================================================
;  euclid.asm - Maximo comun divisor (MCD) por el algoritmo de Euclides
;
;  Calcula mcd(144, 60) con la forma del resto  r = a - (a/b)*b  (usa las
;  instrucciones DIV y MUL de hardware).  Se itera (a,b) <- (b, a mod b) hasta
;  que b = 0; entonces el mcd es a.
;
;  Registros: A = a, B = b, C = temporal, D = 0 (constante de comparacion).
;
;  Salida esperada (OUT): 0C   (mcd(144,60) = 12)
; ============================================================================

        LDI A, 144              ; a
        LDI B, 60               ; b
        LDI D, 0                ; D = 0 (para comparar con b)

bucle:
        CMP B, D
        JZ  fin                 ; b == 0 -> el mcd es a
        MOV C, A                ; C = a
        DIV C, B                ; C = a / b
        MUL C, B                ; C = (a/b) * b
        SUB A, C                ; A = a - (a/b)*b = a mod b
        MOV C, A                ; C = r
        MOV A, B                ; A = b
        MOV B, C                ; B = r
        JMP bucle

fin:
        OUT A                   ; mcd
        HLT
