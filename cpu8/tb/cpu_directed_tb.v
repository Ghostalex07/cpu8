// ============================================================================
//  cpu_directed_tb.v - Casos limite que ningun programa demo ejercita a nivel
//  de CPU (los programas de programs/ cubren el camino feliz).
//
//    A) CALL/RET anidados (2 niveles) y direcciones de retorno correctas.
//    B) INC/DEC no tocan el flag C (se fuerza C=0 con un SUB que da borrow).
//    C) SHL/SHR a nivel de CPU (cableado alu_sh = rs[0]).
//    D) Direccionamiento indirecto con rd == rs (LD A,[A] / ST B,[A]).
//    E) Pila LIFO (PUSH/POP).
//    F) IRQ: la direccion de retorno es la frontera de instruccion (tras EI).
//    G) Inmediatos ADDI/SUBI/CMPI y flag V (JVS por desbordamiento).
//    H) Direccionamiento indexado LD/ST rd,[rs+off].
//    I) Saltos con signo (JLT/JGE) sobre el flag V.
//
//  Los programas se escriben directamente en RAM por acceso jerarquico, sin
//  depender del ensamblador.  Se compara la secuencia de OUT con lo esperado.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module cpu_directed_tb;

    reg clk = 0, rst = 1, irq = 0;
    reg [7:0] in_data = 8'h00;   // lo fija el caso dirigido de E/S
    wire       halted, out_valid;
    wire [7:0] out_data;
    wire [1:0] in_port, out_port;

    cpu #(.IRQ_VECTOR(8'h10)) dut (
        .clk(clk), .rst(rst), .irq(irq),
        .halted(halted), .out_data(out_data), .out_valid(out_valid),
        .in_data(in_data), .in_port(in_port), .out_port(out_port)
    );

    always #5 clk = ~clk;

    integer errors = 0;
    integer i;
    reg [7:0] outs [0:15];
    reg [1:0] out_ports [0:15];
    integer   nouts;

    task limpia_mem;
        begin
            for (i = 0; i < 256; i = i + 1) dut.u_ram.mem[i] = 8'h00;
        end
    endtask

    task poke;
        input integer a;
        input [7:0]   d;
        begin dut.u_ram.mem[a] = d; end
    endtask

    task arranca;                 // reset sincrono 2 ciclos, irq=0
        begin
            rst = 1; irq = 0;
            repeat (2) @(posedge clk);
            @(negedge clk) rst = 0;
        end
    endtask

    task corre;                   // ejecuta hasta HLT recogiendo OUT
        input integer max;
        begin
            nouts = 0; i = 0;
            while (!halted && i < max) begin
                @(posedge clk); #1;
                if (out_valid) begin
                    if (nouts < 16) begin
                        outs[nouts]      = out_data;
                        out_ports[nouts] = out_port;
                    end
                    nouts = nouts + 1;
                end
                i = i + 1;
            end
        end
    endtask

    task chkout;
        input integer idx;
        input [7:0]   exp;
        begin
            if (idx >= nouts) begin
                errors = errors + 1;
                $display("  FALLO: falta OUT[%0d] (esperado %02h)", idx, exp);
            end else if (outs[idx] !== exp) begin
                errors = errors + 1;
                $display("  FALLO OUT[%0d]=%02h (esperado %02h)", idx, outs[idx], exp);
            end
        end
    endtask

    task chknout;
        input integer exp;
        begin
            if (nouts !== exp) begin
                errors = errors + 1;
                $display("  FALLO: %0d salidas (esperado %0d)", nouts, exp);
            end
        end
    endtask

    task chkport;
        input integer idx;
        input [1:0]   exp;
        begin
            if (idx >= nouts) begin
                errors = errors + 1;
                $display("  FALLO: falta OUT[%0d] para el puerto", idx);
            end else if (out_ports[idx] !== exp) begin
                errors = errors + 1;
                $display("  FALLO puerto de OUT[%0d]=%0d (esperado %0d)",
                         idx, out_ports[idx], exp);
            end
        end
    endtask

    initial begin
        $display("=== Testbench dirigido de la CPU (casos limite) ===");

        // A) CALL/RET anidados -> OUT B = 1
        limpia_mem;
        poke(8'h00,8'hC1); poke(8'h01,8'h04); // CALL 0x04
        poke(8'h02,8'hE4);                    // OUT B
        poke(8'h03,8'hF0);                    // HLT
        poke(8'h04,8'hC1); poke(8'h05,8'h08); // CALL 0x08
        poke(8'h06,8'hF1);                    // RET
        poke(8'h08,8'h01);                    // INC B
        poke(8'h09,8'hF1);                    // RET
        arranca; corre(2000);
        chknout(1); chkout(0,8'h01);

        // B) INC/DEC no tocan C -> OUT C = 0xAA
        limpia_mem;
        poke(8'h00,8'h10); poke(8'h01,8'h00); // LDI A,0
        poke(8'h02,8'h14); poke(8'h03,8'h01); // LDI B,1
        poke(8'h04,8'h61);                    // SUB A,B -> C=0 (borrow)
        poke(8'h05,8'h00);                    // INC A
        poke(8'h06,8'hD2); poke(8'h07,8'h0F); // JC 0x0F
        poke(8'h08,8'h05);                    // DEC B
        poke(8'h09,8'hD2); poke(8'h0A,8'h0F); // JC 0x0F
        poke(8'h0B,8'h18); poke(8'h0C,8'hAA); // LDI C,0xAA
        poke(8'h0D,8'hE8);                    // OUT C
        poke(8'h0E,8'hF0);                    // HLT
        poke(8'h0F,8'h18); poke(8'h10,8'h0B); // (fallo) LDI C,0x0B
        poke(8'h11,8'hE8); poke(8'h12,8'hF0); // OUT C ; HLT
        arranca; corre(2000);
        chknout(1); chkout(0,8'hAA);

        // C) SHL/SHR en la CPU -> 0x02, 0x01
        limpia_mem;
        poke(8'h00,8'h10); poke(8'h01,8'h81); // LDI A,0x81
        poke(8'h02,8'hB0);                    // SHL A
        poke(8'h03,8'hE0);                    // OUT A
        poke(8'h04,8'hB1);                    // SHR A
        poke(8'h05,8'hE0);                    // OUT A
        poke(8'h06,8'hF0);                    // HLT
        arranca; corre(2000);
        chknout(2); chkout(0,8'h02); chkout(1,8'h01);

        // D) Indirecto rd==rs -> OUT A = 0x55
        limpia_mem;
        poke(8'h00,8'h10); poke(8'h01,8'h20); // LDI A,0x20
        poke(8'h02,8'h14); poke(8'h03,8'h55); // LDI B,0x55
        poke(8'h04,8'hF5); poke(8'h05,8'h04); // ST B,[A]
        poke(8'h06,8'hF4); poke(8'h07,8'h00); // LD A,[A]
        poke(8'h08,8'hE0);                    // OUT A
        poke(8'h09,8'hF0);                    // HLT
        arranca; corre(2000);
        chknout(1); chkout(0,8'h55);

        // E) Pila LIFO -> 0x22, 0x11
        limpia_mem;
        poke(8'h00,8'h10); poke(8'h01,8'h11); // LDI A,0x11
        poke(8'h02,8'h14); poke(8'h03,8'h22); // LDI B,0x22
        poke(8'h04,8'h08);                    // PUSH A
        poke(8'h05,8'h09);                    // PUSH B
        poke(8'h06,8'h0E);                    // POP C
        poke(8'h07,8'h0F);                    // POP D
        poke(8'h08,8'hE8);                    // OUT C
        poke(8'h09,8'hEC);                    // OUT D
        poke(8'h0A,8'hF0);                    // HLT
        arranca; corre(2000);
        chknout(2); chkout(0,8'h22); chkout(1,8'h11);

        // F) IRQ: retorno en frontera de instruccion -> OUT C = 1
        limpia_mem;
        poke(8'h00,8'hF2);                    // EI
        poke(8'h01,8'h10); poke(8'h02,8'h77); // LDI A,0x77
        poke(8'h03,8'hE8);                    // OUT C
        poke(8'h04,8'hF0);                    // HLT
        poke(8'h10,8'h02);                    // (handler) INC C
        poke(8'h11,8'hF1);                    // RET
        arranca; irq = 1; corre(2000);
        chknout(1); chkout(0,8'h01);

        // G) Inmediatos ADDI/SUBI/CMPI y flag V -> 0x0F, 0x09, 0x09, 0x80
        limpia_mem;
        poke(8'h00,8'h10); poke(8'h01,8'h0A); // LDI  A,10
        poke(8'h02,8'h11); poke(8'h03,8'h05); // ADDI A,5   -> 15
        poke(8'h04,8'hE0);                    // OUT A      -> 0x0F
        poke(8'h05,8'h12); poke(8'h06,8'h06); // SUBI A,6   -> 9
        poke(8'h07,8'hE0);                    // OUT A      -> 9
        poke(8'h08,8'h13); poke(8'h09,8'h09); // CMPI A,9   -> Z=1
        poke(8'h0A,8'hD0); poke(8'h0B,8'h0E); // JZ 0x0E
        poke(8'h0C,8'h10); poke(8'h0D,8'hFF); // LDI  A,0xFF (no debe ejecutarse)
        poke(8'h0E,8'hE0);                    // OUT A      -> 9
        poke(8'h0F,8'h14); poke(8'h10,8'h7F); // LDI  B,0x7F
        poke(8'h11,8'h15); poke(8'h12,8'h01); // ADDI B,1   -> 0x80, V=1
        poke(8'h13,8'hD8); poke(8'h14,8'h17); // JVS 0x17
        poke(8'h15,8'h14); poke(8'h16,8'h00); // LDI  B,0 (no debe ejecutarse)
        poke(8'h17,8'hE4);                    // OUT B      -> 0x80
        poke(8'h18,8'hF0);                    // HLT
        arranca; corre(2000);
        chknout(4); chkout(0,8'h0F); chkout(1,8'h09);
        chkout(2,8'h09); chkout(3,8'h80);

        // H) Indexado LD/ST rd,[rs+off] -> OUT D = 0xAA
        limpia_mem;
        poke(8'h00,8'h10); poke(8'h01,8'hAA); // LDI A,0xAA
        poke(8'h02,8'h14); poke(8'h03,8'h30); // LDI B,0x30
        poke(8'h04,8'h41); poke(8'h05,8'h03); // ST A,[B+3]  -> RAM[0x33]=0xAA
        poke(8'h06,8'h18); poke(8'h07,8'h30); // LDI C,0x30
        poke(8'h08,8'h3E); poke(8'h09,8'h03); // LD D,[C+3]  -> D=0xAA
        poke(8'h0A,8'hEC);                    // OUT D
        poke(8'h0B,8'hF0);                    // HLT
        arranca; corre(2000);
        chknout(1); chkout(0,8'hAA);

        // I) Saltos con signo (JLT/JGE) -> OUT: 0x01, 0xFF
        limpia_mem;
        poke(8'h00,8'h10); poke(8'h01,8'hFF); // LDI A,0xFF (-1)
        poke(8'h02,8'h14); poke(8'h03,8'h01); // LDI B,1
        poke(8'h04,8'hA1);                    // CMP A,B     -> -1 < 1 (N!=V)
        poke(8'h05,8'hD4); poke(8'h06,8'h09); // JLT 0x09
        poke(8'h07,8'h14); poke(8'h08,8'h7F); // LDI B,0x7F (no debe ejecutarse)
        poke(8'h09,8'hE4);                    // OUT B       -> 1
        poke(8'h0A,8'hA4);                    // CMP B,A     ->  1 > -1 (N==V)
        poke(8'h0B,8'hD5); poke(8'h0C,8'h0F); // JGE 0x0F
        poke(8'h0D,8'h10); poke(8'h0E,8'h7F); // LDI A,0x7F (no debe ejecutarse)
        poke(8'h0F,8'hE0);                    // OUT A       -> 0xFF
        poke(8'h10,8'hF0);                    // HLT
        arranca; corre(2000);
        chknout(2); chkout(0,8'h01); chkout(1,8'hFF);

        // J) E/S portada: IN n,rd y OUT n,rd (in_data = 0x12)
        limpia_mem;
        in_data = 8'h12;
        poke(8'h00,8'hF9); poke(8'h01,8'h06); // IN 2, B   -> B = in_data = 0x12
        poke(8'h02,8'hF8); poke(8'h03,8'h07); // OUT 3, B  -> puerto 3, 0x12
        poke(8'h04,8'h10); poke(8'h05,8'hAB); // LDI A,0xAB
        poke(8'h06,8'hE0);                    // OUT A     -> puerto 0, 0xAB
        poke(8'h07,8'hF0);                    // HLT
        arranca; corre(2000);
        chknout(2);
        chkout(0,8'h12); chkport(0,2'd3);
        chkout(1,8'hAB); chkport(1,2'd0);
        in_data = 8'h00;

        if (errors == 0) $display("CPU_DIRECTED: TODOS LOS TESTS PASARON");
        else             $display("CPU_DIRECTED: %0d FALLOS", errors);
        if (errors != 0) $fatal(1, "CPU_DIRECTED: hay fallos, revisa arriba");
        $finish;
    end

endmodule

`default_nettype wire
