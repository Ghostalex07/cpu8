// ============================================================================
//  pc_fv.sv - Formal properties of the program counter (rtl/pc.v)
//
//  The harness checks the documented priority of the synchronous actions:
//  reset, then load, then increment, then hold.  The only assumption is that
//  reset is applied at time 0; every later input sequence is legal.
//
//  Run with `make formal` (SymbiYosys, see formal/pc.sby, BMC depth 8).
// ============================================================================
`default_nettype none

module pc_fv (
    input wire       clk,
    input wire       rst,
    input wire       load,
    input wire       inc,
    input wire [7:0] d_in
);

    wire [7:0] q;

    pc dut (
        .clk (clk),
        .rst (rst),
        .load(load),
        .inc (inc),
        .d_in(d_in),
        .q   (q)
    );

    reg f_past_valid = 1'b0;

    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) begin
        if (f_past_valid) begin
            if ($past(rst)) assert (q == 8'h00);
            else if ($past(load)) assert (q == $past(d_in));
            else if ($past(inc)) assert (q == $past(q) + 8'd1);
            else assert (q == $past(q));
        end
    end

endmodule

`default_nettype wire
