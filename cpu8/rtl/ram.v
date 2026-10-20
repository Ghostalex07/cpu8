// ============================================================================
//  ram.v - Data/program memory (von Neumann) of 256 x 8 bits
//
//  A single port:
//    - SYNCHRONOUS WRITE (on the rising edge and only if `we` = 1).
//    - READ registered on the FALLING edge: the data appears mid-cycle
//      and is available to the datapath (which registers on the rising edge)
//      before the next posedge.  It is transparent for the CPU (it sees the data
//      in the same cycle in which it addresses), but it allows the memory to be
//      mapped to the iCE40 BRAMs (SB_RAM40_4K), which have their own read clock,
//      instead of using distributed logic (see fpga, Phase 7.6).
//
//  The memory is initialized with `$readmemh("file.hex", ram.mem)`, which loads
//  one byte per line (the format our assembler will generate). It has no reset:
//  the content is whatever $readmemh loads (or undefined if not loaded).  The
//  synchronous write is inhibited while `rst` is high, so a reset that lands in
//  the middle of a ST/PUSH/CALL cycle cannot commit the store.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module ram (
    input  wire       clk,    // system clock
    input  wire       rst,    // reset (inhibits writes, keeps the contents)
    input  wire       we,     // write enable (active high)
    input  wire [7:0] addr,   // address (0..255)
    input  wire [7:0] wdata,  // data to write
    output reg  [7:0] rdata   // read data (registered on the falling edge)
);

  // 256 locations of 8 bits (one SB_RAM40_4K on the iCE40).
  reg [7:0] mem[0:255];

`ifdef RAM_INIT
  // Initialization ONLY for FPGA synthesis (Phase 7.6): loads the program
  // from "fpga/program.hex".  In iverilog and Verilator RAM_INIT is NOT defined,
  // so the testbench loads the RAM as usual.
  initial $readmemh("fpga/program.hex", mem);
`endif

  // Synchronous write, inhibited during reset (see the header comment).
  always @(posedge clk) begin
    if (we && !rst) mem[addr] <= wdata;
  end

  // Read registered on the falling edge (half a cycle of latency): the
  // datapath registers on the posedge, so it sees mem[addr] in the same cycle.
  always @(negedge clk) begin
    rdata <= mem[addr];
  end

endmodule

`default_nettype wire
