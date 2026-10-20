// ============================================================================
//  flag_i_tb.v - Directed test for the interrupt-enable flag I
//
//  Checks the two paths that the differential fuzz does not compare:
//    - DI clears I: a level-high IRQ raised afterwards stays pending;
//    - POPF restores I from bit 4 of the popped flags byte, so the pending
//      IRQ is taken immediately afterwards.
//
//  The program is embedded in the testbench (no .hex or .ref needed):
//    0x00  EI
//    0x01  DI              ; I = 0 before the IRQ is raised
//    0x02  LDI A, 1
//    0x04  OUT A           -> 1; the testbench raises irq here
//    0x05  NOP             ; must NOT take the IRQ (DI worked)
//    0x06  LDI A, 2
//    0x08  OUT A           -> 2
//    0x09  LDI A, 0x10
//    0x0B  PUSH A          ; RAM[0xF0] = 0x10 (I = 1), SP = 0xEF
//    0x0C  JMP 0x20
//    0x20  POPF            ; SP = 0xF0, flags <- RAM[0xF0] -> I = 1
//    0x22  NOP
//    0x23  NOP
//    0x24  HLT             ; reached only if POPF did not enable interrupts
//    0x30  LDI A, 0xFF     ; IRQ vector -> OUT 0xFF
//    0x32  OUT A
//    0x33  HLT
//
//  Expected OUT sequence: 1, 2, 0xFF.  If DI fails the sequence is 1, 0xFF;
//  if POPF fails it is 1, 2.  Both are reported as failures.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module flag_i_tb;

  reg clk = 0, rst = 1;
  reg irq = 0;

  wire halted, out_valid;
  wire [7:0] out_data;
  wire [1:0] in_port;

  cpu #(
      .IRQ_VECTOR(8'h30)
  ) dut (
      .clk(clk),
      .rst(rst),
      .irq(irq),
      .halted(halted),
      .out_data(out_data),
      .out_valid(out_valid),
      .in_data(8'h00),
      .in_port(in_port)
  );

  always #5 clk = ~clk;

  reg [7:0] outv[0:15];
  reg [7:0] expected[0:2];
  integer nout = 0, errors = 0, i, k;

  initial begin
    $dumpfile("build/flag_i_tb.vcd");
    $dumpvars(0, flag_i_tb);

    // Deterministic RAM, including the bytes not covered by the program.
    for (i = 0; i < 256; i = i + 1) dut.u_ram.mem[i] = 8'h00;

    dut.u_ram.mem[8'h00] = 8'hF2;  // EI
    dut.u_ram.mem[8'h01] = 8'hF3;  // DI
    dut.u_ram.mem[8'h02] = 8'h10;  // LDI A, 1
    dut.u_ram.mem[8'h03] = 8'h01;
    dut.u_ram.mem[8'h04] = 8'hE0;  // OUT A
    dut.u_ram.mem[8'h05] = 8'h20;  // NOP
    dut.u_ram.mem[8'h06] = 8'h10;  // LDI A, 2
    dut.u_ram.mem[8'h07] = 8'h02;
    dut.u_ram.mem[8'h08] = 8'hE0;  // OUT A
    dut.u_ram.mem[8'h09] = 8'h10;  // LDI A, 0x10
    dut.u_ram.mem[8'h0A] = 8'h10;
    dut.u_ram.mem[8'h0B] = 8'h08;  // PUSH A
    dut.u_ram.mem[8'h0C] = 8'hC0;  // JMP 0x20
    dut.u_ram.mem[8'h0D] = 8'h20;
    for (k = 8'h0E; k <= 8'h1F; k = k + 1) dut.u_ram.mem[k] = 8'h20;  // NOP padding
    dut.u_ram.mem[8'h20] = 8'hFA;  // POPF
    dut.u_ram.mem[8'h21] = 8'hB0;
    dut.u_ram.mem[8'h22] = 8'h20;  // NOP
    dut.u_ram.mem[8'h23] = 8'h20;  // NOP
    dut.u_ram.mem[8'h24] = 8'hF0;  // HLT
    dut.u_ram.mem[8'h30] = 8'h10;  // LDI A, 0xFF (IRQ handler)
    dut.u_ram.mem[8'h31] = 8'hFF;
    dut.u_ram.mem[8'h32] = 8'hE0;  // OUT A
    dut.u_ram.mem[8'h33] = 8'hF0;  // HLT

    expected[0] = 8'd1;
    expected[1] = 8'd2;
    expected[2] = 8'd255;

    $display("=== I-flag simulation (DI + POPF) ===");

    // Synchronous reset; irq stays low until the program has executed DI and
    // emitted its first byte (see the output monitor below).
    rst = 1;
    repeat (2) @(posedge clk);
    @(negedge clk) rst = 0;

    i = 0;
    while (!halted && i < 500000) begin
      @(posedge clk);
      #1;
      if (out_valid) begin
        if (nout < 16) outv[nout] = out_data;
        $display("  OUT[%0d] = %0d", nout, out_data);
        if (nout == 0) irq = 1;  // DI has already run: the IRQ must stay pending
        nout = nout + 1;
      end
      i = i + 1;
    end

    if (!halted) begin
      $display("  FAIL: the CPU did not reach HLT (possible infinite loop)");
      errors = errors + 1;
    end

    if (nout !== 3) begin
      $display("  FAIL: %0d outputs, expected 3", nout);
      errors = errors + 1;
    end else begin
      for (i = 0; i < 3; i = i + 1) begin
        if (outv[i] !== expected[i]) begin
          $display("  FAIL: OUT[%0d] = %0d, expected %0d", i, outv[i], expected[i]);
          errors = errors + 1;
        end
      end
    end

    if (errors == 0) $display("FLAG_I: ALL TESTS PASSED");
    else $display("FLAG_I: %0d FAILURES", errors);

    if (errors != 0) $fatal(1, "FLAG_I: there are failures, check above");
    $finish;
  end

endmodule

`default_nettype wire
