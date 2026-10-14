// ============================================================================
//  pc.v - 8-bit Program Counter
//
//  Synchronous register with three EXCLUSIVE actions, in priority order:
//    1) rst  -> PC = 0                (synchronous reset, active high)
//    2) load -> PC = d_in             (jumps: JMP / Jcc take the destination)
//    3) inc  -> PC = PC + 1           (next instruction)
//    4) (none) -> holds the value
//
//  The control unit will never enable `load` and `inc` at the same time; if it
//  did, `load` wins by this order.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module pc (
    input  wire       clk,
    input  wire       rst,
    input  wire       load,
    input  wire       inc,
    input  wire [7:0] d_in,
    output reg  [7:0] q
);

    always @(posedge clk) begin
        if (rst)        q <= 8'h00;
        else if (load)  q <= d_in;
        else if (inc)   q <= q + 8'd1;
        // otherwise it holds the value (not written => no else branch needed)
    end

endmodule

`default_nettype wire
