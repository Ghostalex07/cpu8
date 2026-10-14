; indirect.asm - Register-indirect addressing (Phase 7.4)
;
; uses a register as a pointer to walk through memory:
;       ST A, [B]   ->  RAM[B] = A
;       LD A, [B]   ->  A = RAM[B]

        LDI A, 0x2A     ; value 42
        LDI B, 0x20     ; B = pointer to 0x20
        ST A, [B]       ; RAM[0x20] = 42
        INC B           ; B = 0x21
        LDI A, 0x07     ; value 7
        ST A, [B]       ; RAM[0x21] = 7
        LD A, [B]       ; A = RAM[0x21] = 7
        OUT A           ; prints 7
        LDI B, 0x20     ; back to the start of the "array"
        LD A, [B]       ; A = RAM[0x20] = 42
        OUT A           ; prints 42
        HLT
