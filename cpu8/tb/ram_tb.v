// ============================================================================
//  ram_tb.v - Testbench de la RAM
//
//  Comprueba:
//    1) La carga con $readmemh deja los valores del .hex en memoria.
//    2) Escritura síncrona + lectura registrada (en flanco de bajada) en varias
//       direcciones.
//    3) Reescritura de una posición previamente cargada por $readmemh.
//    4) `we=0` no modifica la memoria.
//
//  La lectura es registrada en el flanco de BAJADA (mem[addr] -> rdata), de modo
//  que el dato queda disponible a mitad de ciclo para el datapath, que registra
//  en el flanco de subida.  Por eso `chk` espera al flanco de bajada antes de
//  comprobar rdata.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module ram_tb;

    reg clk = 0, we = 0;
    reg [7:0] addr = 0, wdata = 0;
    wire [7:0] rdata;

    integer errors = 0;

    ram dut (
        .clk(clk), .we(we), .addr(addr), .wdata(wdata), .rdata(rdata)
    );

    always #5 clk = ~clk;

    // Lee la dirección `a` (espera al flanco de bajada: lectura registrada) y
    // compara con lo esperado.
    task chk;
        input [7:0] a;
        input [7:0] exp;
        begin
            addr = a; @(negedge clk); #1;
            if (rdata !== exp) begin
                errors = errors + 1;
                $display("  FALLO RAM[%02h]=%02h (esperado %02h)", a, rdata, exp);
            end
        end
    endtask

    // Escribe `d` en la dirección `a` durante un ciclo.
    task wr;
        input [7:0] a;
        input [7:0] d;
        begin
            we = 1; addr = a; wdata = d; @(posedge clk); #1; we = 0;
        end
    endtask

    initial begin
        $display("=== Testbench de la RAM ===");

        // 1) Carga con $readmemh (acceso jerárquico a la memoria interna).
        //    Indicamos el rango [0:7] para no avisar de que el .hex tiene
        //    menos de 256 palabras.
        $readmemh("tb/ram_init.hex", dut.mem, 0, 7);
        chk(8'h00, 8'hA5);
        chk(8'h01, 8'h5A);
        chk(8'h02, 8'h00);
        chk(8'h03, 8'hFF);
        chk(8'h04, 8'h12);
        chk(8'h07, 8'h78);

        // 2) Escritura síncrona y lectura registrada.
        wr(8'h10, 8'hDE);
        chk(8'h10, 8'hDE);
        wr(8'hFF, 8'h42);
        chk(8'hFF, 8'h42);

        // 3) Reescritura de una posición cargada por $readmemh.
        wr(8'h00, 8'h11);
        chk(8'h00, 8'h11);

        // 4) we=0 no debe cambiar nada.
        we = 0; addr = 8'h10; wdata = 8'h00; @(posedge clk); #1;
        chk(8'h10, 8'hDE);

        if (errors == 0)
            $display("RAM: TODOS LOS TESTS PASARON");
        else
            $display("RAM: %0d FALLOS", errors);

        if (errors != 0) $fatal(1, "RAM: hay fallos, revisa arriba");
        $finish;
    end

endmodule

`default_nettype wire
