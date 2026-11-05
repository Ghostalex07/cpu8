`timescale 1ns / 1ps
`default_nettype none

module watchdog_tb;
  reg clk = 0;
  reg rst = 1;
  always #5 clk = ~clk;

  reg wr = 0;
  reg [7:0] period = 0;
  wire irq;
  wire timeout;

  watchdog #(
      .TICKS_PER_MS(4)
  ) dut (
      .clk(clk),
      .rst(rst),
      .wr(wr),
      .period(period),
      .irq(irq),
      .timeout(timeout)
  );

  integer errors = 0;
  task reload;
    input [7:0] p;
    begin
      period = p;
      wr = 1;
      @(posedge clk);
      #1;
      wr = 0;
      period = 0;
    end
  endtask

  initial begin
    repeat (4) @(posedge clk);
    rst = 0;
    @(posedge clk);

    // Test 1: period 1 ms -> timeout after ~4 cycles, irq pulses
    reload(8'd1);
    repeat (20) @(posedge clk);
    if (timeout !== 1'b1) begin
      $display("FAIL timeout not set");
      errors = errors + 1;
    end
    if (irq !== 1'b1) begin
      $display("FAIL irq not set");
      errors = errors + 1;
    end

    // Test 2: reload clears flags and rearms
    reload(8'd2);
    if (timeout !== 1'b0) begin
      $display("FAIL timeout not cleared on reload");
      errors = errors + 1;
    end
    if (irq !== 1'b0) begin
      $display("FAIL irq not cleared on reload");
      errors = errors + 1;
    end
    repeat (40) @(posedge clk);
    if (timeout !== 1'b1) begin
      $display("FAIL timeout2 not set");
      errors = errors + 1;
    end

    // Test 3: period 0 disables
    reload(8'd0);
    repeat (20) @(posedge clk);
    if (timeout !== 1'b0) begin
      $display("FAIL timeout should be cleared by period 0");
      errors = errors + 1;
    end

    if (errors == 0) $display("WATCHDOG: ALL TESTS PASSED");
    else $display("WATCHDOG: %0d FAILURES", errors);
    $finish;
  end
endmodule

`default_nettype wire
