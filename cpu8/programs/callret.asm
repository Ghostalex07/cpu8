; callret.asm - Subrutinas con CALL/RET (Fase 7.4)
;
; llama dos veces a una subrutina "suma" que hace A = A + B.
; CALL guarda la direccion de retorno en la pila; RET la recupera.

        LDI A, 3
        LDI B, 4
        CALL suma       ; A = 3 + 4 = 7
        OUT A           ; imprime 7
        LDI A, 10
        CALL suma       ; A = 10 + 4 = 14
        OUT A           ; imprime 14
        HLT

suma:   ADD A, B        ; subrutina
        RET
