; ============================================================================
;  extensions3.asm - Demo of the extended ISA (Phase 12, prefix 0xFA)
;
;  Exercises, in a single program, the extended instructions added on top of
;  the base ISA: NEG, NOT, ADC, SBC, ROL, ROR, SWAP and the 3-byte LDW/STW.
;  It also checks the flags of the ones that modify them.
;
;  The queue of values written to the OUT port (port 0) is fixed:
;
;      FB 04         -> NEG 0x05 (-> -5) and NOT (-> 0x04)
;      10 11 FF 01   -> ADC without and with carry-in
;      1E 1F         -> SBC with carry-in 1 and 0
;      02 05 00 80   -> ROL twice and ROR twice (rotate through C)
;      34 12         -> SWAP A,B
;      77 88         -> LDW/STW with base B=0xC0 and offsets 0 / -1
;      99 99         -> STW/LDW with 16-bit carry (EA = 0x1C0 -> RAM[0xC0])
;      C1 C2         -> flag checks: NEG 0 -> C=1 ; ADC overflow -> V=1
;
;  Any failure takes a "bad" branch that prints an 0xE* marker and stops, so
;  the number/values of the outputs stop matching programs/extensions3.ref.
; ============================================================================

; ---------------------------------------------------------------------------
;  1) NEG / NOT
; ---------------------------------------------------------------------------
        LDI  A, 0x05
        NEG  A            ; A = 0 - 5 = 0xFB
        OUT  A            ; -> FB
        NOT  A            ; A = ~0xFB = 0x04
        OUT  A            ; -> 04

; ---------------------------------------------------------------------------
;  2) ADC (add with carry).  C starts at 0.
; ---------------------------------------------------------------------------
        LDI  A, 0x01
        LDI  B, 0x01
        ADD  A, B         ; 2, C = 0
        LDI  A, 0x0F
        LDI  B, 0x01
        ADC  A, B         ; 0x0F + 0x01 + 0 = 0x10
        OUT  A            ; -> 10
        ADC  A, B         ; 0x10 + 0x01 + 0 = 0x11
        OUT  A            ; -> 11
        LDI  A, 0xFF
        LDI  B, 0x00
        ADC  A, B         ; 0xFF + 0 + 0 = 0xFF, C = 0
        OUT  A            ; -> FF
        LDI  A, 0xFF
        ADDI A, 0x01      ; A = 0x00, C = 1
        LDI  A, 0x00
        LDI  B, 0x00
        ADC  A, B         ; 0 + 0 + 1 = 1
        OUT  A            ; -> 01

; ---------------------------------------------------------------------------
;  3) SBC (subtract with borrow)
; ---------------------------------------------------------------------------
        LDI  A, 0xFF
        ADDI A, 0x01      ; C = 1
        LDI  A, 0x20
        LDI  B, 0x01
        SBC  A, B         ; 0x20 - 0x01 - 1 = 0x1E, C = 1
        OUT  A            ; -> 1E
        LDI  A, 0x01
        LDI  B, 0x02
        SUB  A, B         ; A = 0xFF, C = 0 (borrow)
        LDI  A, 0x20
        LDI  B, 0x01
        SBC  A, B         ; 0x20 - 0x01 - 0 = 0x1F
        OUT  A            ; -> 1F

; ---------------------------------------------------------------------------
;  4) ROL / ROR (rotate through C)
; ---------------------------------------------------------------------------
        LDI  A, 0x01
        LDI  B, 0x01
        ADD  A, B         ; C = 0
        LDI  A, 0x81
        ROL  A            ; (0x81 << 1 | 0) = 0x02, C = 1
        OUT  A            ; -> 02
        ROL  A            ; (0x02 << 1 | 1) = 0x05, C = 0
        OUT  A            ; -> 05
        LDI  A, 0x01
        ROR  A            ; (0 << 7 | 0x01 >> 1) = 0x00, C = 1
        OUT  A            ; -> 00
        ROR  A            ; (1 << 7 | 0x00 >> 1) = 0x80, C = 0
        OUT  A            ; -> 80

; ---------------------------------------------------------------------------
;  5) SWAP (exchange two registers in one cycle)
; ---------------------------------------------------------------------------
        LDI  A, 0x12
        LDI  B, 0x34
        SWAP A, B         ; A = 0x34, B = 0x12
        OUT  A            ; -> 34
        OUT  B            ; -> 12

; ---------------------------------------------------------------------------
;  6) LDW / STW (3 bytes: 16-bit effective address = rs + off, low byte used,
;     C gets the carry out of bit 7).  Base B = 0xC0 is above the program.
; ---------------------------------------------------------------------------
        LDI  B, 0xC0
        LDI  A, 0x77
        STW  A, [B+0]     ; RAM[0xC0] = 0x77
        LDI  A, 0x88
        STW  A, [B-1]     ; RAM[0xBF] = 0x88 (negative displacement)
        LDI  A, 0x00
        LDW  A, [B+0]     ; A = 0x77
        OUT  A            ; -> 77
        LDW  C, [B-1]     ; C = 0x88
        OUT  C            ; -> 88
        ; 16-bit pointer: EA = 0xC1 + 0xFF = 0x1C0 -> RAM[0xC0], C = 1.
        LDI  C, 0xC1
        LDI  A, 0x99
        STW  A, [C-1]     ; RAM[0xC0] = 0x99, C = 1
        OUT  A            ; -> 99
        LDI  A, 0x00
        LDW  A, [C-1]     ; A = RAM[0xC0] = 0x99, C = 1
        OUT  A            ; -> 99

; ---------------------------------------------------------------------------
;  7) Flag checks
; ---------------------------------------------------------------------------
        ; NEG 0 -> C = 1 (0 - 0 has no borrow out).
        LDI  A, 0x00
        NEG  A            ; A = 0, C = 1, Z = 1
        JC   neg_ok
        LDI  A, 0xE1
        OUT  A
        HLT
neg_ok: LDI  A, 0xC1
        OUT  A            ; -> C1

        ; ADC overflow: 0x7F + 0x00 + C(=1) = 0x80 -> V = 1.
        LDI  A, 0x7F
        LDI  B, 0x00
        ADC  A, B         ; C = 1 (from the NEG above)
        JVS  v_ok
        LDI  A, 0xE2
        OUT  A
        HLT
v_ok:   LDI  A, 0xC2
        OUT  A            ; -> C2
        HLT
