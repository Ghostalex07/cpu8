// ============================================================================
//  irq_tb.v - Interrupt testbench (Phase 7.5)
//
//  Same as cpu_tb.v but additionally:
//    - instantiates the CPU with IRQ_VECTOR = 0x10,
//  and - keeps the irq input high after the reset.
//
//  The program (by default programs/irq.hex, or +hex=<path>) enables the
//  interrupts with EI; since I goes low after servicing the first one, only
//  one is serviced even if irq stays high.  The output is compared with +exp.
//
//  Generates build/irq_tb.vcd to see it in GTKWave.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module irq_tb;

    reg clk = 0, rst = 1;
    reg irq = 0;        // interrupt request level

    wire       halted, out_valid;
    wire [7:0] out_data;

    wire [1:0] in_port;
    wire [7:0] in_data = 8'h10 + {6'b0, in_port};

    cpu #(.IRQ_VECTOR(8'h10)) dut (
        .clk(clk), .rst(rst), .irq(irq),
        .halted(halted), .out_data(out_data), .out_valid(out_valid),
        .in_data(in_data), .in_port(in_port)
    );

    always #5 clk = ~clk;

    reg [1023:0] hexfile;
    reg [1023:0] expfile;
    integer nlen;
    integer errors = 0, nout = 0, i;
    reg use_exp;

    reg [7:0] expmem [0:255];
    integer   nexp;

    task contar_tokens;
        input  [1023:0] fname;
        output integer  n;
        integer fdd, c;
        reg     in_t;
        begin
            n = 0;
            in_t = 0;
            fdd = $fopen(fname, "r");
            if (fdd == 0) begin
                $display("ERROR: could not open %0s", fname);
                $fatal(1, "file not found");
            end
            c = $fgetc(fdd);
            while (c != -1) begin
                if (c == 32 || c == 9 || c == 10 || c == 13) in_t = 0;
                else if (!in_t) begin in_t = 1; n = n + 1; end
                c = $fgetc(fdd);
            end
            $fclose(fdd);
        end
    endtask

    initial begin
        if (!$value$plusargs("hex=%s", hexfile))
            hexfile = "programs/irq.hex";

        $dumpfile("build/irq_tb.vcd");
        $dumpvars(0, irq_tb);

        contar_tokens(hexfile, nlen);
        if (nlen == 0) begin
            $display("ERROR: the program %0s is empty", hexfile);
            $fatal(1, "empty program");
        end
        // RAM at 0 before loading (positions not covered by the .hex).
        for (i = 0; i < 256; i = i + 1) dut.u_ram.mem[i] = 8'h00;
        $readmemh(hexfile, dut.u_ram.mem, 0, nlen - 1);

        use_exp = $value$plusargs("exp=%s", expfile);
        nexp    = 0;
        if (use_exp) begin
            contar_tokens(expfile, nexp);
            if (nexp == 0) begin
                $display("ERROR: the expected list %0s is empty", expfile);
                $fatal(1, "empty expected list");
            end
            $readmemh(expfile, expmem, 0, nexp - 1);
        end

        $display("=== IRQ simulation (program %0s, %0d bytes) ===", hexfile, nlen);

        // Synchronous reset 2 cycles and, afterwards, irq high throughout the test.
        rst = 1;
        repeat (2) @(posedge clk);
        @(negedge clk) begin rst = 0; irq = 1; end

        i = 0;
        while (!halted && i < 500000) begin
            @(posedge clk);
            #1;
            if (out_valid) begin
                if (nout < nexp) begin
                    if (out_data !== expmem[nout]) begin
                        $display("  OUT[%0d] = %0d   EXPECTED %0d   <-- WRONG",
                                 nout, out_data, expmem[nout]);
                        errors = errors + 1;
                    end else begin
                        $display("  OUT[%0d] = %0d   ok", nout, out_data);
                    end
                end else begin
                    $display("  OUT[%0d] = %0d   <-- extra output", nout, out_data);
                    errors = errors + 1;
                end
                nout = nout + 1;
            end
            i = i + 1;
        end

        if (!halted) begin
            $display("  FAIL: the CPU did not reach HLT (possible infinite loop)");
            errors = errors + 1;
        end

        $display("  Outputs emitted: %0d (expected: %0d)", nout, nexp);
        if (nout !== nexp) errors = errors + 1;

        if (errors == 0) $display("IRQ: ALL TESTS PASSED");
        else             $display("IRQ: %0d FAILURES", errors);

        if (errors != 0) $fatal(1, "IRQ: there are failures, check above");
        $finish;
    end

endmodule

`default_nettype wire
