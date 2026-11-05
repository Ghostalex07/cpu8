// ============================================================================
//  timer_fv.sv - Formal properties of the millisecond timer (rtl/timer.v)
//
//  The harness checks the documented level-interrupt behaviour:
//    - a zero period disables the timer and forces irq low;
//    - a write (re)loads the period, clears the counters and clears irq;
//    - while the current period is non-zero, ms stays in 0..period-1;
//    - irq, once raised, stays high until the next write or reset.
//
//  Only the reset is assumed (applied at time 0); every later input sequence
//  is explored.  Internal registers are observed through ports wired after
//  flattening by timer.sby (`connect -set ...`).
//
//  Run with `make formal` (formal/timer.sby, BMC depth 16).  TICKS_PER_MS is
//  reduced to 4 so the interesting transitions happen in a few cycles.
// ============================================================================
`default_nettype none

module timer_fv (
    input wire       clk,
    input wire       rst,
    input wire       wr,
    input wire [7:0] period
);

  wire       irq;
  // Filled in after flattening (see timer.sby).
  wire [7:0] period_obs;
  wire [7:0] ms_obs;

  timer #(
      .TICKS_PER_MS(4)
  ) dut (
      .clk(clk),
      .rst(rst),
      .wr(wr),
      .period(period),
      .irq(irq)
  );

  initial assume (rst);

  reg f_past_valid = 1'b0;
  always @(posedge clk) f_past_valid <= 1'b1;

  // --- Combinational invariant, checked on reachable states only ---
  // (the power-up register values are arbitrary, so it is guarded by
  // f_past_valid like the sequential properties).
  always @(posedge clk) begin
    if (f_past_valid) assert (!(period_obs == 8'd0) || (irq == 1'b0));
  end

  // --- Sequential properties ---
  always @(posedge clk) begin
    if (f_past_valid) begin
      // Reset wins over everything.
      if ($past(rst)) begin
        assert (period_obs == 8'd0);
        assert (ms_obs == 8'd0);
        assert (irq == 1'b0);
      end
      // A write clears the pending interrupt (the new period and the counter
      // reset are checked by the simulation testbench, tb/timer_tb.v).
      else if ($past(wr)) begin
        assert (irq == 1'b0);
      end
      // With no write and a disabled timer the output stays quiet.
      else if ($past(period_obs) == 8'd0) begin
        assert (ms_obs == 8'd0);
        assert (irq == 1'b0);
      end
      // Otherwise ms is always a valid millisecond within the period.
      else begin
        assert (ms_obs < period_obs);
      end

      // irq is sticky: once high it remains high until a write or reset.
      if ($past(irq) && !$past(wr) && !$past(rst)) assert (irq);
    end
  end

  // --- Cover: the interrupt is actually reachable ---
  always @(posedge clk) begin
    if (f_past_valid && irq) cover (1'b1);
  end

endmodule

`default_nettype wire
