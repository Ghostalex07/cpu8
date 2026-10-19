`timescale 1ns/1ps
`default_nettype none
// ============================================================================
//  cpu_trace_tb.v - Trace debugger (Phase 9)
//
//  Runs a program and shows ONE line per retired instruction, with the
//  CPU state *after* executing it:
//
//      PC   IR   A  B  C  D   Z C N V  SP
//
//  Usage (via `make trace PROG=programs/xxx`):
//      vvp build/trace.vvp +hex=programs/xxx.hex
//
//  It is not part of `make test`: it is an interactive debugging tool.
// ============================================================================

module cpu_trace_tb;

    reg clk = 0, rst = 1, irq = 0;
    reg [7:0] in_data = 8'h00;      // fixed input (port 0..3 -> same value)
    wire       halted, out_valid;
    wire [7:0] out_data;
    wire [1:0] in_port, out_port;

    cpu dut (
        .clk(clk), .rst(rst), .irq(irq),
        .halted(halted), .out_data(out_data), .out_valid(out_valid),
        .in_data(in_data), .in_port(in_port), .out_port(out_port)
    );

    always #5 clk = ~clk;

    reg [8*256-1:0] hexfile;
    integer n = 0;
    localparam integer MAX_INSTR = 20000;   // safety cap

    initial begin
        if (!$value$plusargs("hex=%s", hexfile)) hexfile = "programs/countdown.hex";
        if (!$value$plusargs("in=%d", in_data)) in_data = 8'h00;
        $readmemh(hexfile, dut.u_ram.mem);
        $display("=== trace of %0s ===", hexfile);
        $display("    PC   IR   A    B    C    D    Z C N V  SP");
        rst = 1;
        repeat (2) @(posedge clk);
        @(negedge clk) rst = 0;
    end

    // PC of the current instruction: latched when the IR is loaded (S_FETCH).
    reg [7:0] trace_pc;
    always @(posedge clk) if (dut.ir_ld) trace_pc <= dut.pc_q;

    // An instruction "retires" on the rising edge in which S_EXEC is executed
    // (state 3'd2).  It is detected on the following negedge, when the registers
    // and flags are already updated.  Pair ops (ADCW/SUBW) spend one extra
    // cycle in S_EXEC2 (3'd6), so their sample is deferred one negedge further.
    reg [2:0] st_d = 3'd0;
    localparam [2:0] S_EXEC  = 3'd2,
                     S_EXEC2 = 3'd6;
    always @(negedge clk) begin
        if (rst) begin
            st_d <= dut.u_ctrl.state;
        end else begin
            if ((st_d == S_EXEC && dut.u_ctrl.state != S_EXEC2) || st_d == S_EXEC2) begin
                $display("  %02h   %02h   %02h   %02h   %02h   %02h   %b %b %b %b  %02h%s",
                         trace_pc, dut.IR,
                         dut.u_rf.regs[0], dut.u_rf.regs[1],
                         dut.u_rf.regs[2], dut.u_rf.regs[3],
                         dut.flag_z, dut.flag_c, dut.flag_n, dut.flag_v, dut.SP,
                         out_valid ? "   OUT" : "");
                n = n + 1;
                if (n >= MAX_INSTR) begin
                    $display("(cap of %0d instructions reached)", MAX_INSTR);
                    $finish;
                end
            end
            st_d <= dut.u_ctrl.state;
            if (halted) begin
                if (out_valid) $display("    (LAST OUT: %02h on port %0d)", out_data, out_port);
                $display("(HLT after %0d instructions)", n);
                $finish;
            end
        end
    end

endmodule

`default_nettype wire
