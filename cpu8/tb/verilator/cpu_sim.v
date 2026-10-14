`timescale 1ns/1ps
`default_nettype none
// ============================================================================
//  cpu_sim.v - envoltorio SOLO para Verilator (Fase 7.6)
//
//  Instancia la CPU y carga el programa en su RAM desde el fichero indicado
//  con +hex=<ruta> (via $readmemh).  El reloj, el reset y la senal irq los
//  controla el banco de pruebas en C++ (tb/verilator/sim_main.cpp).
//
//  No forma parte del diseno sintetizable: es solo la "placa" de simulacion.
// ============================================================================
module cpu_sim #(
    parameter [7:0] IRQ_VECTOR = 8'h10   // direccion del manejador de IRQ
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       irq,
    output wire       halted,
    output wire [7:0] out_data,
    output wire       out_valid
);

    wire [1:0] in_port;
    wire [1:0] out_port;

    cpu #(.IRQ_VECTOR(IRQ_VECTOR)) dut (
        .clk(clk),
        .rst(rst),
        .irq(irq),
        .halted(halted),
        .out_data(out_data),
        .out_valid(out_valid),
        .in_data(8'h10 + {6'b0, in_port}),
        .in_port(in_port),
        .out_port(out_port)
    );

    // Ruta del fichero .hex con el programa (llega como +hex=<ruta>).
    reg [8*256-1:0] hexfile;

    initial begin
        if (!$value$plusargs("hex=%s", hexfile))
            hexfile = "programs/fase4.hex";
        $readmemh(hexfile, dut.u_ram.mem);
    end
endmodule

`default_nettype wire
