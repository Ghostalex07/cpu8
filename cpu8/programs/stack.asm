; stack.asm - Test of PUSH/POP/RET (Phase 7.3)
; The stack starts with SP = 0xF0 and grows downwards:
;   PUSH A  ->  mem[SP] = A ; SP = SP - 1
;   POP  C  ->  SP = SP + 1 ; C = mem[SP]
;   RET     ->  SP = SP + 1 ; PC = mem[SP]
; Expected output: 2 1 1

        LDI A, 1
        LDI B, 2
        PUSH A          ; mem[F0] = 1, SP = EF
        PUSH B          ; mem[EF] = 2, SP = EE
        POP C           ; SP = EF, C = 2  (the last one in)
        POP D           ; SP = F0, D = 1  (the first one in)
        OUT C           ; prints 2
        OUT D           ; prints 1

        ; RET: push a return address and jump to it.
        LDI A, dest
        PUSH A          ; mem[F0] = addr(dest), SP = EF
        RET             ; SP = F0, PC = addr(dest)
        LDI A, 0xEE     ; must not run
        OUT A
dest:
        OUT D           ; prints 1 (proof that RET worked)
        HLT
