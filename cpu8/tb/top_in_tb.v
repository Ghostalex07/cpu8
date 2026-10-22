`timescale 1ns / 1ps
`default_nettype none
// ============================================================================
//  top_in_tb.v - input-port handshake test at the FPGA top level
//
//  The testbench models a peripheral whose data depends on the port that the
//  CPU is currently selecting: pmod_in is a combinational function of
//  dut.in_port.  This is the worst case for the two-FF synchronizer in
//  fpga/top.v: the selected port must be stable for at least two clock edges
//  before the CPU samples in_data.
//
//  Program: IN 2,A -> OUT A -> IN 3,B -> OUT 3,B -> HLT.
//  The old one-cycle handshake returned the value of the previous port (0)
//  instead of 2 and 3; with the S_IN wait state it must return A2 and A3.
// ============================================================================
module top_in_tb;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  // Combinational peripheral: port n presents 0xA0 | n.
  reg [7:0] pmod_in;
  always @(*) pmod_in = 8'hA0 | {6'b0, dut.in_port};

  wire [4:0] led;

  top dut (
      .clk(clk),
      .pmod_in(pmod_in),
      .led(led)
  );

  integer errors = 0;
  integer k;

  initial begin
    for (k = 0; k < 256; k = k + 1) dut.cpu_i.u_ram.mem[k] = 8'h00;
    dut.cpu_i.u_ram.mem[0] = 8'hF9;  // IN 2,A
    dut.cpu_i.u_ram.mem[1] = 8'h02;
    dut.cpu_i.u_ram.mem[2] = 8'hE0;  // OUT A
    dut.cpu_i.u_ram.mem[3] = 8'hF9;  // IN 3,B
    dut.cpu_i.u_ram.mem[4] = 8'h07;
    dut.cpu_i.u_ram.mem[5] = 8'hF8;  // OUT 3,B
    dut.cpu_i.u_ram.mem[6] = 8'h07;
    dut.cpu_i.u_ram.mem[7] = 8'hF0;  // HLT

    wait (dut.rst == 1'b0);
    repeat (40) @(posedge clk);
    #1;

    if (!dut.halted) begin
      $display("  FAIL: the CPU did not reach HLT");
      errors = errors + 1;
    end
    if (dut.cpu_i.u_rf.regs[0] !== 8'hA2) begin
      $display("  FAIL: IN 2,A -> A=%02X, expected A2", dut.cpu_i.u_rf.regs[0]);
      errors = errors + 1;
    end
    if (dut.cpu_i.u_rf.regs[1] !== 8'hA3) begin
      $display("  FAIL: IN 3,B -> B=%02X, expected A3", dut.cpu_i.u_rf.regs[1]);
      errors = errors + 1;
    end
    if (dut.out_data !== 8'hA3) begin
      $display("  FAIL: last OUT=%02X, expected A3", dut.out_data);
      errors = errors + 1;
    end
    if (dut.led !== 5'b11111) begin
      $display("  FAIL: LED=%02X, expected all on after HLT", dut.led);
      errors = errors + 1;
    end

    if (errors == 0) $display("TOP IN: ALL TESTS PASSED");
    else $display("TOP IN: %0d FAILURES", errors);

    if (errors != 0) $fatal(1, "TOP IN: there are failures, check above");
    $finish;
  end

endmodule

`default_nettype wire
