; ============================================================================
;  extensions.asm - Demo de las extensiones del ISA (Fase 8)
;
;  Ejercita, en un solo programa, las tres familias nuevas y comprueba que su
;  comportamiento es el esperado.  La salida por el puerto OUT es fija:
;
;      0A 0F 08     -> LDI/ADDI/SUBI (+ CMPI como comprobacion)
;      22 33 11 44  -> LD/ST indexados con base B=0xC0 y desplazamientos +/-;
;                      el 44 se recupera de [B-1] (offset negativo)
;      A1 A2 A3     -> saltos con signo (N^V): JLT no tomado, JGE/JLE/JGT si
;      B1 B2        -> saltos de estado: JVS/JMI (V,N) y JVC/JPL
;
;  Cualquier fallo toma una rama "mal" que imprime un marcador 0xE* y termina,
;  con lo que el valor/numero de salidas deja de coincidir con el .ref.
; ============================================================================

; ---------------------------------------------------------------------------
;  1) Inmediatos de la ALU: ADDI / SUBI / CMPI (pagina 0x1, subop en rs)
; ---------------------------------------------------------------------------
        LDI  A, 10       ; A = 10
        OUT  A           ; -> 0A
        ADDI A, 5        ; A = 15
        OUT  A           ; -> 0F
        SUBI A, 7        ; A = 8
        OUT  A           ; -> 08
        CMPI A, 8        ; A - 8 = 0  -> Z=1
        JZ   idx         ; si CMPI/JZ fallan, cae al error
        LDI  A, 0xE0
        OUT  A
        HLT

; ---------------------------------------------------------------------------
;  2) Direccionamiento indexado: LD/ST rd,[rs+off] con base B = 0xC0.
;     Se usan off 0/1/2 y off = -1 (0xFF) para probar tambien el signo.
;     La base 0xC0 y 0xBF estan muy por encima del tamano del programa.
; ---------------------------------------------------------------------------
idx:    LDI  B, 0xC0      ; base = 0xC0
        LDI  A, 0x11
        ST   A, [B+0]     ; RAM[0xC0] = 0x11
        LDI  A, 0x22
        ST   A, [B+1]     ; RAM[0xC1] = 0x22
        LDI  A, 0x33
        ST   A, [B+2]     ; RAM[0xC2] = 0x33
        LDI  A, 0x44
        ST   A, [B-1]     ; RAM[0xBF] = 0x44  (offset negativo)
        LD   A, [B+1]     ; A = 0x22
        OUT  A            ; -> 22
        LD   C, [B+2]     ; C = 0x33
        OUT  C            ; -> 33
        LD   A, [B+0]     ; A = 0x11
        OUT  A            ; -> 11
        LD   A, [B-1]     ; A = 0x44
        OUT  A            ; -> 44

; ---------------------------------------------------------------------------
;  3) Saltos con signo (N^V).  A=0x7F(127), B=0xFF(-1): con signo 127 > -1,
;     asi que JLT NO debe saltar y JGE si (sin signo diria "menor").
; ---------------------------------------------------------------------------
        LDI  A, 0x7F
        LDI  B, 0xFF
        CMP  A, B
        JLT  mal3         ; no debe saltar
        JGE  ok3a
mal3:   LDI  A, 0xE1
        OUT  A
        HLT
ok3a:   LDI  A, 0xA1
        OUT  A            ; -> A1

        ; A=0xFE(-2), B=0x7F(127): -2 <= 127  -> JLE
        LDI  A, 0xFE
        LDI  B, 0x7F
        CMP  A, B
        JLE  ok3b
        LDI  A, 0xE2
        OUT  A
        HLT
ok3b:   LDI  A, 0xA2
        OUT  A            ; -> A2

        ; A=0x01(1), B=0xFE(-2): 1 > -2  -> JGT
        LDI  A, 0x01
        LDI  B, 0xFE
        CMP  A, B
        JGT  ok3c
        LDI  A, 0xE3
        OUT  A
        HLT
ok3c:   LDI  A, 0xA3
        OUT  A            ; -> A3

; ---------------------------------------------------------------------------
;  4) Saltos de estado: JVS/JMI (desbordamiento y negativo) y JVC/JPL.
; ---------------------------------------------------------------------------
        LDI  A, 0x7F
        LDI  B, 0x01
        ADD  A, B         ; 0x7F + 1 = 0x80 -> V=1, N=1
        JVS  st_v         ; V=1
        LDI  A, 0xE4
        OUT  A
        HLT
st_v:   JMI  st_n         ; N=1
        LDI  A, 0xE5
        OUT  A
        HLT
st_n:   LDI  A, 0xB1
        OUT  A            ; -> B1

        LDI  A, 0x01
        LDI  B, 0x01
        ADD  A, B         ; 0x02 -> V=0, N=0
        JVC  st_c         ; V=0
        LDI  A, 0xE6
        OUT  A
        HLT
st_c:   JPL  st_p         ; N=0
        LDI  A, 0xE7
        OUT  A
        HLT
st_p:   LDI  A, 0xB2
        OUT  A            ; -> B2
        HLT
