; ============================================================================
;  countdown.asm - Counts down from 9 to 0
;
;  Prints the numbers 9,8,...,1,0 on the OUT port.
;
;  Strategy: A starts at 9.  On each pass A is printed and 1 is subtracted.
;  The subtraction A - B (with B=1) leaves C=1 while A>=1 (there is no borrow
;  under the ISA's inverted convention), so "JC loop" repeats while numbers
;  remain.  When it tries to subtract with A already 0 the borrow appears (C=0)
;  and the loop ends.
; ============================================================================

        LDI A,9          ; first number to show
        LDI B,1          ; constant 1 to keep subtracting

loop:   OUT A            ; sends the current value to the port
        SUB A,B          ; A = A - 1   (C=1 while A>=1)
        JC  loop         ; if there was no borrow, another pass
        HLT              ; A reached 0: done
