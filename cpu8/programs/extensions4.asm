; ============================================================
;  extensions4.asm - Demo of the rest of the 0xFA prefix (Phase 12)
;
;  Exercises TEST, PUSHF, POPF, ADCW and SUBW (docs/ISA.md section 10.10):
;
;  - TEST writes only flags (Z, N; C=0, V=0) and leaves rd untouched.
;  - PUSHF/POPF save and restore the flags byte on the stack
;    (bit0 C, bit1 Z, bit2 N, bit3 V, bit4 I).
;  - ADCW/SUBW operate on 16-bit register pairs: A = A:B and C = C:D.
;    SUBW also subtracts the incoming C flag (rd - rs - C), so C is
;    cleared with TEST before a "plain" subtraction.
;
;  Outputs on port 0 (one value per line in the .ref):
;    0F 01 02 03 04 07 03 05 00 02 06 05 02 07
;    00 FF 08 09 0A FF FF 00 02 0B 0C
; ============================================================

; ---- TEST: an AND that only writes flags ----
        LDI A, 0x0F
        LDI B, 0x33
        TEST A, B           ; 0F & 33 = 03 -> Z=0, C=0; A untouched
        OUT A               ; 0F (TEST does not write rd)
        JZ  bad             ; Z=0 -> must NOT jump
        LDI D, 0x01
        OUT D               ; 01 (JZ not taken: Z=0)
        LDI D, 0x00
        TEST D, D           ; 00 & 00 = 00 -> Z=1
        JZ  z1              ; Z=1 -> taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
z1:     LDI D, 0x02
        OUT D               ; 02 (JZ taken: Z=1)

; ---- PUSHF / POPF: flags on the stack ----
        LDI A, 0xFF
        ADDI A, 0x01        ; A=00, C=1, Z=1 (FF+1 = 100)
        PUSHF               ; mem[0xF0] = {I,V,N,Z,C} = 0x03
        LDI A, 0x00
        SUBI A, 0x01        ; A=FF, C=0, Z=0, N=1 (clobbers everything)
        POPF                ; restores C=1, Z=1 (I=0)
        JC  j1              ; C=1 -> taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
j1:     LDI D, 0x03
        OUT D               ; 03 (C restored = 1)
        JZ  j2              ; Z=1 -> taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
j2:     LDI D, 0x04
        OUT D               ; 04 (Z restored = 1)

; ---- ADCW: 16-bit addition over the pairs ----
        LDI A, 0x03
        LDI B, 0x02         ; pair A:B = 0x0203
        LDI C, 0x04
        LDI D, 0x01         ; pair C:D = 0x0104
        TEST A, C           ; clears C (03 & 04 = 00)
        ADCW A, C           ; 0203 + 0104 + 0 = 0307
        OUT A               ; 07 (low byte)
        OUT 0, B            ; 03 (high byte)
        JNZ m1              ; Z=0 -> taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
m1:     LDI D, 0x05
        OUT D               ; 05 (Z=0)

; internal carry: 00FF + 0101 = 0200 (Z=0 even though the low byte is 0)
        LDI A, 0xFF
        LDI B, 0x00         ; pair A:B = 0x00FF
        LDI C, 0x01
        LDI D, 0x01         ; pair C:D = 0x0101
        TEST A, C           ; clears C
        ADCW A, C           ; 00FF + 0101 + 0 = 0200
        OUT A               ; 00 (low byte)
        OUT 0, B            ; 02 (high byte)
        JNZ m2              ; Z=0 -> taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
m2:     LDI D, 0x06
        OUT D               ; 06 (Z=0 with low byte 0)

; ---- SUBW: 16-bit subtraction (incoming C = borrow to subtract) ----
        LDI A, 0x07
        LDI B, 0x03         ; pair A:B = 0x0307
        LDI C, 0x02
        LDI D, 0x01         ; pair C:D = 0x0102
        TEST A, C           ; clears C -> plain subtraction
        SUBW A, C           ; 0307 - 0102 - 0 = 0205
        OUT A               ; 05 (low byte)
        OUT 0, B            ; 02 (high byte)
        JC  s1              ; C=1 -> no borrow, taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
s1:     LDI D, 0x07
        OUT D               ; 07 (C=1: no borrow)

; with borrow: 0100 - 0200 = FF00 (C=0 afterwards)
        LDI A, 0x00
        LDI B, 0x01         ; pair A:B = 0x0100
        LDI C, 0x00
        LDI D, 0x02         ; pair C:D = 0x0200
        TEST A, C           ; clears C
        SUBW A, C           ; 0100 - 0200 - 0 = FF00
        OUT A               ; 00 (low byte)
        OUT 0, B            ; FF (high byte)
        JC  s2              ; C=0 -> must NOT jump
        LDI D, 0x08
        OUT D               ; 08 (C=0: there was a borrow)
        JMI s3              ; N=1 -> taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
s3:     LDI D, 0x09
        OUT D               ; 09 (N=1)
        JNZ s4              ; Z=0 -> taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
s4:     LDI D, 0x0A
        OUT D               ; 0A (Z=0 with low byte 0)
        JMP s5
s2:     LDI D, 0xEE
        OUT D               ; MUST NOT RUN
; double borrow: 0000 - 0001 = FFFF
s5:     LDI A, 0x00
        LDI B, 0x00         ; pair A:B = 0x0000
        LDI C, 0x01
        LDI D, 0x00         ; pair C:D = 0x0001
        TEST A, C           ; clears C
        SUBW A, C           ; 0000 - 0001 - 0 = FFFF
        OUT A               ; FF (low byte)
        OUT 0, B            ; FF (high byte)

; ---- ADCW with carry in: 01FF + 0000 + 1 = 0200 ----
        LDI A, 0xFF
        LDI B, 0x01         ; pair A:B = 0x01FF
        LDI C, 0x00
        LDI D, 0x00         ; pair C:D = 0x0000
        CMP A, A            ; C=1 (carry in)
        ADCW A, C           ; 01FF + 0000 + 1 = 0200
        OUT A               ; 00 (low byte)
        OUT 0, B            ; 02 (high byte)

; ---- ADCW with zero result: FFFF + 0000 + 1 = 0000 ----
        LDI A, 0xFF
        LDI B, 0xFF         ; pair A:B = 0xFFFF
        LDI C, 0x00
        LDI D, 0x00         ; pair C:D = 0x0000
        CMP A, A            ; C=1
        ADCW A, C           ; FFFF + 0000 + 1 = 0000 -> Z=1, C=1
        JZ  z2              ; Z=1 -> taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
z2:     LDI D, 0x0B
        OUT D               ; 0B (Z=1: all 16 bits zero)
        JC  z3              ; C=1 -> taken
        LDI D, 0xEE
        OUT D               ; MUST NOT RUN
z3:     LDI D, 0x0C
        OUT D               ; 0C (C=1: carry out)
        HLT
bad:    LDI D, 0xEE
        OUT D               ; MUST NOT RUN
        HLT
