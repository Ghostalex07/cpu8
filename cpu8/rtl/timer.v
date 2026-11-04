// ============================================================================
//  timer.v - Programmable millisecond timer with a level interrupt
//
//  The period is written by the CPU as a number of milliseconds (1..255, 0
//  disables the timer and clears the interrupt).  Every period the timer sets
//  `irq` high and reloads; the interrupt stays high until the CPU writes the
//  timer port again (normally the handler re-arms it), which also clears it.
//  That level behaviour matches the CPU's IRQ input: the core samples it at
//  instruction boundaries and clears flag I when the interrupt is taken.
//
//  `TICKS_PER_MS` is CLK_HZ / 1000; it is a parameter so the testbench can use
//  a handful of clocks per millisecond instead of 12000.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module timer #(
    parameter integer TICKS_PER_MS = 12_000  // clock cycles in one millisecond
) (
    input  wire       clk,
    input  wire       rst,     // synchronous reset, active high
    input  wire       wr,      // one-cycle pulse: new period (0 disables)
    input  wire [7:0] period,  // period in milliseconds
    output reg        irq      // level interrupt request
);

  localparam integer CNT_W = (TICKS_PER_MS > 1) ? $clog2(TICKS_PER_MS) : 1;
  /* verilator lint_off WIDTHTRUNC */
  localparam [CNT_W-1:0] RELOAD = TICKS_PER_MS - 1;
  /* verilator lint_on WIDTHTRUNC */

  reg [7:0] period_r;
  reg [7:0] ms;
  reg [CNT_W-1:0] tick;

  always @(posedge clk) begin
    if (rst) begin
      period_r <= 8'd0;
      ms <= 8'd0;
      tick <= {CNT_W{1'b0}};
      irq <= 1'b0;
    end else if (wr) begin
      period_r <= period;
      ms <= 8'd0;
      tick <= {CNT_W{1'b0}};
      irq <= 1'b0;
    end else if (period_r != 8'd0) begin
      if (tick == RELOAD) begin
        tick <= {CNT_W{1'b0}};
        if (ms == period_r - 8'd1) begin
          ms  <= 8'd0;
          irq <= 1'b1;  // one period elapsed: request the interrupt
        end else begin
          ms <= ms + 8'd1;
        end
      end else begin
        tick <= tick + 1'b1;
      end
    end
  end

endmodule

`default_nettype wire
