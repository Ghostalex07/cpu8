; incdec.asm - Prueba de INC y DEC (Fase 7.2)
;
; INC/DEC actualizan Z y N, pero NO deben tocar el flag C.
;
; Primera parte: cuenta 1..5 con INC (comprobando Z via CMP) y luego un DEC.
; Segunda parte: forzamos C=0 con una resta que produce borrow y hacemos
;                INC/DEC; si tocaran C, JC saltaria a la rama de error.

        LDI A,0
        LDI B,5
loop:   INC A          ; A = A + 1
        OUT A          ; imprime 1,2,3,4,5
        CMP A,B        ; Z=1 cuando A==5
        JNZ loop
        DEC A          ; A = 4
        OUT A          ; imprime 4

        ; --- C no debe cambiar con INC/DEC ---
        LDI A,0
        LDI B,1
        SUB A,B        ; A = 0-1 = FF ; C = 0 (hubo borrow)
        INC A          ; A = 00 ; C debe seguir 0
        JC  error
        DEC B          ; B = 00 ; C debe seguir 0
        JC  error
        HLT

error:  OUT A          ; solo se imprime si algo fallo
        HLT
