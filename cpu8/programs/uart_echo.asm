; ============================================================================
;  uart_echo.asm - UART console demo for the iCEstick
;
;  Prints a short banner through the serial port (FT2232H channel B, 115200
;  8N1, /dev/ttyUSB1) and then echoes every received byte back to the host
;  and to the 5 LEDs.  Polls the console status (port 3) so a frame is only
;  read after it has been received.
;
;  This program never halts on purpose: it is a hardware demo, not part of the
;  halt-based program regression.  `tb/top_uart_tb.v` exercises the same
;  logic with a faster divisor.
; ============================================================================

        LDI A, 0x43   ; 'C'
        OUT 1, A
        LDI A, 0x50   ; 'P'
        OUT 1, A
        LDI A, 0x55   ; 'U'
        OUT 1, A
        LDI A, 0x38   ; '8'
        OUT 1, A
        LDI A, 0x0D
        OUT 1, A
        LDI A, 0x0A
        OUT 1, A

loop:
        IN 3, A       ; console status
        SHR A         ; rx_ready -> carry
        JNC loop
        IN 1, A       ; read the byte (acknowledges rx_ready)
        OUT 1, A      ; echo it
        OUT 0, A      ; show it on the LEDs
        JMP loop
