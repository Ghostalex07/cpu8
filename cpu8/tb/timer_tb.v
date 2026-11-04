// ============================================================================
//  timer_tb.v - Programmable millisecond timer testbench
//
//  Uses TICKS_PER_MS = 4 so a millisecond lasts four clocks.  Checks that a
//  written period fires after exactly that many "milliseconds", that `irq` is
//  a level (it stays high until the next write), that a new write clears and
//  reloads it, that period 0 disables the timer and that the counter reloads
//  after every period.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module timer_tb;

  localparam integer TICKS_PER_MS = 4;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst = 1'b1;
  reg wr = 1'b0;
  reg [7:0] period = 8'h00;
  wire irq;

  integer errors = 0;

  timer #(
      .TICKS_PER_MS(TICKS_PER_MS)
  ) dut (
      .clk(clk),
      .rst(rst),
      .wr(wr),
      .period(period),
      .irq(irq)
  );

  task write_period;
    input [7:0] value;
    begin
      @(posedge clk);
      period = value;
      wr = 1'b1;
      @(posedge clk);
      wr = 1'b0;
      #1;
    end
  endtask

  task wait_irq;
    input integer ms;
    input [8*24-1:0] label;
    integer n;
    begin
      n = 0;
      while (!irq && n < ms * TICKS_PER_MS * 2) begin
        @(posedge clk);
        n = n + 1;
      end
      if (!irq) begin
        $display("  FAIL: %0s: irq did not fire within %0d ms", label, ms);
        errors = errors + 1;
      end else begin
        $display("  %0s: irq after %0d cycles (%0d ms) ok", label, n, ms);
      end
    end
  endtask

  task check_low;
    input [8*24-1:0] label;
    begin
      if (irq) begin
        $display("  FAIL: %0s: irq must be low", label);
        errors = errors + 1;
      end
    end
  endtask

  initial begin
    $dumpfile("build/timer_tb.vcd");
    $dumpvars(0, timer_tb);

    repeat (2) @(posedge clk);
    rst = 1'b0;
    #1;
    check_low("after reset");

    // 1) A one-millisecond period fires after four clocks.
    write_period(8'd1);
    check_low("after arming 1 ms");
    wait_irq(1, "1 ms");

    // 2) The level stays high until the CPU acknowledges/re-arms.
    repeat (10) @(posedge clk);
    if (!irq) begin
      $display("  FAIL: irq must stay high until the next write");
      errors = errors + 1;
    end

    // 3) A new period clears the request and reloads.
    write_period(8'd3);
    check_low("after re-arming 3 ms");
    wait_irq(3, "3 ms");

    // 4) Re-arm with the same period: the counter must reload, not latch.
    write_period(8'd2);
    check_low("after re-arming 2 ms");
    wait_irq(2, "2 ms");
    write_period(8'd2);
    wait_irq(2, "2 ms again");

    // 5) Period 0 disables and clears.
    write_period(8'd0);
    check_low("after disabling");
    repeat (8 * TICKS_PER_MS) @(posedge clk);
    check_low("after waiting with the timer disabled");

    if (errors == 0) $display("TIMER: ALL TESTS PASSED");
    else $display("TIMER: %0d FAILURES", errors);

    if (errors != 0) $fatal(1, "TIMER: there are failures, check above");
    $finish;
  end

endmodule

`default_nettype wire
