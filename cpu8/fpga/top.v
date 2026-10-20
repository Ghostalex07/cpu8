`timescale 1ns/1ps
`default_nettype none
// ============================================================================
//  top.v - FPGA implementation (Phase 7.6) for the iCEstick (iCE40HX1K, TQ144)
//
//  It is the "board": it instantiates the CPU, generates the power-on reset from
//  the clock, shows the 5 least significant OUT outputs on the 5 LEDs and wires
//  the 8 data pins of the Pmod connector to the CPU input bus (`in_data`). The
//  iCEstick has no user switches, so `IN` reads that byte.
//
//  The program is loaded into the CPU RAM at synthesis time: ram.v includes a
//  $readmemh("fpga/program.hex") under `ifdef RAM_INIT` (the Makefile defines it).
// ============================================================================
module top (
    input  wire       clk,        // 12 MHz clock (pin 21 on the iCEstick)
    input  wire [7:0] pmod_in,    // Pmod data pins: CPU input bus (see the PCF)
    output wire [4:0] led         // 5 LEDs (D1..D5)
);

    // Power-on reset: rst=1 during the first 8 cycles after start-up.
    reg [3:0] por = 4'd0;
    wire rst = ~por[3];

    always @(posedge clk)
        if (por != 4'hF) por <= por + 4'd1;

    // The Pmod pins are asynchronous: two flip-flops resynchronize them to clk.
    // The PCF enables the internal pull-ups, so an unconnected bus reads 0xFF.
    reg [7:0] in_meta = 8'hFF;
    reg [7:0] in_sync = 8'hFF;

    always @(posedge clk) begin
        in_meta <= pmod_in;
        in_sync <= in_meta;
    end

    // The CPU (no interrupts in this demo).
    wire        halted;
    wire        out_valid;
    wire [7:0]  out_data;
    wire [1:0]  in_port;

    cpu #(.IRQ_VECTOR(8'h08)) cpu_i (
        .clk(clk),
        .rst(rst),
        .irq(1'b0),
        .halted(halted),
        .out_data(out_data),
        .out_valid(out_valid),
        .in_data(in_sync),
        .in_port(in_port)
    );

    // The 5 LEDs show the low bits of the last value sent by OUT.
    // If the CPU has stopped (HLT), they all turn on.
    assign led = halted ? 5'b11111 : out_data[4:0];

endmodule

`default_nettype wire
