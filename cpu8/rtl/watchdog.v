// ============================================================================
//  watchdog.v - Programmable watchdog timer
//
//  Counts down from a period given in milliseconds.  When it reaches zero it
//  sets `timeout` and pulses `irq`.  Writing 0 disables it and clears the
//  flags.  TICKS_PER_MS is the number of clock cycles per millisecond.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module watchdog #(
    parameter integer TICKS_PER_MS = 12_000
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       wr,
    input  wire [7:0] period,
    output reg        irq,
    output reg        timeout
);

  reg [ 7:0] period_r;
  reg [15:0] tick;
  reg [ 7:0] remaining;
  reg        enabled;

  always @(posedge clk) begin
    if (rst) begin
      period_r  <= 8'd0;
      tick      <= 16'd0;
      remaining <= 8'd0;
      enabled   <= 1'b0;
      irq       <= 1'b0;
      timeout   <= 1'b0;
    end else if (wr) begin
      period_r  <= period;
      tick      <= 16'd0;
      remaining <= period;
      enabled   <= (period != 8'd0);
      irq       <= 1'b0;
      timeout   <= 1'b0;
    end else if (enabled && !timeout) begin
      /* verilator lint_off WIDTH */
      if (tick == TICKS_PER_MS - 1) begin
        /* verilator lint_on WIDTH */
        tick <= 16'd0;
        if (remaining == 8'd1) begin
          remaining <= 8'd0;
          enabled   <= 1'b0;
          timeout   <= 1'b1;
          irq       <= 1'b1;
        end else begin
          remaining <= remaining - 8'd1;
        end
      end else begin
        tick <= tick + 16'd1;
      end
    end
  end

endmodule

`default_nettype wire
