`timescale 1ns / 1ps
`default_nettype none

module spi_tb;
  reg clk = 0;
  reg rst = 1;
  always #5 clk = ~clk;

  reg start = 0;
  reg [7:0] tx_data = 8'h00;
  wire mosi;
  wire miso = mosi;  // loopback
  wire sclk;
  wire cs_n;
  wire busy;
  wire done;
  wire [7:0] rx_data;

  spi_master #(
      .DIV(4)
  ) dut (
      .clk(clk),
      .rst(rst),
      .start(start),
      .tx_data(tx_data),
      .mosi(mosi),
      .miso(miso),
      .sclk(sclk),
      .cs_n(cs_n),
      .busy(busy),
      .done(done),
      .rx_data(rx_data)
  );

  integer errors = 0;
  initial begin
    repeat (4) @(posedge clk);
    rst = 0;
    @(posedge clk);

    // Test 1: send 0xA5, loopback -> rx == tx
    tx_data = 8'hA5;
    @(posedge clk);
    start = 1;
    @(posedge clk);
    #1;
    start = 0;

    // wait for done
    while (!done) begin
      @(posedge clk);
      #1;
    end
    if (rx_data !== 8'hA5) begin
      $display("FAIL rx=%02h expected A5", rx_data);
      errors = errors + 1;
    end
    if (cs_n !== 1'b1) begin
      $display("FAIL cs_n not high after done");
      errors = errors + 1;
    end
    if (busy !== 1'b0) begin
      $display("FAIL busy not cleared");
      errors = errors + 1;
    end

    // Test 2: send 0x00
    repeat (4) @(posedge clk);
    tx_data = 8'h00;
    @(posedge clk);
    start = 1;
    @(posedge clk);
    #1;
    start = 0;
    while (!done) begin
      @(posedge clk);
      #1;
    end
    if (rx_data !== 8'h00) begin
      $display("FAIL rx=%02h expected 00", rx_data);
      errors = errors + 1;
    end

    // Test 3: start ignored while busy
    repeat (4) @(posedge clk);
    tx_data = 8'hFF;
    @(posedge clk);
    start = 1;
    @(posedge clk);
    #1;
    start = 0;
    // pulse start again mid-transfer
    repeat (3) @(posedge clk);
    start = 1;
    @(posedge clk);
    #1;
    start = 0;
    while (!done) begin
      @(posedge clk);
      #1;
    end
    if (rx_data !== 8'hFF) begin
      $display("FAIL rx=%02h expected FF", rx_data);
      errors = errors + 1;
    end

    if (errors == 0) $display("SPI: ALL TESTS PASSED");
    else $display("SPI: %0d FAILURES", errors);
    $finish;
  end
endmodule

`default_nettype wire
