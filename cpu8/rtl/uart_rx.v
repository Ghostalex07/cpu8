// ============================================================================
//  uart_rx.v - 8N1 UART receiver
//
//  Samples the serial line at `CLK_HZ / DIV` baud.  The asynchronous input is
//  resynchronized with two flip-flops; on a start edge the receiver waits half
//  a bit period, checks that the start bit is still low (to reject glitches)
//  and then samples the eight data bits and the stop bit in the middle of each
//  bit.  A complete frame with a valid stop bit sets `ready` and stores the
//  byte in `data`; a new frame that arrives before the CPU reads the previous
//  one sets `overrun`, so no data is lost silently.
//
//  `rd` is a one-cycle pulse from the port decoder (an IN of the data port):
//  it clears `ready` and `overrun` and acknowledges the byte.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module uart_rx #(
    parameter integer DIV = 104  // clock cycles per bit: CLK_HZ / BAUD
) (
    input  wire       clk,
    input  wire       rst,      // synchronous reset, active high
    input  wire       rx,       // serial line (asynchronous, idle high)
    input  wire       rd,       // one-cycle pulse: the byte has been read
    output reg  [7:0] data,     // last received byte
    output reg        ready,    // `data` holds an unread byte
    output reg        overrun,  // a frame was lost because `ready` was set
    output wire       busy      // high while a frame is being received
);

  localparam integer CNT_W = (DIV > 1) ? $clog2(DIV) : 1;
  /* verilator lint_off WIDTHTRUNC */
  localparam [CNT_W-1:0] RELOAD = DIV - 1;
  /* verilator lint_on WIDTHTRUNC */
  // The two-flop synchronizer delays the detected edge by two clocks, so wait
  // half a bit MINUS that skew to sample the middle of the start bit.
  localparam integer SKEW = 2;
  /* verilator lint_off WIDTHTRUNC */
  localparam [CNT_W-1:0] HALF = ((DIV / 2) > SKEW) ? (DIV / 2 - SKEW) : 0;
  /* verilator lint_on WIDTHTRUNC */

  localparam [1:0] S_IDLE = 2'd0;
  localparam [1:0] S_START = 2'd1;
  localparam [1:0] S_DATA = 2'd2;
  localparam [1:0] S_STOP = 2'd3;

  // Two flip-flops resynchronize the (possibly idle-high) serial input.
  reg rx_meta = 1'b1;
  reg rx_sync = 1'b1;
  reg rx_prev = 1'b1;

  always @(posedge clk) begin
    rx_meta <= rx;
    rx_sync <= rx_meta;
    rx_prev <= rx_sync;
  end

  wire start_edge = rx_prev && !rx_sync;

  reg [1:0] st;
  reg [CNT_W-1:0] cnt;
  reg [2:0] bitn;
  reg [7:0] sh;

  assign busy = (st != S_IDLE);

  always @(posedge clk) begin
    if (rst) begin
      st <= S_IDLE;
      cnt <= {CNT_W{1'b0}};
      bitn <= 3'd0;
      sh <= 8'h00;
      data <= 8'h00;
      ready <= 1'b0;
      overrun <= 1'b0;
    end else begin
      if (rd) begin
        ready   <= 1'b0;
        overrun <= 1'b0;
      end
      case (st)
        S_IDLE: begin
          if (start_edge) begin
            st  <= S_START;
            cnt <= HALF;
          end
        end
        S_START: begin
          if (cnt == {CNT_W{1'b0}}) begin
            if (!rx_sync) begin
              st   <= S_DATA;
              bitn <= 3'd0;
              cnt  <= RELOAD;
            end else begin
              st <= S_IDLE;  // false start (glitch), wait for the next one
            end
          end else begin
            cnt <= cnt - 1'b1;
          end
        end
        S_DATA: begin
          if (cnt == {CNT_W{1'b0}}) begin
            sh  <= {rx_sync, sh[7:1]};  // LSB first
            cnt <= RELOAD;
            if (bitn == 3'd7) st <= S_STOP;
            else bitn <= bitn + 3'd1;
          end else begin
            cnt <= cnt - 1'b1;
          end
        end
        S_STOP: begin
          if (cnt == {CNT_W{1'b0}}) begin
            if (rx_sync) begin
              data <= sh;
              if (ready) overrun <= 1'b1;
              ready <= 1'b1;
            end
            st <= S_IDLE;
          end else begin
            cnt <= cnt - 1'b1;
          end
        end
        default: st <= S_IDLE;
      endcase
    end
  end

endmodule

`default_nettype wire
