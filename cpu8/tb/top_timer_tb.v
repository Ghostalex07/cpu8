`timescale 1ns / 1ps
`default_nettype none
// ============================================================================
//  top_timer_tb.v - Timer interrupt integration test
//
//  Phase 1 loads a program that arms the timer (period 2 ms), enables
//  interrupts and loops showing B on the LEDs.  The handler at 0x08 re-arms
//  the timer, increments B, re-enables interrupts and returns with RETI.  The
//  test waits for several interrupts and checks the LED counter.
//
//  Phase 2 arms the timer without enabling interrupts, waits for it to fire,
//  reads the pending flag through port 2, disables the timer with period 0 and
//  checks that the pending flag is cleared and stays low.
// ============================================================================
module top_timer_tb;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg  [7:0] pmod_in = 8'hFF;
  wire       uart_tx;
  wire [4:0] led;

  top #(
      .UART_DIV(8),
      .TIMER_TICKS_PER_MS(4)
  ) dut (
      .clk(clk),
      .pmod_in(pmod_in),
      .uart_rx(1'b1),
      .uart_tx(uart_tx),
      .led(led)
  );

  integer errors = 0;
  integer k;
  integer n;
  integer guard;
  reg [7:0] prog[0:63];
  reg saw_irq = 1'b0;
  reg saw_pending = 1'b0;
  reg saw_clear = 1'b0;
  reg [7:0] counter;
  reg matched = 1'b0;
  wire [7:0] reg_b = dut.cpu_i.u_rf.regs[1];

  always @(posedge clk) if (dut.timer_irq) saw_irq <= 1'b1;

  task load_program;
    begin
      for (k = 0; k < 256; k = k + 1) dut.cpu_i.u_ram.mem[k] = 8'h00;
      for (k = 0; k < n; k = k + 1) dut.cpu_i.u_ram.mem[k] = prog[k];
    end
  endtask

  task restart_cpu;
    begin
      repeat (2) @(posedge clk);
      dut.por = 4'h0;
      repeat (12) @(posedge clk);
      if (dut.rst !== 1'b0) begin
        $display("  FAIL: the CPU did not leave reset");
        errors = errors + 1;
      end
    end
  endtask

  initial begin
    // ---------------------------------------------------------------
    //  Phase 1: periodic interrupts (period 2 -> 8 clocks here)
    // ---------------------------------------------------------------
    n = 43;
    for (k = 0; k < 64; k = k + 1) prog[k] = 8'h00;

    prog[0]  = 8'hC0;
    prog[1]  = 8'h20;  // JMP main
    // Handler at 0x08: re-arm, B++, EI, RETI.
    prog[8]  = 8'h10;
    prog[9]  = 8'h02;  // LDI A, 2
    prog[10] = 8'hF8;
    prog[11] = 8'h02;  // OUT 2, A
    prog[12] = 8'h15;
    prog[13] = 8'h01;  // ADDI B, 1
    prog[14] = 8'hF2;  // EI
    prog[15] = 8'hFA;
    prog[16] = 8'hE0;  // RETI
    // main at 0x20.
    prog[32] = 8'h14;
    prog[33] = 8'h00;  // LDI B, 0
    prog[34] = 8'h10;
    prog[35] = 8'h02;  // LDI A, 2
    prog[36] = 8'hF8;
    prog[37] = 8'h02;  // OUT 2, A
    prog[38] = 8'hF2;  // EI
    prog[39] = 8'hF8;
    prog[40] = 8'h04;  // OUT 0, B   (loop)
    prog[41] = 8'hC0;
    prog[42] = 8'h27;  // JMP 0x27

    load_program;
    wait (dut.rst == 1'b0);
    repeat (8) @(posedge clk);

    guard = 0;
    while ((dut.cpu_i.u_rf.regs[1] < 8'd3) && (guard < 4000)) begin
      @(posedge clk);
      guard = guard + 1;
    end
    #1;
    counter = dut.cpu_i.u_rf.regs[1];
    if (counter < 8'd3) begin
      $display("  FAIL: only %0d timer interrupts in %0d cycles", counter, guard);
      errors = errors + 1;
    end
    if (!saw_irq) begin
      $display("  FAIL: timer_irq never went high");
      errors = errors + 1;
    end
    // The main loop may not have shown the new B yet, and B keeps changing
    // every 8 cycles: require a match that survives a full clock.
    guard = 0;
    while (!matched && (guard < 200)) begin
      @(posedge clk);
      #1;
      if (dut.led === reg_b[4:0]) begin
        @(posedge clk);
        #1;
        if (dut.led === reg_b[4:0]) matched = 1'b1;
      end
      guard = guard + 1;
    end
    if (!matched) begin
      $display("  FAIL: LED=%02X, B=%02X", dut.led, reg_b);
      errors = errors + 1;
    end

    // ---------------------------------------------------------------
    //  Phase 2: pending flag and disable (period 0)
    // ---------------------------------------------------------------
    n = 31;
    prog[0] = 8'h10;
    prog[1] = 8'h02;  // LDI A, 2
    prog[2] = 8'hF8;
    prog[3] = 8'h02;  // OUT 2, A
    prog[4] = 8'h1C;
    prog[5] = 8'h1E;  // LDI D, 30
    prog[6] = 8'h07;  // DEC D
    prog[7] = 8'hD1;
    prog[8] = 8'h06;  // JNZ 6
    prog[9] = 8'hF9;
    prog[10] = 8'h02;  // IN 2, A
    prog[11] = 8'hF8;
    prog[12] = 8'h00;  // OUT 0, A
    prog[13] = 8'h10;
    prog[14] = 8'h00;  // LDI A, 0
    prog[15] = 8'hF8;
    prog[16] = 8'h02;  // OUT 2, A (disable)
    prog[17] = 8'h1C;
    prog[18] = 8'h1E;  // LDI D, 30
    prog[19] = 8'h07;  // DEC D
    prog[20] = 8'hD1;
    prog[21] = 8'h13;  // JNZ 0x13
    prog[22] = 8'hF9;
    prog[23] = 8'h02;  // IN 2, A
    prog[24] = 8'hF8;
    prog[25] = 8'h00;  // OUT 0, A
    prog[26] = 8'h10;
    prog[27] = 8'h1F;  // LDI A, 0x1F
    prog[28] = 8'hF8;
    prog[29] = 8'h00;  // OUT 0, A (done marker)
    prog[30] = 8'hF0;  // HLT

    load_program;
    restart_cpu;

    guard = 0;
    while (!saw_pending && (guard < 4000)) begin
      @(posedge clk);
      if (dut.led === 5'b00001) saw_pending <= 1'b1;
      guard = guard + 1;
    end
    if (!saw_pending) begin
      $display("  FAIL: port 2 never reported the pending interrupt");
      errors = errors + 1;
    end
    if (dut.timer_irq !== 1'b1) begin
      $display("  FAIL: timer_irq is low while the pending flag reads 1");
      errors = errors + 1;
    end

    guard = 0;
    while (!saw_clear && (guard < 4000)) begin
      @(posedge clk);
      if (saw_pending && (dut.led === 5'b00000)) saw_clear <= 1'b1;
      guard = guard + 1;
    end
    if (!saw_clear) begin
      $display("  FAIL: period 0 did not clear the pending interrupt");
      errors = errors + 1;
    end

    guard = 0;
    while ((dut.out_data !== 8'h1F) && (guard < 4000)) begin
      @(posedge clk);
      guard = guard + 1;
    end
    #1;
    if (dut.out_data !== 8'h1F) begin
      $display("  FAIL: the disable program did not finish (out_data=%02X)", dut.out_data);
      errors = errors + 1;
    end
    if (dut.timer_irq !== 1'b0) begin
      $display("  FAIL: timer_irq still high after period 0");
      errors = errors + 1;
    end
    if (dut.timer_i.period_r !== 8'h00) begin
      $display("  FAIL: timer period is %02X, expected 00", dut.timer_i.period_r);
      errors = errors + 1;
    end

    if (errors == 0) $display("TOP TIMER: ALL TESTS PASSED");
    else $display("TOP TIMER: %0d FAILURES", errors);

    if (errors != 0) $fatal(1, "TOP TIMER: there are failures, check above");
    $finish;
  end

endmodule

`default_nettype wire
