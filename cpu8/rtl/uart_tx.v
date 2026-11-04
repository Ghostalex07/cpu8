// ============================================================================
//  uart_tx.v - 8N1 UART transmitter
//
//  Shifts out one byte as a standard 8N1 frame (one start bit, eight data bits
//  LSB first and one stop bit) at `CLK_HZ / DIV` baud.  `start` is a one-cycle
//  pulse that loads `data`; while `busy` is high the transmitter ignores new
//  starts, so the peripheral that owns it must poll the status port (or accept
//  the drop).
//
//  The line idles high and returns high during the stop bit.  A fractional
//  divisor (the iCEstick runs at 12 MHz and 115200 baud is 104.17 clocks per
//  bit) is rounded down: 104 clocks gives 115384 baud, 0.16 % fast, far inside
//  the 2 % that a UART receiver tolerates.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module uart_tx #(
    parameter integer DIV = 104  // clock cycles per bit: CLK_HZ / BAUD
) (
    input  wire       clk,
    input  wire       rst,    // synchronous reset, active high
    input  wire       start,  // one-cycle pulse: begin a transmission
    input  wire [7:0] data,   // byte to send
    output wire       tx,     // serial line (idle high)
    output wire       busy    // high while a frame is being shifted out
);

  localparam integer CNT_W = (DIV > 1) ? $clog2(DIV) : 1;
  /* verilator lint_off WIDTHTRUNC */
  localparam [CNT_W-1:0] RELOAD = DIV - 1;
  /* verilator lint_on WIDTHTRUNC */

  reg [9:0] sh;  // {stop, data[7:0], start}; bit 0 goes out first
  reg [3:0] bits;  // bits left to send (10 down to 1)
  reg [CNT_W-1:0] cnt;  // clocks left in the current bit
  reg busy_r;

  assign tx   = busy_r ? sh[0] : 1'b1;
  assign busy = busy_r;

  always @(posedge clk) begin
    if (rst) begin
      sh <= 10'h3FF;
      bits <= 4'd0;
      cnt <= {CNT_W{1'b0}};
      busy_r <= 1'b0;
    end else if (!busy_r) begin
      if (start) begin
        sh <= {1'b1, data, 1'b0};
        bits <= 4'd10;
        cnt <= RELOAD;
        busy_r <= 1'b1;
      end
    end else if (cnt == {CNT_W{1'b0}}) begin
      cnt  <= RELOAD;
      sh   <= {1'b1, sh[9:1]};
      bits <= bits - 4'd1;
      if (bits == 4'd1) busy_r <= 1'b0;
    end else begin
      cnt <= cnt - 1'b1;
    end
  end

endmodule

`default_nettype wire
