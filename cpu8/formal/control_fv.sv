// ============================================================================
//  control_fv.sv - Formal properties of the control FSM (rtl/control.v)
//
//  The harness checks the documented sequential behaviour of the 7-state FSM
//  (S_FETCH=0, S_OPR=1, S_EXEC=2, S_IRQ=3, S_HLT=4, S_OPR2=5, S_EXEC2=6).
//  Encoding 7 is reserved and must never be produced.
//
//  Initialisation: the only assumption is `initial assume (rst)`, i.e. the
//  trace starts with a synchronous reset applied at time 0.  No constraint is
//  placed on the inputs afterwards, so every legal instruction / interrupt
//  sequence is explored.  Clocked assertions are guarded by `f_past_valid`,
//  which suppresses the very first cycle where the sampled state is the
//  unconstrained power-up value (after the reset edge the state is known).
//
//  Observing the internal FSM state: Yosys has no hierarchical references, so
//  `state_obs` / `nstate_obs` are left undriven here.  control.sby flattens
//  the design and then connects them to the flattened `dut.state` and
//  `dut.nstate` wires with `connect -set` (see formal/control.sby).
//
//  Run with `make formal` (SymbiYosys, see formal/control.sby, BMC depth 12).
//  The cover statements at the end are checked by formal/control_cover.sby
//  (mode cover), because SymbiYosys removes $cover cells in bmc/prove mode.
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

    // Every DUT output is connected: leaving them dangling would let `prep`
    // optimise the FSM (and the logic under test) away.
    wire       halted;
    wire       ir_ld, opr_ld, pc_as_addr, pc_inc, pc_load;
    wire       rf_we, ram_we, flags_we, out_wr, alu_sh;
    wire [1:0] rf_waddr;
    wire [3:0] alu_op;
    wire       sel_imm, sel_mem, sel_a_rs, sel_one, flags_c_we;
    wire       sp_inc, sp_dec, sp_as_addr, sel_ram_rs;
    wire       pc_from_mem, sel_ram_pc, ind, idx, ext, xop_ld, rf_we2;
    wire       addr_alu, flag_ld, sel_ram_fl, pair16_ld, pair16_hi;
    wire       pc_from_vec, flag_i_set, flag_i_clear;
    wire       flag_save, flag_restore, sel_in, io_op;

    // Filled in after flattening (see control.sby).
    wire [2:0] state_obs;
    wire [2:0] nstate_obs;

    control dut (
        .clk(clk), .rst(rst), .instr(instr), .fetched(fetched), .xsub(xsub),
        .flag_z(flag_z), .flag_c(flag_c), .flag_n(flag_n), .flag_v(flag_v),
        .flag_i(flag_i), .irq(irq),
        .ir_ld(ir_ld), .opr_ld(opr_ld), .pc_as_addr(pc_as_addr),
        .pc_inc(pc_inc), .pc_load(pc_load), .rf_we(rf_we),
        .rf_waddr(rf_waddr), .ram_we(ram_we), .flags_we(flags_we),
        .out_wr(out_wr), .alu_op(alu_op), .alu_sh(alu_sh),
        .sel_imm(sel_imm), .sel_mem(sel_mem), .sel_a_rs(sel_a_rs),
        .sel_one(sel_one), .flags_c_we(flags_c_we), .sp_inc(sp_inc),
        .sp_dec(sp_dec), .sp_as_addr(sp_as_addr), .sel_ram_rs(sel_ram_rs),
        .pc_from_mem(pc_from_mem), .sel_ram_pc(sel_ram_pc), .ind(ind),
        .idx(idx), .ext(ext), .xop_ld(xop_ld), .rf_we2(rf_we2),
        .addr_alu(addr_alu), .flag_ld(flag_ld), .sel_ram_fl(sel_ram_fl),
        .pair16_ld(pair16_ld), .pair16_hi(pair16_hi),
        .pc_from_vec(pc_from_vec), .flag_i_set(flag_i_set),
        .flag_i_clear(flag_i_clear), .flag_save(flag_save),
        .flag_restore(flag_restore), .sel_in(sel_in), .io_op(io_op),
        .halted(halted)
    );

    // --- State encodings (mirror rtl/control.v) ---
    localparam [2:0] S_FETCH = 3'd0;
    localparam [2:0] S_OPR   = 3'd1;
    localparam [2:0] S_EXEC  = 3'd2;
    localparam [2:0] S_IRQ   = 3'd3;
    localparam [2:0] S_HLT   = 3'd4;
    localparam [2:0] S_OPR2  = 3'd5;
    localparam [2:0] S_EXEC2 = 3'd6;

    // --- Instruction decode helpers (same definitions as the RTL) ---
    wire [3:0] opcode = instr[7:4];
    wire [3:0] fop    = fetched[7:4];
    wire       is_ext = (instr == 8'hFA);
    wire       is_hlt = (instr == 8'hF0);
    wire       needs_operand =
        (fop == 4'h1) || (fop == 4'h3) || (fop == 4'h4) ||
        (fop == 4'hC) || (fop == 4'hD) ||
        (fetched == 8'hF4) || (fetched == 8'hF5) ||
        (fetched == 8'hF6) || (fetched == 8'hF7) ||
        (fetched == 8'hF8) || (fetched == 8'hF9) ||
        (fetched == 8'hFA);

    // ---------------------------------------------------------------
    // Trace initialisation: reset is asserted at time 0.
    // ---------------------------------------------------------------
    initial assume (rst);

    reg f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    // ===============================================================
    // Combinational invariants (hold for every reachable state and
    // every input). State 7 is reserved and unreachable: the state
    // register has no init, and Yosys models it as 0 at time 0.
    // ===============================================================

    // The next-state function never produces the reserved encoding.
    always @* assert (nstate_obs != 3'd7);

    // A corrupted state recovers to S_FETCH.
    always @* assert (state_obs != 3'd7 || nstate_obs == S_FETCH);

    // halted is exactly "the FSM is in S_HLT".
    always @* assert (halted == (state_obs == S_HLT));

    // Mutually exclusive control outputs (no branch of the RTL enables both).
    always @* assert (!(sp_inc && sp_dec));
    always @* assert (!(pc_inc && pc_load));
    always @* assert (!(ir_ld && opr_ld));
    always @* assert (!(ram_we && rf_we));
    always @* assert (!(pc_from_vec && pc_from_mem));
    always @* assert (!(sel_ram_pc && sel_ram_rs));

    // Outputs are only asserted in the states that use them.
    always @* assert (!ir_ld        || state_obs == S_FETCH);
    always @* assert (!opr_ld       || state_obs == S_OPR || state_obs == S_OPR2);
    always @* assert (!xop_ld       || state_obs == S_OPR);
    always @* assert (!pc_as_addr   || state_obs == S_FETCH ||
                                        state_obs == S_OPR   ||
                                        state_obs == S_OPR2);
    always @* assert (!pc_inc       || state_obs == S_FETCH ||
                                        state_obs == S_OPR   ||
                                        state_obs == S_OPR2);
    always @* assert (!pc_load      || state_obs == S_EXEC || state_obs == S_IRQ);
    always @* assert (!pc_from_vec  || state_obs == S_IRQ);
    always @* assert (!flag_save    || state_obs == S_IRQ);
    always @* assert (!flag_restore || state_obs == S_EXEC);
    always @* assert (!rf_we        || state_obs == S_EXEC || state_obs == S_EXEC2);
    always @* assert (!rf_we2       || state_obs == S_EXEC);
    always @* assert (!ram_we       || state_obs == S_EXEC || state_obs == S_IRQ);
    always @* assert (!sp_dec       || state_obs == S_EXEC || state_obs == S_IRQ);
    always @* assert (!sp_inc       || state_obs == S_EXEC);
    always @* assert (!sp_as_addr   || state_obs == S_EXEC || state_obs == S_IRQ);
    always @* assert (!pair16_ld    || state_obs == S_EXEC);
    always @* assert (!pair16_hi    || state_obs == S_EXEC2);
    always @* assert (!flag_i_set   || state_obs == S_EXEC);
    always @* assert (!flag_ld      || state_obs == S_EXEC);
    always @* assert (!out_wr       || state_obs == S_EXEC);
    always @* assert (!addr_alu     || state_obs == S_EXEC);
    always @* assert (!ext          || state_obs == S_EXEC || state_obs == S_EXEC2);

    // ===============================================================
    // Sequential properties.  An immediate assertion inside an
    // `always @(posedge clk)` block samples the pre-edge value, so
    // `$past(x)` refers to the previous cycle and the current
    // `state_obs` is the value produced by the previous edge.
    // ===============================================================
    always @(posedge clk) begin
        if (f_past_valid) begin

            // --- Reset (synchronous, active high) ---
            if ($past(rst)) assert (state_obs == S_FETCH);

            // --- Reachable state set: 7 is never entered ---
            assert (state_obs != 3'd7);

            // --- S_HLT stutters until reset ---
            if ($past(state_obs == S_HLT) && !$past(rst))
                assert (state_obs == S_HLT);
            if (state_obs == S_HLT) assert (nstate_obs == S_HLT);
            if (state_obs == S_HLT)
                assert (!ir_ld && !pc_inc && !pc_load && !ram_we && !rf_we);

            // --- Legal transition set from each state (derived from RTL) ---

            // S_FETCH: IRQ only if interrupts are enabled and requested;
            // otherwise OPR when the fetched byte carries an operand, else EXEC.
            if (state_obs == S_FETCH) begin
                if (flag_i && irq) assert (nstate_obs == S_IRQ);
                else               assert (nstate_obs != S_IRQ);
                if (!(flag_i && irq)) begin
                    if (needs_operand) assert (nstate_obs == S_OPR);
                    else                   assert (nstate_obs == S_EXEC);
                end
            end

            // S_OPR: prefixed LDW/STW (subop 7/8) need a third byte, else EXEC.
            if (state_obs == S_OPR) begin
                if (is_ext && (fop == 4'h7 || fop == 4'h8))
                    assert (nstate_obs == S_OPR2);
                else
                    assert (nstate_obs == S_EXEC);
            end

            // S_OPR2: always EXEC.
            if (state_obs == S_OPR2) assert (nstate_obs == S_EXEC);

            // S_EXEC: EXEC2 for ADCW/SUBW, HLT for 0xF0, otherwise FETCH.
            if (state_obs == S_EXEC) begin
                if (is_ext && (xsub == 4'hC || xsub == 4'hD))
                    assert (nstate_obs == S_EXEC2);
                else if (is_hlt)
                    assert (nstate_obs == S_HLT);
                else
                    assert (nstate_obs == S_FETCH);
                assert (nstate_obs == S_FETCH ||
                        nstate_obs == S_HLT   ||
                        nstate_obs == S_EXEC2);
            end

            // S_EXEC2: always FETCH.
            if (state_obs == S_EXEC2) assert (nstate_obs == S_FETCH);

            // S_IRQ: always FETCH and performs the interrupt entry actions.
            if (state_obs == S_IRQ) begin
                assert (nstate_obs == S_FETCH);
                assert (ram_we && sp_dec && !sp_inc);
                assert (pc_load && pc_from_vec);
                assert (flag_i_clear && flag_save);
            end

            // S_IRQ is only ever produced by S_FETCH with flag_i && irq:
            // no other state is allowed to request the interrupt cycle.
            if (state_obs != S_FETCH) assert (nstate_obs != S_IRQ);
        end
    end

    // ===============================================================
    // Covers: reachable states and transitions. They are checked by
    // control_cover.sby, because BMC removes $cover cells.
    // ===============================================================
    always @(posedge clk) begin
        if (f_past_valid && state_obs == S_FETCH) cover (1'b1);
        if (f_past_valid && state_obs == S_OPR) cover (1'b1);
        if (f_past_valid && state_obs == S_OPR2) cover (1'b1);
        if (f_past_valid && state_obs == S_EXEC) cover (1'b1);
        if (f_past_valid && state_obs == S_EXEC2) cover (1'b1);
        if (f_past_valid && state_obs == S_IRQ) cover (1'b1);
        if (f_past_valid && state_obs == S_HLT) cover (1'b1);

        // Interesting transitions.
        if (f_past_valid && state_obs == S_FETCH && nstate_obs == S_OPR)
            cover (1'b1);
        if (f_past_valid && state_obs == S_OPR   && nstate_obs == S_EXEC)
            cover (1'b1);
        if (f_past_valid && state_obs == S_EXEC  && nstate_obs == S_FETCH)
            cover (1'b1);
        if (f_past_valid && state_obs == S_FETCH && nstate_obs == S_IRQ && flag_i && irq)
            cover (1'b1);
        if (f_past_valid && state_obs == S_IRQ   && nstate_obs == S_FETCH)
            cover (1'b1);
        if (f_past_valid && state_obs == S_EXEC  && nstate_obs == S_EXEC2)
            cover (1'b1);
        if (f_past_valid && state_obs == S_EXEC  && nstate_obs == S_HLT)
            cover (1'b1);

        // A stack operation (PUSH rs or CALL) in S_EXEC.
        if (f_past_valid && state_obs == S_EXEC && ram_we && sp_dec && sp_as_addr &&
               (opcode == 4'h0 ? (instr[3:2] == 2'b10) : sel_ram_pc))
            cover (1'b1);
    end

endmodule

`default_nettype wire
