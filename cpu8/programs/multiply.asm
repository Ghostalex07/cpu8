; ============================================================================
;  multiply.asm - Multiplicacion por sumas sucesivas (6 x 7)
;
;  Calcula 6*7 sumando el multiplicando A=6 al acumulador C tantas veces como
;  indique el contador B=7, e imprime cada suma parcial:
;      6 12 18 24 30 36 42
;
;  Al comienzo de cada vuelta se decrementa B; cuando B ya era 0 la resta
;  produce borrow (C=0) y "JNC" termina antes de sumar una vez de mas.
; ============================================================================

        LDI A,6          ; multiplicando
        LDI B,7          ; multiplicador -> numero de vueltas
        LDI C,0          ; acumulador (el producto)
        LDI D,1          ; constante 1 para decrementar el contador

loop:   SUB B,D          ; B = B - 1   (C=1 mientras B>=1)
        JNC fin          ; B era 0 -> ya hemos sumado todo
        ADD C,A          ; acumula 6
        OUT C            ; muestra la suma parcial
        JMP loop

fin:    HLT
