; stack.asm - Prueba de PUSH/POP/RET (Fase 7.3)
; La pila arranca con SP = 0xF0 y crece hacia abajo:
;   PUSH A  ->  mem[SP] = A ; SP = SP - 1
;   POP  C  ->  SP = SP + 1 ; C = mem[SP]
;   RET     ->  SP = SP + 1 ; PC = mem[SP]
; Salida esperada: 2 1 1

        LDI A, 1
        LDI B, 2
        PUSH A          ; mem[F0] = 1, SP = EF
        PUSH B          ; mem[EF] = 2, SP = EE
        POP C           ; SP = EF, C = 2  (el ultimo en entrar)
        POP D           ; SP = F0, D = 1  (el primero en entrar)
        OUT C           ; imprime 2
        OUT D           ; imprime 1

        ; RET: empujamos una direccion de retorno y saltamos a ella.
        LDI A, destino
        PUSH A          ; mem[F0] = dir(destino), SP = EF
        RET             ; SP = F0, PC = dir(destino)
        LDI A, 0xEE     ; no debe ejecutarse
        OUT A
destino:
        OUT D           ; imprime 1 (prueba de que el RET funciono)
        HLT
