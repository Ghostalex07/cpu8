; ============================================================================
;  countdown.asm - Cuenta atras de 9 a 0
;
;  Imprime por el puerto OUT los numeros 9,8,...,1,0.
;
;  Estrategia: A empieza en 9.  En cada vuelta se imprime A y se le resta 1.
;  La resta A - B (con B=1) deja C=1 mientras A>=1 (no hay borrow con el
;  convenio invertido del ISA), asi que "JC loop" repite mientras queden
;  numeros.  Al intentar restar cuando A ya es 0 aparece el borrow (C=0) y el
;  bucle termina.
; ============================================================================

        LDI A,9          ; primer numero a mostrar
        LDI B,1          ; constante 1 para ir restando

loop:   OUT A            ; saca por el puerto el valor actual
        SUB A,B          ; A = A - 1   (C=1 mientras A>=1)
        JC  loop         ; si no hubo borrow, otra vuelta
        HLT              ; A llego a 0: fin
