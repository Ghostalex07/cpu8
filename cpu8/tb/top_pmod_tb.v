`timescale 1ns / 1ps
`default_nettype none
// ============================================================================
//  top_pmod_tb.v - Pmod loop demo test
//
//  Loads programs/pmod.hex (IN A / OUT A / JMP loop) into the top-level RAM
//  and changes pmod_in while the CPU keeps looping.  This checks the complete
//  path: Pmod pins -> two-FF synchronizer -> in_data -> IN -> OUT -> LEDs.
//  Unlike top_tb, the program never halts, so the testbench samples the
//  outputs after a fixed number of cycles for each input value.
// ============================================================================
module top_pmod_tb;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg  [7:0] pmod_in = 8'h00;
  wire [4:0] led;

  top dut (
      .clk(clk),
      .pmod_in(pmod_in),
      .led(led)
  );

  integer errors = 0;
  integer k;

  task check_input;
    input [7:0] value;
    begin
      pmod_in = value;
      // The synchronizer needs two cycles; the IN/OUT/JMP loop takes a few
      // more.  32 cycles leave a comfortable margin.
      repeat (32) @(posedge clk);
      #1;
      if (dut.halted) begin
        $display("  FAIL: the CPU halted on the loop program");
        errors = errors + 1;
      end
      if (dut.out_data !== value) begin
        $display("  FAIL: pmod_in=%02X -> OUT=%02X (expected %02X)", value, dut.out_data, value);
        errors = errors + 1;
      end
      if (led !== value[4:0]) begin
        $display("  FAIL: pmod_in=%02X -> LED=%02X (expected %02X)", value, led, value[4:0]);
        errors = errors + 1;
      end
      $display("  pmod_in=%02X -> OUT=%02X LED=%02X ok", value, dut.out_data, led);
    end
  endtask

  initial begin
    // Deterministic RAM, then the assembled loop program (4 bytes:
    // E1 E0 C0 00 = IN A / OUT A / JMP 0).
    for (k = 0; k < 256; k = k + 1) dut.cpu_i.u_ram.mem[k] = 8'h00;
    $readmemh("programs/pmod.hex", dut.cpu_i.u_ram.mem, 0, 3);

    // Wait for the top-level power-on reset, then let the loop settle.
    wait (dut.rst == 1'b0);
    repeat (8) @(posedge clk);

    check_input(8'h00);
    check_input(8'hFF);
    check_input(8'h55);
    check_input(8'hAA);
    check_input(8'h01);
    check_input(8'h02);
    check_input(8'h04);
    check_input(8'h08);
    check_input(8'h10);
    check_input(8'h20);
    check_input(8'h40);
    check_input(8'h80);
    check_input(8'hA5);
    check_input(8'h5A);

    if (errors == 0) $display("TOP PMOD: ALL TESTS PASSED");
    else $display("TOP PMOD: %0d FAILURES", errors);

    if (errors != 0) $fatal(1, "TOP PMOD: there are failures, check above");
    $finish;
  end

endmodule

`default_nettype wire
