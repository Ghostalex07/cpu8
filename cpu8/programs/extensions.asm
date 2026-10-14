; ============================================================================
;  extensions.asm - Demo of the ISA extensions (Phase 8)
;
;  Exercises, in a single program, the three new families and checks that their
;  behaviour is as expected.  The output on the OUT port is fixed:
;
;      0A 0F 08     -> LDI/ADDI/SUBI (+ CMPI as a check)
;      22 33 11 44  -> indexed LD/ST with base B=0xC0 and +/- offsets;
;                      the 44 is recovered from [B-1] (negative offset)
;      A1 A2 A3     -> signed branches (N^V): JLT not taken, JGE/JLE/JGT taken
;      B1 B2        -> status branches: JVS/JMI (V,N) and JVC/JPL
;
;  Any failure takes a "bad" branch that prints an 0xE* marker and stops, so the
;  value/number of outputs stops matching the .ref.
; ============================================================================

; ---------------------------------------------------------------------------
;  1) ALU immediates: ADDI / SUBI / CMPI (page 0x1, subop in rs)
; ---------------------------------------------------------------------------
        LDI  A, 10       ; A = 10
        OUT  A           ; -> 0A
        ADDI A, 5        ; A = 15
        OUT  A           ; -> 0F
        SUBI A, 7        ; A = 8
        OUT  A           ; -> 08
        CMPI A, 8        ; A - 8 = 0  -> Z=1
        JZ   idx         ; if CMPI/JZ fail, it falls into the error
        LDI  A, 0xE0
        OUT  A
        HLT

; ---------------------------------------------------------------------------
;  2) Indexed addressing: LD/ST rd,[rs+off] with base B = 0xC0.
;     Offsets 0/1/2 and off = -1 (0xFF) are used to test the sign too.
;     The bases 0xC0 and 0xBF are well above the size of the program.
; ---------------------------------------------------------------------------
idx:    LDI  B, 0xC0      ; base = 0xC0
        LDI  A, 0x11
        ST   A, [B+0]     ; RAM[0xC0] = 0x11
        LDI  A, 0x22
        ST   A, [B+1]     ; RAM[0xC1] = 0x22
        LDI  A, 0x33
        ST   A, [B+2]     ; RAM[0xC2] = 0x33
        LDI  A, 0x44
        ST   A, [B-1]     ; RAM[0xBF] = 0x44  (negative offset)
        LD   A, [B+1]     ; A = 0x22
        OUT  A            ; -> 22
        LD   C, [B+2]     ; C = 0x33
        OUT  C            ; -> 33
        LD   A, [B+0]     ; A = 0x11
        OUT  A            ; -> 11
        LD   A, [B-1]     ; A = 0x44
        OUT  A            ; -> 44

; ---------------------------------------------------------------------------
;  3) Signed branches (N^V).  A=0x7F(127), B=0xFF(-1): signed, 127 > -1,
;     so JLT must NOT branch and JGE must (unsigned would say "lower").
; ---------------------------------------------------------------------------
        LDI  A, 0x7F
        LDI  B, 0xFF
        CMP  A, B
        JLT  bad3         ; must not branch
        JGE  ok3a
bad3:   LDI  A, 0xE1
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
;  4) Status branches: JVS/JMI (overflow and negative) and JVC/JPL.
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
