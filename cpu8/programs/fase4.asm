; ===========================================================================
;  fase4.asm - Programa de prueba de la Fase 4 (escrito a mano)
;
;  Este fichero es la fuente real del programa: el ensamblador (Fase 5,
;  asm/assembler.py) lo traduce a fase4.hex, que es lo que carga la CPU.
;
;  Qué hace: guarda 7 en memoria, lo vuelve a leer y luego hace una cuenta
;  atrás de 7 a 1 sacando cada valor por el puerto OUT. Termina con HLT.
;
;  Codificación (byte alto = opcode<<4 | rd<<2 | rs):
;    0x00 : LDI A, 7      -> 10 07
;    0x02 : ST  A, [0x20] -> 40 20   ; M[0x20] = 7
;    0x04 : LD  A, [0x20] -> 30 20   ; A = M[0x20] = 7
;    0x06 : LDI B, 1      -> 14 01
;    0x08 : OUT A         -> E0      ; imprime A (bucle)
;    0x09 : SUB A, B      -> 61      ; A = A - 1
;    0x0A : JNZ 0x08      -> D1 08   ; repite mientras A != 0
;    0x0C : HLT           -> F0
;
;  Salida esperada: 7 6 5 4 3 2 1
; ===========================================================================

        LDI A, 7
        ST  A, [0x20]
        LD  A, [0x20]
        LDI B, 1
loop:   OUT A
        SUB A, B
        JNZ loop
        HLT
