// ============================================================================
//  regfile_tb.v - Testbench del banco de registros
//
//  Comprueba:
//    1) El reset síncrono deja los cuatro registros a 0.
//    2) Escritura y lectura de cada registro.
//    3) `we=0` no modifica ningún registro.
//    4) Los dos puertos de lectura son independientes.
//    5) Escribir y leer el mismo registro en el mismo ciclo: antes del flanco
//       se lee el valor viejo, después el nuevo.
//    6) Un segundo reset vuelve a limpiar todo.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module regfile_tb;

    reg clk = 0;
    reg rst = 0, we = 0;
    reg [1:0] waddr = 0, raddr1 = 0, raddr2 = 0;
    reg [7:0] wdata = 0;
    wire [7:0] rdata1, rdata2;

    integer errors = 0;

    regfile dut (
        .clk(clk), .rst(rst), .we(we), .waddr(waddr), .wdata(wdata),
        .raddr1(raddr1), .raddr2(raddr2), .rdata1(rdata1), .rdata2(rdata2)
    );

    // Reloj de 10 ns (flanco de subida cada 5 ns).
    always #5 clk = ~clk;

    // Aplica un reset síncrono de un ciclo.
    task do_reset;
        begin
            rst = 1; @(posedge clk); #1; rst = 0;
        end
    endtask

    // Escribe `val` en el registro `idx` durante un ciclo.
    task wr;
        input [1:0] idx;
        input [7:0] val;
        begin
            we = 1; waddr = idx; wdata = val; @(posedge clk); #1; we = 0;
        end
    endtask

    // Lee el puerto 1 y compara con lo esperado.
    task chk1;
        input [1:0] idx;
        input [7:0] exp;
        begin
            raddr1 = idx; #1;
            if (rdata1 !== exp) begin
                errors = errors + 1;
                $display("  FALLO rdata1[R%0d]=%02h (esperado %02h)", idx, rdata1, exp);
            end
        end
    endtask

    // Lee el puerto 2 y compara con lo esperado.
    task chk2;
        input [1:0] idx;
        input [7:0] exp;
        begin
            raddr2 = idx; #1;
            if (rdata2 !== exp) begin
                errors = errors + 1;
                $display("  FALLO rdata2[R%0d]=%02h (esperado %02h)", idx, rdata2, exp);
            end
        end
    endtask

    initial begin
        $display("=== Testbench del banco de registros ===");

        // 1) Reset: todo a 0.
        do_reset;
        chk1(2'd0, 8'h00); chk1(2'd1, 8'h00); chk1(2'd2, 8'h00); chk1(2'd3, 8'h00);

        // 2) Escritura y lectura de cada registro.
        wr(2'd0, 8'h11);
        wr(2'd1, 8'h22);
        wr(2'd2, 8'h33);
        wr(2'd3, 8'h44);
        chk1(2'd0, 8'h11); chk1(2'd1, 8'h22); chk1(2'd2, 8'h33); chk1(2'd3, 8'h44);

        // 3) we=0 no debe cambiar nada (intento escribir A=0xFF).
        we = 0; waddr = 2'd0; wdata = 8'hFF; @(posedge clk); #1;
        chk1(2'd0, 8'h11);

        // 4) Los dos puertos de lectura son independientes.
        raddr1 = 2'd1; raddr2 = 2'd3; #1;
        if (rdata1 !== 8'h22) begin errors = errors + 1; $display("  FALLO puerto1=%02h", rdata1); end
        if (rdata2 !== 8'h44) begin errors = errors + 1; $display("  FALLO puerto2=%02h", rdata2); end

        // 5) Escritura y lectura del mismo registro en el mismo ciclo:
        //    antes del flanco se lee el valor viejo (0x11); tras él, el nuevo.
        raddr2 = 2'd0; we = 1; waddr = 2'd0; wdata = 8'h99; #1;
        if (rdata2 !== 8'h11) begin errors = errors + 1; $display("  FALLO valor viejo=%02h", rdata2); end
        @(posedge clk); #1; we = 0;
        chk2(2'd0, 8'h99);

        // 6) Segundo reset.
        do_reset;
        chk1(2'd0, 8'h00); chk1(2'd3, 8'h00);

        if (errors == 0)
            $display("REGFILE: TODOS LOS TESTS PASARON");
        else
            $display("REGFILE: %0d FALLOS", errors);

        if (errors != 0) $fatal(1, "REGFILE: hay fallos, revisa arriba");
        $finish;
    end

endmodule

`default_nettype wire
