; ============================================================================
;  pmod.asm - Pmod input demo for the iCEstick
;
;  Reads the byte on the Pmod data pins with IN and sends it back with OUT in
;  an endless loop.  The top-level shows the five least significant bits on
;  the LEDs, so moving the Pmod inputs between 3.3 V and GND changes the LED
;  pattern in real time.
;
;  This program never halts on purpose: it is a hardware demo, not part of the
;  halt-based program regression.  `tb/top_pmod_tb.v` loads the assembled image
;  and checks several input values; `make fpga FPGA_PROG=pmod` builds the
;  bitstream.
; ============================================================================

loop:
        IN  A           ; A = byte on the Pmod data pins
        OUT A           ; show it on the LEDs
        JMP loop        ; repeat forever
