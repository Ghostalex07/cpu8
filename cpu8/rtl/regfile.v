// ============================================================================
//  regfile.v - General-purpose register file (A, B, C, D)
//
//  Four 8-bit registers. It has:
//    - 2 synchronous WRITE ports (on the rising edge), with enables `we` and
//      `we2`.  The second one exists for SWAP rd,rs (extended instruction),
//      which exchanges two registers in a single cycle.
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
    input  wire       we,      // write enable (port 1)
    input  wire [1:0] waddr,   // index of the destination register (port 1)
    input  wire [7:0] wdata,   // data to write (port 1)
    input  wire       we2,     // write enable (port 2, SWAP rd,rs)
    input  wire [1:0] waddr2,  // index of the destination register (port 2)
    input  wire [7:0] wdata2,  // data to write (port 2)
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
    // The reset has priority over the writes.  When SWAP writes two DIFFERENT
    // registers there is no conflict; with rd==rs both ports write the same
    // (unchanged) value, which is a harmless no-op.
    always @(posedge clk) begin
        if (rst) begin
            regs[R_A] <= 8'h00;
            regs[R_B] <= 8'h00;
            regs[R_C] <= 8'h00;
            regs[R_D] <= 8'h00;
        end else begin
            if (we)  regs[waddr]  <= wdata;
            if (we2) regs[waddr2] <= wdata2;
        end
    end

    // Combinational read: the value appears as soon as the address changes.
    assign rdata1 = regs[raddr1];
    assign rdata2 = regs[raddr2];

endmodule

`default_nettype wire
