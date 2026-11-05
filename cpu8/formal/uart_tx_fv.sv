// ============================================================================
//  uart_tx_fv.sv - Formal properties of the 8N1 transmitter (rtl/uart_tx.v)
//
//  Checks the frame-level contract:
//    - the line is high whenever the transmitter is idle;
//    - a start pulse accepted while idle makes busy rise on the next cycle;
//    - a frame never lasts longer than 10 bit periods (start + 8 data + stop);
//    - busy only rises through an accepted start (never spontaneously).
//
//  DIV is reduced to 4 so a whole frame fits in a small BMC depth.  Only reset
//  is assumed (at time 0); start/data are otherwise free.
//
//  Run with `make formal` (formal/uart_tx.sby, BMC depth 64).
// ============================================================================
`default_nettype none

module uart_tx_fv (
    input wire       clk,
    input wire       rst,
    input wire       start,
    input wire [7:0] data
);

  localparam integer DIV = 4;
  localparam [5:0] MAX_AGE = 10 * DIV + 2;

  wire tx;
  wire busy;

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

  initial assume (rst);

  reg f_past_valid = 1'b0;
  always @(posedge clk) f_past_valid <= 1'b1;

  // Cycles the transmitter has been busy (bounded by the frame length).
  reg [5:0] age;
  always @(posedge clk) begin
    if (rst) age <= 6'd0;
    else if (busy) age <= age + 6'd1;
    else age <= 6'd0;
  end

  always @(posedge clk) begin
    if (f_past_valid) begin
      // Idle line is high.
      if (!busy) assert (tx == 1'b1);

      // An accepted start (idle, not in reset) raises busy next cycle.
      if ($past(start) && !$past(busy) && !$past(rst)) assert (busy);

      // busy only rises through an accepted start.
      if (busy && !$past(busy) && !$past(rst))
        assert ($past(start) || $past(rst));

      // A frame is start + 8 data + stop = 10 bit periods of DIV clocks.
      if (!rst) assert (age < MAX_AGE);
    end
  end

  // --- Cover: a full frame is transmitted ---
  always @(posedge clk) begin
    if (f_past_valid && busy) cover (1'b1);
    if (f_past_valid && !busy && $past(busy)) cover (1'b1);
  end

endmodule

`default_nettype wire
