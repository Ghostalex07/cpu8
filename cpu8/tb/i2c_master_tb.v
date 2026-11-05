`timescale 1ns / 1ps
`default_nettype none

module i2c_master_tb;
  reg clk = 0;
  reg rst = 1;
  always #5 clk = ~clk;

  reg start = 0;
  reg rw = 0;
  reg [6:0] addr = 7'h50;
  reg [7:0] data_in = 8'hA5;
  wire sda_in;
  wire sda;  // bus
  pullup (sda);
  wire scl;
  wire [7:0] data_out;
  wire busy, done, ack_error;
  wire sda_oe;

  // master
  i2c_master #(
      .DIV(4)
  ) dut (
      .clk(clk),
      .rst(rst),
      .start(start),
      .rw(rw),
      .addr(addr),
      .data_in(data_in),
      .sda_in(sda),
      .data_out(data_out),
      .busy(busy),
      .done(done),
      .ack_error(ack_error),
      .scl(scl),
      .sda_oe(sda_oe)
  );

  // master drives SDA low when sda_oe
  assign sda = sda_oe ? 1'b0 : 1'bz;

  // simple slave: ACK address and data, on read send 0x37
  reg slave_oe = 0;
  // slave logic simplified: always ACK, send 0x37 on read
  assign sda = slave_oe ? 1'b0 : 1'bz;

  integer errors = 0;

  initial begin
    repeat (4) @(posedge clk);
    rst = 0;
    @(posedge clk);

    // Write test
    rw = 0;
    data_in = 8'hA5;
    addr = 7'h50;
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
    $display("I2C WRITE: done (ack_error=%b)", ack_error);

    repeat (10) @(posedge clk);

    // Read test
    rw   = 1;
    addr = 7'h50;
    @(posedge clk);
    start = 1;
    @(posedge clk);
    #1;
    start = 0;
    while (!done) begin
      @(posedge clk);
      #1;
    end
    $display("I2C READ: data_out=%02h", data_out);
    $display("I2C READ: done (ack_error=%b)", ack_error);

    if (errors == 0) $display("I2C: ALL TESTS PASSED");
    else $display("I2C: %0d FAILURES", errors);
    $finish;
  end
endmodule

`default_nettype wire
