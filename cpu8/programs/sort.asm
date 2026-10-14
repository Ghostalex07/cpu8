; ============================================================================
;  sort.asm - Ordena un array con bubble sort y lo imprime ordenado
;
;  Los datos (6 bytes) se declaran con la directiva .db y se ordenan EN SITIO
;  (en la propia RAM) con el algoritmo de la burbuja; despues se recorren
;  imprimiendo cada elemento por el puerto OUT.
;
;  Registros:  B = puntero al elemento actual
;              C = comparaciones que quedan en la pasada
;              A = arr[i],  D = arr[i+1]
;  Celda RAM:  [PASSES] (0xF8) = pasadas que quedan
;
;  Salida esperada (OUT): 01 02 03 05 08 09
; ============================================================================

        .equ PASSES, 0xF8
        .equ NCEL,   6
        .equ NPAS,   5          ; NCEL - 1
        .equ NCOM,   5          ; NCEL - 1

inicio:
        LDI A, NPAS             ; pasadas restantes = N-1
        ST  A, [PASSES]

pasada:
        LDI B, arr              ; puntero al primer elemento
        LDI C, NCOM             ; comparaciones de esta pasada

bucle:
        LD  A, [B+0]            ; A = arr[i]
        LD  D, [B+1]            ; D = arr[i+1]
        CMP A, D
        JC  mayor_igual         ; C=1 -> A>=D (sin borrow)
        JMP siguiente           ; A<D  -> ya esta ordenado
mayor_igual:
        JZ  siguiente           ; A==D -> nada que hacer
        ST  D, [B+0]            ; A>D  -> intercambia la pareja
        ST  A, [B+1]
siguiente:
        INC B
        DEC C
        JNZ bucle               ; quedan comparaciones en esta pasada

        LD  A, [PASSES]         ; una pasada menos
        DEC A
        ST  A, [PASSES]
        JNZ pasada              ; quedan pasadas

        ; --- imprime el array ya ordenado ---
        LDI B, arr
        LDI C, NCEL
imprime:
        LD  A, [B+0]
        OUT A
        INC B
        DEC C
        JNZ imprime
        HLT

arr:
        .db 0x05, 0x03, 0x08, 0x01, 0x09, 0x02
