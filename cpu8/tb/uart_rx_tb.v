// ============================================================================
//  uart_rx_tb.v - 8N1 UART receiver testbench
//
//  Drives the serial line with a behavioural transmitter (DIV = 8 clocks per
//  bit) and checks: a normal frame, the read strobe that clears `ready`, a
//  second frame arriving before the first is read (overrun), a frame with a
//  bad stop bit (discarded) and a short glitch (false start, ignored).
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module uart_rx_tb;

  localparam integer DIV = 8;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst = 1'b1;
  reg rx = 1'b1;
  reg rd = 1'b0;

  wire [7:0] data;
  wire ready;
  wire overrun;
  wire busy;

  integer errors = 0;

  uart_rx #(
      .DIV(DIV)
  ) dut (
      .clk(clk),
      .rst(rst),
      .rx(rx),
      .rd(rd),
      .data(data),
      .ready(ready),
      .overrun(overrun),
      .busy(busy)
  );

  // Drive one 8N1 frame; the bit edges are aligned to the falling clock edge.
  task frame;
    input [7:0] value;
    input stop;
    integer i;
    begin
      @(negedge clk);
      rx = 1'b0;  // start
      repeat (DIV) @(negedge clk);
      for (i = 0; i < 8; i = i + 1) begin
        rx = value[i];
        repeat (DIV) @(negedge clk);
      end
      rx = stop;
      repeat (DIV) @(negedge clk);
      rx = 1'b1;
    end
  endtask

  task read_byte;
    begin
      @(posedge clk);
      rd = 1'b1;
      @(posedge clk);
      rd = 1'b0;
      #1;
      if (ready) begin
        $display("  FAIL: ready is still high after the read strobe");
        errors = errors + 1;
      end
    end
  endtask

  task expect_byte;
    input [7:0] value;
    integer n;
    begin
      n = 0;
      while (!ready && n < 4 * DIV * 16) begin
        @(posedge clk);
        n = n + 1;
      end
      if (!ready) begin
        $display("  FAIL: timeout waiting for %02X", value);
        errors = errors + 1;
      end else if (data !== value) begin
        $display("  FAIL: received %02X, expected %02X", data, value);
        errors = errors + 1;
      end else begin
        $display("  received %02X ok", value);
      end
    end
  endtask

  initial begin
    $dumpfile("build/uart_rx_tb.vcd");
    $dumpvars(0, uart_rx_tb);

    repeat (2) @(posedge clk);
    rst = 1'b0;
    #1;
    if (ready || overrun || busy) begin
      $display("  FAIL: the receiver is not idle after reset");
      errors = errors + 1;
    end

    // 1) Normal frame
    frame(8'h55, 1'b1);
    expect_byte(8'h55);
    read_byte();
    read_byte();  // a second read must be harmless

    // 2) More values, including the extremes
    frame(8'h00, 1'b1);
    expect_byte(8'h00);
    read_byte();
    frame(8'hFF, 1'b1);
    expect_byte(8'hFF);
    read_byte();
    frame(8'hA5, 1'b1);
    expect_byte(8'hA5);
    read_byte();

    // 3) Overrun: a second frame arrives before the first is read
    frame(8'h01, 1'b1);
    expect_byte(8'h01);
    frame(8'h02, 1'b1);
    expect_byte(8'h02);
    #1;
    if (!overrun) begin
      $display("  FAIL: overrun was not flagged");
      errors = errors + 1;
    end
    if (!ready) begin
      $display("  FAIL: ready must stay high after an overrun");
      errors = errors + 1;
    end
    read_byte();
    #1;
    if (overrun) begin
      $display("  FAIL: overrun is still high after the read strobe");
      errors = errors + 1;
    end

    // 4) Bad stop bit: the frame is discarded
    frame(8'h3C, 1'b0);
    repeat (4 * DIV) @(posedge clk);
    if (ready) begin
      $display("  FAIL: a frame with a bad stop bit was accepted");
      errors = errors + 1;
    end

    // 5) Short glitch: a false start must not produce a byte
    @(negedge clk);
    rx = 1'b0;
    repeat (2) @(negedge clk);
    rx = 1'b1;
    repeat (4 * DIV) @(posedge clk);
    if (ready) begin
      $display("  FAIL: a glitch produced a byte");
      errors = errors + 1;
    end

    if (errors == 0) $display("UART RX: ALL TESTS PASSED");
    else $display("UART RX: %0d FAILURES", errors);

    if (errors != 0) $fatal(1, "UART RX: there are failures, check above");
    $finish;
  end

endmodule

`default_nettype wire
