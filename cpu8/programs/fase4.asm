; ===========================================================================
;  fase4.asm - Phase 4 test program (written by hand)
;
;  This file is the real source of the program: the assembler (Phase 5,
;  asm/assembler.py) translates it to fase4.hex, which is what the CPU loads.
;
;  What it does: stores 7 in memory, reads it back and then counts down from
;  7 to 1, sending each value to the OUT port. It ends with HLT.
;
;  Encoding (high byte = opcode<<4 | rd<<2 | rs):
;    0x00 : LDI A, 7      -> 10 07
;    0x02 : ST  A, [0x20] -> 40 20   ; M[0x20] = 7
;    0x04 : LD  A, [0x20] -> 30 20   ; A = M[0x20] = 7
;    0x06 : LDI B, 1      -> 14 01
;    0x08 : OUT A         -> E0      ; prints A (loop)
;    0x09 : SUB A, B      -> 61      ; A = A - 1
;    0x0A : JNZ 0x08      -> D1 08   ; repeats while A != 0
;    0x0C : HLT           -> F0
;
;  Expected output: 7 6 5 4 3 2 1
; ===========================================================================

        LDI A, 7
        ST  A, [0x20]
        LD  A, [0x20]
        LDI B, 1
loop:   OUT A
        SUB A, B
        JNZ loop
        HLT
