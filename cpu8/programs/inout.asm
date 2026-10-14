; ---------------------------------------------------------------------------
;  inout.asm - Entrada IN y salida por puerto OUT n, rd (Fase 9)
;
;  El banco de pruebas presenta en `in_data` el valor del puerto pedido:
;    puerto 0 -> 0x10, puerto 1 -> 0x11, puerto 2 -> 0x12, puerto 3 -> 0x13
;
;  Salida esperada (OUT): 10 12 AB 55
; ---------------------------------------------------------------------------

        IN  A               ; A = entrada del puerto 0 = 0x10
        OUT A               ; -> 10   (puerto 0, forma de registro)

        IN  2, B            ; B = entrada del puerto 2 = 0x12
        OUT 2, B            ; -> 12   (puerto 2, forma portada)

        LDI C, 0xAB
        OUT 1, C            ; -> AB   (puerto 1)

        LDI D, 0x55
        OUT D               ; -> 55   (puerto 0)

        HLT
