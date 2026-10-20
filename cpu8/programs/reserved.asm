; reserved.asm — encodings that the ISA leaves reserved
;
; They must behave as harmless no-ops, so that any binary that happens to
; contain them keeps running.  This demo also exercises DI, which no other
; program uses.
;
;   0xE2           OP_OUT with rs=10: reserved sub-operation (1-byte no-op)
;   0xFA 0xF0      prefix with xop=0xF: reserved extended operation (2-byte no-op)
;   0xF3           DI: disables interrupts (I is already 0 after reset)

LDI A, 0x42
OUT A               ; 42
.db 0xE2            ; reserved OUT sub-operation
.db 0xFA, 0xF0      ; reserved prefix sub-operation
DI
LDI B, 0x55
OUT B               ; 55
HLT
