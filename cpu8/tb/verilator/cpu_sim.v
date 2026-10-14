`timescale 1ns/1ps
`default_nettype none
// ============================================================================
//  cpu_sim.v - Verilator-ONLY wrapper (Phase 7.6)
//
//  Instantiates the CPU and loads the program into its RAM from the file given
//  with +hex=<path> (via $readmemh).  The clock, the reset and the irq signal are
//  controlled by the C++ testbench (tb/verilator/sim_main.cpp).
//
//  It is not part of the synthesizable design: it is only the simulation "board".
// ============================================================================
module cpu_sim #(
    parameter [7:0] IRQ_VECTOR = 8'h10   // address of the IRQ handler
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

    // Path of the .hex file with the program (arrives as +hex=<path>).
    reg [8*256-1:0] hexfile;

    initial begin
        if (!$value$plusargs("hex=%s", hexfile))
            hexfile = "programs/fase4.hex";
        $readmemh(hexfile, dut.u_ram.mem);
    end
endmodule

`default_nettype wire
