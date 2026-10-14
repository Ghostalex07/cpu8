; ============================================================================
;  fibonacci.asm - Fibonacci hasta que la suma desborde los 8 bits
;
;  Imprime: 1 1 2 3 5 8 13 21 34 55 89 144 233  y para.
;  El siguiente termino (233+144=377) ya no cabe en un byte, asi que la suma
;  marca carry y el programa termina justo antes de mostrarlo.
;
;  A y B guardan dos terminos consecutivos.  Antes de calcular el nuevo se
;  copia A en C para no perderlo (sera el B de la siguiente vuelta).  ADD pone
;  C=1 cuando el resultado supera 255: ese es el criterio de parada.
; ============================================================================

        LDI A,1          ; primer termino
        LDI B,1          ; segundo termino
        OUT A            ; los dos primeros salen tal cual
        OUT B

loop:   MOV C,A          ; guarda el termino antiguo (futuro B)
        ADD A,B          ; A = A + B   (C=1 si desbordan los 8 bits)
        JC  fin          ; si desbordo, terminamos sin imprimirlo
        OUT A            ; muestra el nuevo termino
        MOV B,C          ; avanza la ventana: B pasa a ser el antiguo A
        JMP loop

fin:    HLT
