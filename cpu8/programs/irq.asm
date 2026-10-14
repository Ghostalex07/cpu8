; ============================================================================
;  irq.asm - Prueba de interrupciones (Fase 7.5)
;
;  El programa principal cuenta de 0 a 9 (OUT A cada vuelta) con las
;  interrupciones habilitadas (EI).  El manejador de IRQ (en 0x10, el vector
;  que usa tb/irq_tb.v) incrementa C y regresa con RET.
;
;  Como al atender la interrupcion se baja el flag I, aunque la senal irq se
;  mantenga alta SOLO se atiende UNA interrupcion.  Al terminar el bucle se
;  imprime C (=1) para comprobar que la interrupcion ocurrio exactamente una
;  vez.
;
;  Salida esperada:  0 1 2 3 4 5 6 7 8 9 1
; ============================================================================

        LDI A, 0        ; 0x00: 10 00   contador principal
        LDI B, 1        ; 0x02: 14 01   incremento
        LDI C, 0        ; 0x04: 18 00   contador de interrupciones
        LDI D, 10       ; 0x06: 1C 0A   limite del bucle
        EI              ; 0x08: F2      habilita interrupciones

bucle:  OUT A           ; 0x09: E0
        ADD A, B        ; 0x0A: 51
        CMP A, D        ; 0x0B: A3      Z=1 cuando A llega a 10
        JNZ bucle       ; 0x0C: D1 09
        OUT C           ; 0x0E: E8      imprime cuantas interrupciones hubo
        HLT             ; 0x0F: F0

; --- Manejador de interrupcion (debe estar en IRQ_VECTOR = 0x10) ---
        INC C           ; 0x10: 02
        RET             ; 0x11: F1
