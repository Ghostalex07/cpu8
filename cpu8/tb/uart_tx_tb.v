// ============================================================================
//  uart_tx_tb.v - 8N1 UART transmitter testbench
//
//  Runs the transmitter with a short divisor (8 clocks per bit, so a frame
//  lasts 800 ns) and decodes the line with a behavioural receiver: mid-bit
//  sampling of the start, the eight data bits and the stop bit.  It also
//  checks the idle level, `busy` and that a start pulse while a frame is in
//  flight is ignored instead of corrupting it.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module uart_tx_tb;

  localparam integer DIV = 8;
  localparam integer BIT_NS = DIV * 10;  // 10 ns clock period

  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst = 1'b1;
  reg start = 1'b0;
  reg [7:0] data = 8'h00;
  wire tx;
  wire busy;

  integer errors = 0;

  uart_tx #(
      .DIV(DIV)
  ) dut (
      .clk(clk),
      .rst(rst),
      .start(start),
      .data(data),
      .tx(tx),
      .busy(busy)
  );

  // One-cycle start pulse; waits until the transmitter is free.
  task send;
    input [7:0] value;
    begin
      wait (!busy);
      @(posedge clk);
      data  = value;
      start = 1'b1;
      @(posedge clk);
      start = 1'b0;
    end
  endtask

  // Decode one 8N1 frame: sample the middle of each bit.
  task recv;
    output [7:0] value;
    integer i;
    begin
      @(negedge tx);  // start bit
      #(BIT_NS + BIT_NS / 2);
      for (i = 0; i < 8; i = i + 1) begin
        value[i] = tx;
        #(BIT_NS);
      end
      if (tx !== 1'b1) begin
        $display("  FAIL: stop bit is %b, expected 1", tx);
        errors = errors + 1;
      end
    end
  endtask

  task check_byte;
    input [7:0] value;
    reg [7:0] got;
    begin
      if (busy) begin
        $display("  FAIL: busy is high before sending %02X", value);
        errors = errors + 1;
      end
      fork
        recv(got);
        send(value);
      join
      if (got !== value) begin
        $display("  FAIL: sent %02X, received %02X", value, got);
        errors = errors + 1;
      end else begin
        $display("  sent %02X ok", value);
      end
      wait (!busy);
      #(BIT_NS);  // let the line settle before the next frame
    end
  endtask

  initial begin
    $dumpfile("build/uart_tx_tb.vcd");
    $dumpvars(0, uart_tx_tb);

    repeat (2) @(posedge clk);
    rst = 1'b0;
    #1;
    if (tx !== 1'b1) begin
      $display("  FAIL: the line must idle high after reset");
      errors = errors + 1;
    end

    check_byte(8'h55);
    check_byte(8'hA5);
    check_byte(8'h00);
    check_byte(8'hFF);
    check_byte(8'h80);
    check_byte(8'h01);

    // A start pulse while a frame is in flight must be ignored.
    begin : ignored_start
      reg [7:0] got;
      fork
        begin
          send(8'h3C);
          wait (busy);
          @(posedge clk);
          data  = 8'hF0;
          start = 1'b1;
          @(posedge clk);
          start = 1'b0;
        end
        recv(got);
      join
      if (got !== 8'h3C) begin
        $display("  FAIL: busy frame sent 3C, received %02X", got);
        errors = errors + 1;
      end else begin
        $display("  start while busy ignored, frame 3C ok");
      end
    end

    wait (!busy);
    #(BIT_NS * 12);
    if (tx !== 1'b1) begin
      $display("  FAIL: unexpected frame after the ignored start");
      errors = errors + 1;
    end

    if (errors == 0) $display("UART TX: ALL TESTS PASSED");
    else $display("UART TX: %0d FAILURES", errors);

    if (errors != 0) $fatal(1, "UART TX: there are failures, check above");
    $finish;
  end

endmodule

`default_nettype wire
