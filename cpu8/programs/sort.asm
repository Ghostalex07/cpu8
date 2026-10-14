; ============================================================================
;  sort.asm - Sorts an array with bubble sort and prints it sorted
;
;  The data (6 bytes) is declared with the .db directive and sorted IN PLACE
;  (in RAM itself) with the bubble algorithm; afterwards it is walked through,
;  printing each element on the OUT port.
;
;  Registers:  B = pointer to the current element
;              C = comparisons left in the pass
;              A = arr[i],  D = arr[i+1]
;  RAM cell:   [PASSES] (0xF8) = passes left
;
;  Expected output (OUT): 01 02 03 05 08 09
; ============================================================================

        .equ PASSES, 0xF8
        .equ NCEL,   6
        .equ NPAS,   5          ; NCEL - 1
        .equ NCOM,   5          ; NCEL - 1

start:
        LDI A, NPAS             ; passes left = N-1
        ST  A, [PASSES]

pass:
        LDI B, arr              ; pointer to the first element
        LDI C, NCOM             ; comparisons in this pass

loop:
        LD  A, [B+0]            ; A = arr[i]
        LD  D, [B+1]            ; D = arr[i+1]
        CMP A, D
        JC  greater_equal       ; C=1 -> A>=D (no borrow)
        JMP next                ; A<D  -> already sorted
greater_equal:
        JZ  next                ; A==D -> nothing to do
        ST  D, [B+0]            ; A>D  -> swap the pair
        ST  A, [B+1]
next:
        INC B
        DEC C
        JNZ loop                ; comparisons left in this pass

        LD  A, [PASSES]         ; one fewer pass
        DEC A
        ST  A, [PASSES]
        JNZ pass                ; passes left

        ; --- print the now sorted array ---
        LDI B, arr
        LDI C, NCEL
print:
        LD  A, [B+0]
        OUT A
        INC B
        DEC C
        JNZ print
        HLT

arr:
        .db 0x05, 0x03, 0x08, 0x01, 0x09, 0x02
