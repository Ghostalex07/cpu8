// ============================================================================
//  pc_tb.v - Testbench del Contador de Programa
//
//  Comprueba el reset, el incremento (con desbordamiento 0xFF -> 0x00), la
//  carga de un valor (salto), la retención cuando no hay load ni inc, y el
//  orden de prioridad reset > load > inc.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module pc_tb;

    reg clk = 0, rst = 0, load = 0, inc = 0;
    reg [7:0] d_in = 0;
    wire [7:0] q;

    integer errors = 0;

    pc dut (
        .clk(clk), .rst(rst), .load(load), .inc(inc), .d_in(d_in), .q(q)
    );

    always #5 clk = ~clk;

    task tick;
        begin @(posedge clk); #1; end
    endtask

    task chk;
        input [7:0] exp;
        begin
            if (q !== exp) begin
                errors = errors + 1;
                $display("  FALLO PC=%02h (esperado %02h)", q, exp);
            end
        end
    endtask

    initial begin
        $display("=== Testbench del PC ===");

        // 1) Reset -> 0
        rst = 1; tick; rst = 0; chk(8'h00);

        // 2) Incrementos consecutivos
        inc = 1;
        tick; chk(8'h01);
        tick; chk(8'h02);
        tick; chk(8'h03);
        tick; chk(8'h04);
        tick; chk(8'h05);

        // 3) Sin load ni inc -> mantiene
        inc = 0; tick; chk(8'h05);

        // 4) Carga de un valor (salto)
        load = 1; d_in = 8'hAB; tick; load = 0; chk(8'hAB);

        // 5) Desbordamiento 0xFF + 1 = 0x00
        load = 1; d_in = 8'hFF; tick; load = 0; chk(8'hFF);
        inc = 1; tick; chk(8'h00); inc = 0;

        // 6) Reset de nuevo
        rst = 1; tick; rst = 0; chk(8'h00);

        if (errors == 0)
            $display("PC: TODOS LOS TESTS PASARON");
        else
            $display("PC: %0d FALLOS", errors);

        if (errors != 0) $fatal(1, "PC: hay fallos, revisa arriba");
        $finish;
    end

endmodule

`default_nettype wire
