; ============================================================================
;  monitor.asm - Mini serial monitor (UART console)
;
;  Prints a banner, echoes every received byte and answers 'H' with a short
;  help line.  It runs forever, so it is a hardware demo (not a halt-based
;  regression program).
;
;  I/O map (docs/ISA.md §10.9):
;    port 1 OUT: send a byte on the UART
;    port 1 IN : read the received byte (clears rx_ready)
;    port 3 IN : status: bit0 rx_ready, bit1 tx_busy, bit2 overrun, bit3 rx_busy
; ============================================================================

        LDI B, banner
        CALL putstr

loop:
        ; Wait for a received byte.
wait_rx:
        IN 3, A
        ANDI A, 0x01
        JZ wait_rx
        IN 1, A                 ; read it (also clears rx_ready)
        CALL putchar            ; echo
        CMPI A, 0x48            ; 'H'
        JNZ loop
        LDI B, help
        CALL putstr
        JMP loop

; ---- putchar: send A on the UART, waiting for the transmitter. Clobbers D.
putchar:
        MOV D, A
pc_wait:
        IN 3, A
        ANDI A, 0x02            ; tx_busy
        JNZ pc_wait
        MOV A, D
        OUT 1, A
        RET

; ---- putstr: send the NUL-terminated string pointed to by B. Uses A and D.
putstr:
        LD A, [B]
        OR A, A
        JZ ps_end
        CALL putchar
        INC B
        JMP putstr
ps_end:
        RET

banner: .db "cpu8 monitor\r\n", 0
help:   .db "commands: H = help\r\n", 0
