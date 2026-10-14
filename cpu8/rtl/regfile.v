// ============================================================================
//  regfile.v - General-purpose register file (A, B, C, D)
//
//  Four 8-bit registers. It has:
//    - 1 synchronous WRITE port (on the rising edge), with enable `we`.
//    - 2 combinational READ ports, so that `rd` and `rs` can be read at the
//      same time (the ALU needs both operands in the same cycle).
//
//  The reset is SYNCHRONOUS (active high) and leaves the four registers at 0.
//
//  Register indices (match the rd/rs field of the ISA):
//    A = 00, B = 01, C = 10, D = 11
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module regfile (
    input  wire       clk,     // system clock
    input  wire       rst,     // synchronous reset, active high
    input  wire       we,      // write enable
    input  wire [1:0] waddr,   // index of the destination register
    input  wire [7:0] wdata,   // data to write
    input  wire [1:0] raddr1,  // address of read port 1 (rs)
    input  wire [1:0] raddr2,  // address of read port 2 (rd)
    output wire [7:0] rdata1,  // value of register raddr1
    output wire [7:0] rdata2   // value of register raddr2
);

    // Symbolic names of the register indices.
    localparam [1:0] R_A = 2'b00;
    localparam [1:0] R_B = 2'b01;
    localparam [1:0] R_C = 2'b10;
    localparam [1:0] R_D = 2'b11;

    // The four registers. `regs[i]` is the register with index i.
    reg [7:0] regs [0:3];

    // Write and reset, both SYNCHRONOUS (they only change on the rising edge).
    // The reset has priority over the write.
    always @(posedge clk) begin
        if (rst) begin
            regs[R_A] <= 8'h00;
            regs[R_B] <= 8'h00;
            regs[R_C] <= 8'h00;
            regs[R_D] <= 8'h00;
        end else if (we) begin
            regs[waddr] <= wdata;
        end
    end

    // Combinational read: the value appears as soon as the address changes.
    assign rdata1 = regs[raddr1];
    assign rdata2 = regs[raddr2];

endmodule

`default_nettype wire
