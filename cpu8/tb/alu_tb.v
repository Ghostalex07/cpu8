// ============================================================================
//  alu_tb.v - Testbench exhaustivo de la ALU
//
//  1) Casos dirigidos: comprobación manual de operaciones y flags (incluidos
//     los casos límite de acarreo y borrow).
//  2) Barrido exhaustivo: recorre las 256x256 parejas de operandos para ADD y
//     SUB, comparando contra un modelo "oracle" calculado en el propio testbench
//     con enteros de 32 bits (independiente de la implementación del RTL).
//
//  Si algo falla, imprime el caso, cuenta los errores y termina con $fatal
//  (para que `make test` falle de verdad).
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module alu_tb;

    // Entradas al DUT
    reg  [3:0] op;
    reg        sh;
    reg  [7:0] a, b;

    // Salidas del DUT
    wire [7:0] y;
    wire       c, v, z, n;

    integer errors = 0;
    integer i, j;
    integer isum, isub;
    reg [7:0] t;   // resultado temporal para construir oracles

    // Instancia del módulo bajo prueba
    alu dut (
        .op(op), .sh(sh), .a(a), .b(b),
        .y(y), .c(c), .v(v), .z(z), .n(n)
    );

    // ------------------------------------------------------------------
    // Tarea de comprobación: aplica op/sh/a/b, espera 1 ns y compara TODO.
    // ------------------------------------------------------------------
    task check;
        input [3:0] top;
        input       tsh;
        input [7:0] va, vb;
        input [7:0] ey;
        input       ec, ez, en;
        begin
            op = top; sh = tsh; a = va; b = vb; #1;
            if ((y !== ey) || (c !== ec) || (z !== ez) || (n !== en)) begin
                errors = errors + 1;
                $display("  FALLO op=%0d sh=%b a=%02h b=%02h -> y=%02h c=%b z=%b n=%b  (esperado y=%02h c=%b z=%b n=%b)",
                         top, tsh, va, vb, y, c, z, n, ey, ec, ez, en);
            end
        end
    endtask

    // Tarea de comprobación que además verifica el flag V (desbordamiento con
    // signo).  Se usa en los casos aritméticos (ADD/SUB/CMP).
    task check_v;
        input [3:0] top;
        input       tsh;
        input [7:0] va, vb;
        input [7:0] ey;
        input       ec, ez, en, ev;
        begin
            op = top; sh = tsh; a = va; b = vb; #1;
            if ((y !== ey) || (c !== ec) || (z !== ez) || (n !== en) || (v !== ev)) begin
                errors = errors + 1;
                $display("  FALLO op=%0d sh=%b a=%02h b=%02h -> y=%02h c=%b v=%b z=%b n=%b  (esperado y=%02h c=%b v=%b z=%b n=%b)",
                         top, tsh, va, vb, y, c, v, z, n, ey, ec, ev, ez, en);
            end
        end
    endtask

    initial begin
        $display("=== Testbench de la ALU ===");

        // ------------------------------------------------------------
        // 1) Casos dirigidos
        // ------------------------------------------------------------
        $display("-- ADD --");
        check(4'h5, 0, 8'h05, 8'h03, 8'h08, 1'b0, 1'b0, 1'b0); // 5+3=8
        check(4'h5, 0, 8'hFF, 8'h01, 8'h00, 1'b1, 1'b1, 1'b0); // 255+1=0, C=1, Z=1
        check(4'h5, 0, 8'h7F, 8'h01, 8'h80, 1'b0, 1'b0, 1'b1); // 127+1=128, N=1
        check(4'h5, 0, 8'h80, 8'h80, 8'h00, 1'b1, 1'b1, 1'b0); // 128+128=0, C=1
        check(4'h5, 0, 8'h00, 8'h00, 8'h00, 1'b0, 1'b1, 1'b0); // 0+0=0, Z=1

        $display("-- Flag V (desbordamiento con signo, Ca2) --");
        check_v(4'h5, 0, 8'h7F, 8'h01, 8'h80, 1'b0, 1'b0, 1'b1, 1'b1); //  127 +  1 = -128 -> V=1
        check_v(4'h5, 0, 8'hFF, 8'h02, 8'h01, 1'b1, 1'b0, 1'b0, 1'b0); //   -1 +  2 =    1 -> V=0
        check_v(4'h5, 0, 8'h80, 8'hFF, 8'h7F, 1'b1, 1'b0, 1'b0, 1'b1); // -128 + -1 =  127 -> V=1
        check_v(4'h5, 0, 8'hC0, 8'hC0, 8'h80, 1'b1, 1'b0, 1'b1, 1'b0); //  -64 + -64 = -128 -> V=0
        check_v(4'h6, 0, 8'h80, 8'h01, 8'h7F, 1'b1, 1'b0, 1'b0, 1'b1); // -128 -  1 =  127 -> V=1
        check_v(4'h6, 0, 8'h7F, 8'hFF, 8'h80, 1'b0, 1'b0, 1'b1, 1'b1); //  127 - -1 = -128 -> V=1
        check_v(4'h6, 0, 8'h05, 8'h03, 8'h02, 1'b1, 1'b0, 1'b0, 1'b0); //    5 -  3 =    2 -> V=0
        check_v(4'hA, 0, 8'h80, 8'h01, 8'h7F, 1'b1, 1'b0, 1'b0, 1'b1); // CMP -128,1 -> V=1

        $display("-- SUB / CMP (C=1 => no borrow, a>=b) --");
        check(4'h6, 0, 8'h05, 8'h03, 8'h02, 1'b1, 1'b0, 1'b0); // 5-3=2,  no borrow
        check(4'h6, 0, 8'h03, 8'h05, 8'hFE, 1'b0, 1'b0, 1'b1); // 3-5=-2, borrow
        check(4'h6, 0, 8'h05, 8'h05, 8'h00, 1'b1, 1'b1, 1'b0); // 5-5=0,  no borrow, Z=1
        check(4'h6, 0, 8'h00, 8'h01, 8'hFF, 1'b0, 1'b0, 1'b1); // 0-1=-1, borrow
        check(4'hA, 0, 8'h03, 8'h05, 8'hFE, 1'b0, 1'b0, 1'b1); // CMP da el diff y flags
        check(4'hA, 0, 8'h07, 8'h07, 8'h00, 1'b1, 1'b1, 1'b0);

        $display("-- AND / OR / XOR (C=0) --");
        check(4'h7, 0, 8'hF0, 8'h0F, 8'h00, 1'b0, 1'b1, 1'b0);
        check(4'h7, 0, 8'hFF, 8'h80, 8'h80, 1'b0, 1'b0, 1'b1);
        check(4'h8, 0, 8'hF0, 8'h0F, 8'hFF, 1'b0, 1'b0, 1'b1);
        check(4'h8, 0, 8'h00, 8'h00, 8'h00, 1'b0, 1'b1, 1'b0);
        check(4'h9, 0, 8'hFF, 8'hFF, 8'h00, 1'b0, 1'b1, 1'b0);
        check(4'h9, 0, 8'hAA, 8'h55, 8'hFF, 1'b0, 1'b0, 1'b1);

        $display("-- SHL (C = bit7 previo) --");
        check(4'hB, 0, 8'h81, 8'h00, 8'h02, 1'b1, 1'b0, 1'b0); // 1000_0001 -> 0000_0010, C=1
        check(4'hB, 0, 8'h40, 8'h00, 8'h80, 1'b0, 1'b0, 1'b1); // 0100_0000 -> 1000_0000
        check(4'hB, 0, 8'h80, 8'h00, 8'h00, 1'b1, 1'b1, 1'b0); // 1000_0000 -> 0000_0000, C=1, Z=1
        check(4'hB, 0, 8'h00, 8'h00, 8'h00, 1'b0, 1'b1, 1'b0);

        $display("-- SHR (C = bit0 previo) --");
        check(4'hB, 1, 8'h01, 8'h00, 8'h00, 1'b1, 1'b1, 1'b0); // 0000_0001 -> 0000_0000, C=1, Z=1
        check(4'hB, 1, 8'h80, 8'h00, 8'h40, 1'b0, 1'b0, 1'b0); // 1000_0000 -> 0100_0000
        check(4'hB, 1, 8'hFF, 8'h00, 8'h7F, 1'b1, 1'b0, 1'b0); // 1111_1111 -> 0111_1111, C=1
        check(4'hB, 1, 8'h02, 8'h00, 8'h01, 1'b0, 1'b0, 1'b0);

        // ------------------------------------------------------------
        // 2) Barrido exhaustivo con oracle independiente
        //    (oracle calculado en el testbench, ajeno a la implementación)
        // ------------------------------------------------------------
        $display("-- Barrido exhaustivo ADD / SUB / CMP (65536 parejas) --");
        for (i = 0; i < 256; i = i + 1) begin
            for (j = 0; j < 256; j = j + 1) begin
                isum = i + j;                       // oracle ADD (32 bits)
                // C = carry-out del bit 7 de a+b  <=>  isum >= 256  <=>  isum[8]
                // V = desbordamiento con signo: signos iguales y resultado distinto.
                check_v(4'h5, 0, i[7:0], j[7:0],
                      isum[7:0], isum[8], (isum[7:0] == 0), isum[7],
                      ((i[7] == j[7]) && (isum[7] != i[7])));

                isub = i - j;                       // oracle SUB / CMP
                // C = 1 si NO hay borrow (a>=b) = carry-out de a+~b+1
                // V = desbordamiento con signo: signos distintos y resultado != a.
                check_v(4'h6, 0, i[7:0], j[7:0],
                      isub[7:0], (i >= j), (isub[7:0] == 0), isub[7],
                      ((i[7] != j[7]) && (isub[7] != i[7])));
                check_v(4'hA, 0, i[7:0], j[7:0],     // CMP: mismo diff y flags
                      isub[7:0], (i >= j), (isub[7:0] == 0), isub[7],
                      ((i[7] != j[7]) && (isub[7] != i[7])));
            end
        end

        $display("-- Barrido exhaustivo AND / OR / XOR (65536 parejas) --");
        for (i = 0; i < 256; i = i + 1) begin
            for (j = 0; j < 256; j = j + 1) begin
                // Oracle bit a bit (operadores de Verilog, independientes de la ALU)
                t = i[7:0] & j[7:0];
                check(4'h7, 0, i[7:0], j[7:0], t, 1'b0, (t == 0), t[7]);
                t = i[7:0] | j[7:0];
                check(4'h8, 0, i[7:0], j[7:0], t, 1'b0, (t == 0), t[7]);
                t = i[7:0] ^ j[7:0];
                check(4'h9, 0, i[7:0], j[7:0], t, 1'b0, (t == 0), t[7]);
            end
        end

        $display("-- Barrido exhaustivo SHL / SHR (256 valores) --");
        for (i = 0; i < 256; i = i + 1) begin
            t = i[7:0] << 1;            // SHL truncado a 8 bits: C = bit7 previo
            check(4'hB, 0, i[7:0], 8'h00, t, i[7], (t == 0), t[7]);
            t = i[7:0] >> 1;            // SHR: C = bit0 previo
            check(4'hB, 1, i[7:0], 8'h00, t, i[0], (t == 0), t[7]);
        end

        // ------------------------------------------------------------
        // MUL / DIV (Fase 9).  V no interviene (siempre 0).
        // ------------------------------------------------------------
        $display("-- MUL (dirigidos) --");
        check_v(4'hC, 0, 8'h07, 8'h06, 8'h2A, 1'b0, 1'b0, 1'b0, 1'b0); // 7*6=42
        check_v(4'hC, 0, 8'h14, 8'h14, 8'h90, 1'b1, 1'b0, 1'b1, 1'b0); // 20*20=400 -> 0x90, C=1
        check_v(4'hC, 0, 8'h00, 8'h07, 8'h00, 1'b0, 1'b1, 1'b0, 1'b0); // 0*7=0, Z=1
        check_v(4'hC, 0, 8'hFF, 8'hFF, 8'h01, 1'b1, 1'b0, 1'b0, 1'b0); // 255*255=65025 -> 0x01, C=1

        $display("-- DIV (dirigidos) --");
        check_v(4'hD, 0, 8'hC8, 8'h07, 8'h1C, 1'b0, 1'b0, 1'b0, 1'b0); // 200/7=28
        check_v(4'hD, 0, 8'h64, 8'h03, 8'h21, 1'b0, 1'b0, 1'b0, 1'b0); // 100/3=33
        check_v(4'hD, 0, 8'h09, 8'h00, 8'h00, 1'b1, 1'b1, 1'b0, 1'b0); // 9/0 -> 0, C=1
        check_v(4'hD, 0, 8'h05, 8'h08, 8'h00, 1'b0, 1'b1, 1'b0, 1'b0); // 5/8=0, Z=1

        $display("-- Barrido exhaustivo MUL (65536 parejas) --");
        for (i = 0; i < 256; i = i + 1) begin
            for (j = 0; j < 256; j = j + 1) begin
                t = (i * j) & 8'hFF;   // producto truncado a 8 bits
                check_v(4'hC, 0, i[7:0], j[7:0],
                        t, ((i * j) > 255), (t == 0), t[7], 1'b0);
            end
        end

        $display("-- Barrido exhaustivo DIV (65536 parejas) --");
        for (i = 0; i < 256; i = i + 1) begin
            for (j = 0; j < 256; j = j + 1) begin
                if (j == 0) t = 8'h00;         // division por cero -> 0
                else        t = (i / j) & 8'hFF;
                check_v(4'hD, 0, i[7:0], j[7:0],
                        t, (j == 0), (t == 0), t[7], 1'b0);
            end
        end

        // ------------------------------------------------------------
        // Resumen
        // ------------------------------------------------------------
        if (errors == 0)
            $display("ALU: TODOS LOS TESTS PASARON");
        else
            $display("ALU: %0d FALLOS", errors);

        if (errors != 0) $fatal(1, "ALU: hay fallos, revisa arriba");
        $finish;
    end

endmodule

`default_nettype wire
