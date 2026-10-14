; incdec.asm - Test of INC and DEC (Phase 7.2)
;
; INC/DEC update Z and N, but must NOT touch flag C.
;
; First part: counts 1..5 with INC (checking Z via CMP) and then a DEC.
; Second part: forces C=0 with a subtraction that produces a borrow and does
;              INC/DEC; if they touched C, JC would jump to the error branch.

        LDI A,0
        LDI B,5
loop:   INC A          ; A = A + 1
        OUT A          ; prints 1,2,3,4,5
        CMP A,B        ; Z=1 when A==5
        JNZ loop
        DEC A          ; A = 4
        OUT A          ; prints 4

        ; --- C must not change with INC/DEC ---
        LDI A,0
        LDI B,1
        SUB A,B        ; A = 0-1 = FF ; C = 0 (there was a borrow)
        INC A          ; A = 00 ; C must stay 0
        JC  error
        DEC B          ; B = 00 ; C must stay 0
        JC  error
        HLT

error:  OUT A          ; only printed if something failed
        HLT
