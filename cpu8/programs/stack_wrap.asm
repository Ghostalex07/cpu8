; ============================================================================
;  stack_wrap.asm - Stack pointer wrap-around test
;
;  The stack starts at SP = 0xF0 and grows downwards.  A loop performs 0xF1
;  pushes: SP crosses 0x80, reaches 0x00, and wraps 0x00 -> 0xFF.  The first
;  byte of this code is overwritten by the first push, but it has already been
;  fetched; the rest of the loop lives above the stack and stays intact.
;
;  After the loop A = 0xF1.  The next push (with SP = 0xFF) writes it at 0xFF,
;  proving the wrap, and the two LD instructions read there and at 0x00 (the
;  last regular push, value 0xF0).
;
;  Expected output: F1 (written after the wrap) and F0 (last value pushed at
;  0x00 before it).
; ============================================================================

        .nostack         ; the code lives above SP; the stack never clobbers it
        JMP start
        .org 0xF0

start:  LDI C, 0xF1     ; 241 pushes: SP F0 -> 00 -> FF
loop:   PUSH A          ; A starts at 0 and is incremented after every push
        INC A
        DEC C
        JNZ loop

        PUSH A          ; SP = FF after the wrap: store F1 at 0xFF
        LD B, [0xFF]
        OUT B           ; F1
        LD B, [0x00]
        OUT B           ; F0
        HLT
