// ============================================================================
//  cpu_tb.v - Full CPU testbench
//
//  Loads a .hex program into RAM (by default programs/fase4.hex, or the one
//  passed with +hex=<path>), releases the reset and runs until the CPU
//  executes HLT.  It collects everything that comes out through the OUT port.
//
//  If +exp=<path> is passed, it compares each output with the expected list in
//  that file (one hex value per line, no comments).  Without +exp it only
//  prints the outputs, without checking anything.
//
//  It also generates build/cpu_tb.vcd to see the fetch/decode/execute cycle in
//  GTKWave.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module cpu_tb;

    reg clk = 0, rst = 1;

    wire       halted, out_valid;
    wire [7:0] out_data;

    // Input: value of the port requested by the IN instruction (port 0 -> 0x10,
    // port 1 -> 0x11, ...).  Only programs with IN use it.
    wire [1:0] in_port;
    wire [7:0] in_data = 8'h10 + {6'b0, in_port};

    cpu dut (
        .clk(clk), .rst(rst), .irq(1'b0),
        .halted(halted), .out_data(out_data), .out_valid(out_valid),
        .in_data(in_data), .in_port(in_port)
    );

    always #5 clk = ~clk;

    reg [1023:0] hexfile;
    reg [1023:0] expfile;
    integer nlen;
    integer errors = 0, nout = 0, i;
    reg use_exp;

    // Expected outputs read from +exp (in hex by $readmemh).  The
    // unused positions stay at 'x' so that they can be counted.
    reg [7:0] expmem [0:255];
    integer   nexp;

    // Counts how many "tokens" (words separated by whitespace) there are in a
    // text file.  We use it to know how many bytes the program has
    // and how many expected outputs there are, and thus load only that range
    // with $readmemh (avoids the "Not enough words..." warning).
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
            hexfile = "programs/fase4.hex";

        // Waveforms for GTKWave.
        $dumpfile("build/cpu_tb.vcd");
        $dumpvars(0, cpu_tb);

        // --- How many bytes the program has (to load only that range) ---
        // $fscanf("%h") does not work in iverilog 11, so we count words
        // by reading the file character by character: each byte of the .hex is a token.
        contar_tokens(hexfile, nlen);
        if (nlen == 0) begin
            $display("ERROR: the program %0s is empty", hexfile);
            $fatal(1, "empty program");
        end
        // Leaves RAM at 0 before loading: the positions not covered by the
        // .hex would stay at 'x' and any read of uninitialized data
        // would be indeterminate.  With 0 the behaviour is deterministic.
        for (i = 0; i < 256; i = i + 1) dut.u_ram.mem[i] = 8'h00;
        $readmemh(hexfile, dut.u_ram.mem, 0, nlen - 1);

        // --- Expected outputs (+exp) ---
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

        $display("=== CPU simulation (program %0s, %0d bytes) ===", hexfile, nlen);

        // Synchronous reset 2 cycles.
        rst = 1;
        repeat (2) @(posedge clk);
        @(negedge clk) rst = 0;

        // Loop with timeout until HLT, collecting the OUT outputs.
        i = 0;
        while (!halted && i < 500000) begin
            @(posedge clk);
            #1;
            if (out_valid) begin
                if (use_exp) begin
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
                end else begin
                    $display("  OUT[%0d] = %0d", nout, out_data);
                end
                nout = nout + 1;
            end
            i = i + 1;
        end

        if (!halted) begin
            $display("  FAIL: the CPU did not reach HLT (possible infinite loop)");
            errors = errors + 1;
        end

        if (use_exp) begin
            $display("  Outputs emitted: %0d (expected: %0d)", nout, nexp);
            if (nout !== nexp) errors = errors + 1;
        end else begin
            $display("  Outputs emitted: %0d (no expected list, not compared)", nout);
        end

        if (errors != 0)      $display("CPU: %0d FAILURES", errors);
        else if (use_exp)     $display("CPU: ALL TESTS PASSED");
        else                  $display("CPU: NO EXPECTED LIST (nothing compared)");

        if (errors != 0) $fatal(1, "CPU: there are failures, check above");
        $finish;
    end

endmodule

`default_nettype wire
