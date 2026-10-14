; ---------------------------------------------------------------------------
;  inout.asm - IN input and port output OUT n, rd (Phase 9)
;
;  The testbench presents the value of the requested port on `in_data`:
;    port 0 -> 0x10, port 1 -> 0x11, port 2 -> 0x12, port 3 -> 0x13
;
;  Expected output (OUT): 10 12 AB 55
; ---------------------------------------------------------------------------

        IN  A               ; A = input from port 0 = 0x10
        OUT A               ; -> 10   (port 0, register form)

        IN  2, B            ; B = input from port 2 = 0x12
        OUT 2, B            ; -> 12   (port 2, ported form)

        LDI C, 0xAB
        OUT 1, C            ; -> AB   (port 1)

        LDI D, 0x55
        OUT D               ; -> 55   (port 0)

        HLT
