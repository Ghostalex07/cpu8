`timescale 1ns / 1ps
`default_nettype none
// ============================================================================
//  top_in_tb.v - input-port handshake test at the FPGA top level
//
//  The testbench models a peripheral whose data depends on the port that the
//  CPU is currently selecting: pmod_in is a combinational function of
//  dut.in_port.  This is the worst case for the two-FF synchronizer in
//  fpga/top.v: the selected port must be stable for at least two clock edges
//  before the CPU samples in_data.  Only port 0 comes from the Pmod, so the
//  other ports must NOT read that value: the test checks the port mux as well.
//
//  Program: IN A / MOV B,A / IN 1,A / MOV C,A / IN 2,A / MOV D,A /
//          IN 3,A / OUT 0,A / HLT.
//  Expected: A=0 (idle status), B=0xA0, C=0 (no byte received), D=0 (timer
//  disabled) and the last OUT on port 0 is 0.
// ============================================================================
module top_in_tb;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  // Combinational peripheral on the Pmod: port n presents 0xA0 | n on the
  // pins.  Only port 0 reads the Pmod, so the other registers must not pick
  // this value up.
  reg [7:0] pmod_in;
  always @(*) pmod_in = 8'hA0 | {6'b0, dut.in_port};

  wire       uart_tx;
  wire [4:0] led;

  top dut (
      .clk(clk),
      .pmod_in(pmod_in),
      .uart_rx(1'b1),
      .uart_tx(uart_tx),
      .led(led)
  );

  integer errors = 0;
  integer k;

  initial begin
    for (k = 0; k < 256; k = k + 1) dut.cpu_i.u_ram.mem[k] = 8'h00;
    dut.cpu_i.u_ram.mem[0]  = 8'hE1;  // IN A (port 0)
    dut.cpu_i.u_ram.mem[1]  = 8'h24;  // MOV B, A
    dut.cpu_i.u_ram.mem[2]  = 8'hF9;  // IN 1, A
    dut.cpu_i.u_ram.mem[3]  = 8'h01;
    dut.cpu_i.u_ram.mem[4]  = 8'h28;  // MOV C, A
    dut.cpu_i.u_ram.mem[5]  = 8'hF9;  // IN 2, A
    dut.cpu_i.u_ram.mem[6]  = 8'h02;
    dut.cpu_i.u_ram.mem[7]  = 8'h2C;  // MOV D, A
    dut.cpu_i.u_ram.mem[8]  = 8'hF9;  // IN 3, A
    dut.cpu_i.u_ram.mem[9]  = 8'h03;
    dut.cpu_i.u_ram.mem[10] = 8'hF8;  // OUT 0, A
    dut.cpu_i.u_ram.mem[11] = 8'h00;
    dut.cpu_i.u_ram.mem[12] = 8'hF0;  // HLT

    wait (dut.rst == 1'b0);
    repeat (40) @(posedge clk);
    #1;

    if (!dut.halted) begin
      $display("  FAIL: the CPU did not reach HLT");
      errors = errors + 1;
    end
    if (dut.cpu_i.u_rf.regs[0] !== 8'h00) begin
      $display("  FAIL: IN 3,A -> A=%02X, expected 00 (idle status)", dut.cpu_i.u_rf.regs[0]);
      errors = errors + 1;
    end
    if (dut.cpu_i.u_rf.regs[1] !== 8'hA0) begin
      $display("  FAIL: IN 0,A -> B=%02X, expected A0 (Pmod handshake)", dut.cpu_i.u_rf.regs[1]);
      errors = errors + 1;
    end
    if (dut.cpu_i.u_rf.regs[2] !== 8'h00) begin
      $display("  FAIL: IN 1,A -> C=%02X, expected 00 (no byte received)", dut.cpu_i.u_rf.regs[2]);
      errors = errors + 1;
    end
    if (dut.cpu_i.u_rf.regs[3] !== 8'h00) begin
      $display("  FAIL: IN 2,A -> D=%02X, expected 00 (timer disabled)", dut.cpu_i.u_rf.regs[3]);
      errors = errors + 1;
    end
    if (dut.out_data !== 8'h00) begin
      $display("  FAIL: last OUT=%02X, expected 00", dut.out_data);
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
