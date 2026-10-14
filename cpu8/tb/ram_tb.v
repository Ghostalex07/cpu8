// ============================================================================
//  ram_tb.v - RAM testbench
//
//  Checks:
//    1) Loading with $readmemh leaves the values of the .hex in memory.
//    2) Synchronous write + registered read (on the falling edge) at several
//       addresses.
//    3) Rewriting a position previously loaded by $readmemh.
//    4) `we=0` does not modify the memory.
//
//  The read is registered on the FALLING edge (mem[addr] -> rdata), so
//  the data is available mid-cycle to the datapath, which registers
//  on the rising edge.  That is why `chk` waits for the falling edge before
//  checking rdata.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module ram_tb;

    reg clk = 0, we = 0;
    reg [7:0] addr = 0, wdata = 0;
    wire [7:0] rdata;

    integer errors = 0;

    ram dut (
        .clk(clk), .we(we), .addr(addr), .wdata(wdata), .rdata(rdata)
    );

    always #5 clk = ~clk;

    // Reads address `a` (waits for the falling edge: registered read) and
    // compares with the expected value.
    task chk;
        input [7:0] a;
        input [7:0] exp;
        begin
            addr = a; @(negedge clk); #1;
            if (rdata !== exp) begin
                errors = errors + 1;
                $display("  FAIL RAM[%02h]=%02h (expected %02h)", a, rdata, exp);
            end
        end
    endtask

    // Writes `d` to address `a` for one cycle.
    task wr;
        input [7:0] a;
        input [7:0] d;
        begin
            we = 1; addr = a; wdata = d; @(posedge clk); #1; we = 0;
        end
    endtask

    initial begin
        $display("=== RAM testbench ===");

        // 1) Load with $readmemh (hierarchical access to the internal memory).
        //    We specify the range [0:7] so as not to warn that the .hex has
        //    fewer than 256 words.
        $readmemh("tb/ram_init.hex", dut.mem, 0, 7);
        chk(8'h00, 8'hA5);
        chk(8'h01, 8'h5A);
        chk(8'h02, 8'h00);
        chk(8'h03, 8'hFF);
        chk(8'h04, 8'h12);
        chk(8'h07, 8'h78);

        // 2) Synchronous write and registered read.
        wr(8'h10, 8'hDE);
        chk(8'h10, 8'hDE);
        wr(8'hFF, 8'h42);
        chk(8'hFF, 8'h42);

        // 3) Rewrite of a position loaded by $readmemh.
        wr(8'h00, 8'h11);
        chk(8'h00, 8'h11);

        // 4) we=0 must not change anything.
        we = 0; addr = 8'h10; wdata = 8'h00; @(posedge clk); #1;
        chk(8'h10, 8'hDE);

        if (errors == 0)
            $display("RAM: ALL TESTS PASSED");
        else
            $display("RAM: %0d FAILURES", errors);

        if (errors != 0) $fatal(1, "RAM: there are failures, check above");
        $finish;
    end

endmodule

`default_nettype wire
