; ============================================================================
;  factorial.asm - Factorial iterativo (5! = 120) usando la MUL de hardware
;
;  A = acumulador (empieza en 1), B = n.  En cada vuelta A = A*B y B-- ; el
;  bucle termina cuando B llega a 0 (DEC pone Z).
;
;  Salida esperada (OUT): 78   (5! = 120 = 0x78)
; ============================================================================

        LDI A, 1                ; acumulador = 1
        LDI B, 5                ; n = 5

bucle:
        MUL A, B                ; A = A * B
        DEC B
        JNZ bucle               ; mientras B != 0

        OUT A                   ; 120 = 0x78
        HLT
