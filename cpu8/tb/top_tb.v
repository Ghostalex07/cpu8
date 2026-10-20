`timescale 1ns / 1ps
`default_nettype none
// ============================================================================
//  top_tb.v - FPGA top-level integration test
//
//  Checks that the Pmod input bus reaches the CPU: the program reads it with IN
//  and sends it back with OUT. The CPU must halt and the LEDs must show HLT.
// ============================================================================
module top_tb;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg  [7:0] pmod_in = 8'hA5;
  wire [4:0] led;

  top dut (
      .clk(clk),
      .pmod_in(pmod_in),
      .led(led)
  );

  integer errors = 0;
  integer k;

  initial begin
    // Deterministic RAM, then the program: IN A / OUT A / HLT.
    for (k = 0; k < 256; k = k + 1) dut.cpu_i.u_ram.mem[k] = 8'h00;
    dut.cpu_i.u_ram.mem[0] = 8'hE1;  // IN A
    dut.cpu_i.u_ram.mem[1] = 8'hE0;  // OUT A
    dut.cpu_i.u_ram.mem[2] = 8'hF0;  // HLT

    // The top-level POR releases rst after 8 cycles; then IN (3), OUT (2)
    // and HLT (1) need a handful of cycles.
    wait (dut.rst == 1'b0);
    repeat (4) @(posedge clk);
    repeat (40) @(posedge clk);

    if (!dut.halted) begin
      $display("  FAIL: the CPU did not reach HLT");
      errors = errors + 1;
    end
    if (dut.out_data !== 8'hA5) begin
      $display("  FAIL: OUT=%02X, expected A5 (IN did not read pmod_in)", dut.out_data);
      errors = errors + 1;
    end
    if (led !== 5'b11111) begin
      $display("  FAIL: LED=%02X, expected all on after HLT", led);
      errors = errors + 1;
    end

    if (errors == 0) $display("TOP: ALL TESTS PASSED");
    else $display("TOP: %0d FAILURES", errors);

    if (errors != 0) $fatal(1, "TOP: there are failures, check above");
    $finish;
  end

endmodule

`default_nettype wire
