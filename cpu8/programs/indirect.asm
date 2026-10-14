; indirect.asm - Direccionamiento indirecto por registro (Fase 7.4)
;
; usa un registro como puntero para recorrer memoria:
;       ST A, [B]   ->  RAM[B] = A
;       LD A, [B]   ->  A = RAM[B]

        LDI A, 0x2A     ; valor 42
        LDI B, 0x20     ; B = puntero a 0x20
        ST A, [B]       ; RAM[0x20] = 42
        INC B           ; B = 0x21
        LDI A, 0x07     ; valor 7
        ST A, [B]       ; RAM[0x21] = 7
        LD A, [B]       ; A = RAM[0x21] = 7
        OUT A           ; imprime 7
        LDI B, 0x20     ; vuelve al inicio del "array"
        LD A, [B]       ; A = RAM[0x20] = 42
        OUT A           ; imprime 42
        HLT
