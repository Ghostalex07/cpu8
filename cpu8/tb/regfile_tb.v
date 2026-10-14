// ============================================================================
//  regfile_tb.v - Register file testbench
//
//  Checks:
//    1) The synchronous reset leaves all four registers at 0.
//    2) Write and read of each register.
//    3) `we=0` does not modify any register.
//    4) The two read ports are independent.
//    5) Writing and reading the same register in the same cycle: before the
//       edge the old value is read, after it the new one.
//    6) A second reset clears everything again.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module regfile_tb;

    reg clk = 0;
    reg rst = 0, we = 0;
    reg [1:0] waddr = 0, raddr1 = 0, raddr2 = 0;
    reg [7:0] wdata = 0;
    wire [7:0] rdata1, rdata2;

    integer errors = 0;

    regfile dut (
        .clk(clk), .rst(rst), .we(we), .waddr(waddr), .wdata(wdata),
        .raddr1(raddr1), .raddr2(raddr2), .rdata1(rdata1), .rdata2(rdata2)
    );

    // 10 ns clock (rising edge every 5 ns).
    always #5 clk = ~clk;

    // Applies a one-cycle synchronous reset.
    task do_reset;
        begin
            rst = 1; @(posedge clk); #1; rst = 0;
        end
    endtask

    // Writes `val` to register `idx` for one cycle.
    task wr;
        input [1:0] idx;
        input [7:0] val;
        begin
            we = 1; waddr = idx; wdata = val; @(posedge clk); #1; we = 0;
        end
    endtask

    // Reads port 1 and compares with the expected value.
    task chk1;
        input [1:0] idx;
        input [7:0] exp;
        begin
            raddr1 = idx; #1;
            if (rdata1 !== exp) begin
                errors = errors + 1;
                $display("  FAIL rdata1[R%0d]=%02h (expected %02h)", idx, rdata1, exp);
            end
        end
    endtask

    // Reads port 2 and compares with the expected value.
    task chk2;
        input [1:0] idx;
        input [7:0] exp;
        begin
            raddr2 = idx; #1;
            if (rdata2 !== exp) begin
                errors = errors + 1;
                $display("  FAIL rdata2[R%0d]=%02h (expected %02h)", idx, rdata2, exp);
            end
        end
    endtask

    initial begin
        $display("=== Register file testbench ===");

        // 1) Reset: everything to 0.
        do_reset;
        chk1(2'd0, 8'h00); chk1(2'd1, 8'h00); chk1(2'd2, 8'h00); chk1(2'd3, 8'h00);

        // 2) Write and read of each register.
        wr(2'd0, 8'h11);
        wr(2'd1, 8'h22);
        wr(2'd2, 8'h33);
        wr(2'd3, 8'h44);
        chk1(2'd0, 8'h11); chk1(2'd1, 8'h22); chk1(2'd2, 8'h33); chk1(2'd3, 8'h44);

        // 3) we=0 must not change anything (attempt to write A=0xFF).
        we = 0; waddr = 2'd0; wdata = 8'hFF; @(posedge clk); #1;
        chk1(2'd0, 8'h11);

        // 4) The two read ports are independent.
        raddr1 = 2'd1; raddr2 = 2'd3; #1;
        if (rdata1 !== 8'h22) begin errors = errors + 1; $display("  FAIL port1=%02h", rdata1); end
        if (rdata2 !== 8'h44) begin errors = errors + 1; $display("  FAIL port2=%02h", rdata2); end

        // 5) Writing and reading the same register in the same cycle:
        //    before the edge the old value (0x11) is read; after it, the new one.
        raddr2 = 2'd0; we = 1; waddr = 2'd0; wdata = 8'h99; #1;
        if (rdata2 !== 8'h11) begin errors = errors + 1; $display("  FAIL old value=%02h", rdata2); end
        @(posedge clk); #1; we = 0;
        chk2(2'd0, 8'h99);

        // 6) Second reset.
        do_reset;
        chk1(2'd0, 8'h00); chk1(2'd3, 8'h00);

        if (errors == 0)
            $display("REGFILE: ALL TESTS PASSED");
        else
            $display("REGFILE: %0d FAILURES", errors);

        if (errors != 0) $fatal(1, "REGFILE: there are failures, check above");
        $finish;
    end

endmodule

`default_nettype wire
