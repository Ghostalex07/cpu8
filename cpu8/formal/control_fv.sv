// ============================================================================
//  control_fv.sv - Formal invariant of the control FSM (rtl/control.v)
//
//  The FSM uses 3 bits but only seven encodings are defined (0..6); 3'd7 is
//  reserved.  `nstate` is the combinational next-state function, so proving
//  that it never produces 3'd7 for ANY current state and ANY inputs proves
//  that the reachable set stays inside the documented encoding.  The FSM is
//  also self-recovering: if it ever landed in the reserved state it would go
//  back to S_FETCH.
// ============================================================================
`default_nettype none

module control_fv (
    input wire       clk,
    input wire       rst,
    input wire [7:0] instr,
    input wire [7:0] fetched,
    input wire [3:0] xsub,
    input wire       flag_z,
    input wire       flag_c,
    input wire       flag_n,
    input wire       flag_v,
    input wire       flag_i,
    input wire       irq
);

    wire halted;

    control dut (
        .clk(clk), .rst(rst), .instr(instr), .fetched(fetched), .xsub(xsub),
        .flag_z(flag_z), .flag_c(flag_c), .flag_n(flag_n), .flag_v(flag_v),
        .flag_i(flag_i), .irq(irq), .halted(halted)
    );

    localparam [2:0] S_FETCH = 3'd0;

    // The next-state function never leaves the documented encodings.
    always @* assert (dut.nstate != 3'd7);

    // If the FSM ever reached the reserved encoding it recovers to S_FETCH.
    always @* assert (dut.state != 3'd7 || dut.nstate == S_FETCH);

endmodule

`default_nettype wire
