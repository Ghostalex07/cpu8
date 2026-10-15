// ============================================================================
//  alu_tb.v - Exhaustive testbench for the ALU
//
//  1) Directed cases: manual check of operations and flags (including the
//     carry and borrow corner cases).
//  2) Exhaustive sweep: walks the 256x256 pairs of operands for ADD and
//     SUB, comparing against an "oracle" model computed in the testbench
//     itself with 32-bit integers (independent of the RTL implementation).
//
//  If something fails, it prints the case, counts the errors and ends with
//  $fatal (so that `make test` really fails).
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module alu_tb;

    // Inputs to the DUT
    reg  [3:0] op;
    reg        sh;
    reg        cin = 0;
    reg  [7:0] a, b;

    // DUT outputs
    wire [7:0] y;
    wire       c, v, z, n;

    integer errors = 0;
    integer i, j, k;
    integer isum, isub;
    reg [7:0] t;   // temporary result to build oracles

    // Instance of the module under test
    alu dut (
        .op(op), .sh(sh), .a(a), .b(b), .cin(cin),
        .y(y), .c(c), .v(v), .z(z), .n(n)
    );

    // ------------------------------------------------------------------
    // Check task: applies op/sh/a/b, waits 1 ns and compares EVERYTHING.
    // ------------------------------------------------------------------
    task check;
        input [3:0] top;
        input       tsh;
        input [7:0] va, vb;
        input [7:0] ey;
        input       ec, ez, en;
        begin
            op = top; sh = tsh; cin = 1'b0; a = va; b = vb; #1;
            if ((y !== ey) || (c !== ec) || (z !== ez) || (n !== en)) begin
                errors = errors + 1;
                $display("  FAIL op=%0d sh=%b a=%02h b=%02h -> y=%02h c=%b z=%b n=%b  (expected y=%02h c=%b z=%b n=%b)",
                         top, tsh, va, vb, y, c, z, n, ey, ec, ez, en);
            end
        end
    endtask

    // Check task that also verifies flag V (signed overflow).  It is used in
    // the arithmetic cases (ADD/SUB/CMP).
    task check_v;
        input [3:0] top;
        input       tsh;
        input [7:0] va, vb;
        input [7:0] ey;
        input       ec, ez, en, ev;
        begin
            op = top; sh = tsh; cin = 1'b0; a = va; b = vb; #1;
            if ((y !== ey) || (c !== ec) || (z !== ez) || (n !== en) || (v !== ev)) begin
                errors = errors + 1;
                $display("  FAIL op=%0d sh=%b a=%02h b=%02h -> y=%02h c=%b v=%b z=%b n=%b  (expected y=%02h c=%b v=%b z=%b n=%b)",
                         top, tsh, va, vb, y, c, v, z, n, ey, ec, ev, ez, en);
            end
        end
    endtask

    // Check task with carry-in (used by the extended ADC/SBC/ROL/ROR ops).
    task check_ac;
        input [3:0] top;
        input       tsh;
        input       tcin;
        input [7:0] va, vb;
        input [7:0] ey;
        input       ec, ez, en, ev;
        begin
            op = top; sh = tsh; cin = tcin; a = va; b = vb; #1;
            if ((y !== ey) || (c !== ec) || (z !== ez) || (n !== en) || (v !== ev)) begin
                errors = errors + 1;
                $display("  FAIL op=%0d sh=%b cin=%b a=%02h b=%02h -> y=%02h c=%b v=%b z=%b n=%b  (expected y=%02h c=%b v=%b z=%b n=%b)",
                         top, tsh, tcin, va, vb, y, c, v, z, n, ey, ec, ev, ez, en);
            end
        end
    endtask

    initial begin
        $display("=== ALU testbench ===");

        // ------------------------------------------------------------
        // 1) Directed cases
        // ------------------------------------------------------------
        $display("-- ADD --");
        check(4'h5, 0, 8'h05, 8'h03, 8'h08, 1'b0, 1'b0, 1'b0); // 5+3=8
        check(4'h5, 0, 8'hFF, 8'h01, 8'h00, 1'b1, 1'b1, 1'b0); // 255+1=0, C=1, Z=1
        check(4'h5, 0, 8'h7F, 8'h01, 8'h80, 1'b0, 1'b0, 1'b1); // 127+1=128, N=1
        check(4'h5, 0, 8'h80, 8'h80, 8'h00, 1'b1, 1'b1, 1'b0); // 128+128=0, C=1
        check(4'h5, 0, 8'h00, 8'h00, 8'h00, 1'b0, 1'b1, 1'b0); // 0+0=0, Z=1

        $display("-- Flag V (signed overflow, two's complement) --");
        check_v(4'h5, 0, 8'h7F, 8'h01, 8'h80, 1'b0, 1'b0, 1'b1, 1'b1); //  127 +  1 = -128 -> V=1
        check_v(4'h5, 0, 8'hFF, 8'h02, 8'h01, 1'b1, 1'b0, 1'b0, 1'b0); //   -1 +  2 =    1 -> V=0
        check_v(4'h5, 0, 8'h80, 8'hFF, 8'h7F, 1'b1, 1'b0, 1'b0, 1'b1); // -128 + -1 =  127 -> V=1
        check_v(4'h5, 0, 8'hC0, 8'hC0, 8'h80, 1'b1, 1'b0, 1'b1, 1'b0); //  -64 + -64 = -128 -> V=0
        check_v(4'h6, 0, 8'h80, 8'h01, 8'h7F, 1'b1, 1'b0, 1'b0, 1'b1); // -128 -  1 =  127 -> V=1
        check_v(4'h6, 0, 8'h7F, 8'hFF, 8'h80, 1'b0, 1'b0, 1'b1, 1'b1); //  127 - -1 = -128 -> V=1
        check_v(4'h6, 0, 8'h05, 8'h03, 8'h02, 1'b1, 1'b0, 1'b0, 1'b0); //    5 -  3 =    2 -> V=0
        check_v(4'hA, 0, 8'h80, 8'h01, 8'h7F, 1'b1, 1'b0, 1'b0, 1'b1); // CMP -128,1 -> V=1

        $display("-- SUB / CMP (C=1 => no borrow, a>=b) --");
        check(4'h6, 0, 8'h05, 8'h03, 8'h02, 1'b1, 1'b0, 1'b0); // 5-3=2,  no borrow
        check(4'h6, 0, 8'h03, 8'h05, 8'hFE, 1'b0, 1'b0, 1'b1); // 3-5=-2, borrow
        check(4'h6, 0, 8'h05, 8'h05, 8'h00, 1'b1, 1'b1, 1'b0); // 5-5=0,  no borrow, Z=1
        check(4'h6, 0, 8'h00, 8'h01, 8'hFF, 1'b0, 1'b0, 1'b1); // 0-1=-1, borrow
        check(4'hA, 0, 8'h03, 8'h05, 8'hFE, 1'b0, 1'b0, 1'b1); // CMP gives the diff and flags
        check(4'hA, 0, 8'h07, 8'h07, 8'h00, 1'b1, 1'b1, 1'b0);

        $display("-- AND / OR / XOR (C=0) --");
        check(4'h7, 0, 8'hF0, 8'h0F, 8'h00, 1'b0, 1'b1, 1'b0);
        check(4'h7, 0, 8'hFF, 8'h80, 8'h80, 1'b0, 1'b0, 1'b1);
        check(4'h8, 0, 8'hF0, 8'h0F, 8'hFF, 1'b0, 1'b0, 1'b1);
        check(4'h8, 0, 8'h00, 8'h00, 8'h00, 1'b0, 1'b1, 1'b0);
        check(4'h9, 0, 8'hFF, 8'hFF, 8'h00, 1'b0, 1'b1, 1'b0);
        check(4'h9, 0, 8'hAA, 8'h55, 8'hFF, 1'b0, 1'b0, 1'b1);

        $display("-- SHL (C = previous bit7) --");
        check(4'hB, 0, 8'h81, 8'h00, 8'h02, 1'b1, 1'b0, 1'b0); // 1000_0001 -> 0000_0010, C=1
        check(4'hB, 0, 8'h40, 8'h00, 8'h80, 1'b0, 1'b0, 1'b1); // 0100_0000 -> 1000_0000
        check(4'hB, 0, 8'h80, 8'h00, 8'h00, 1'b1, 1'b1, 1'b0); // 1000_0000 -> 0000_0000, C=1, Z=1
        check(4'hB, 0, 8'h00, 8'h00, 8'h00, 1'b0, 1'b1, 1'b0);

        $display("-- SHR (C = previous bit0) --");
        check(4'hB, 1, 8'h01, 8'h00, 8'h00, 1'b1, 1'b1, 1'b0); // 0000_0001 -> 0000_0000, C=1, Z=1
        check(4'hB, 1, 8'h80, 8'h00, 8'h40, 1'b0, 1'b0, 1'b0); // 1000_0000 -> 0100_0000
        check(4'hB, 1, 8'hFF, 8'h00, 8'h7F, 1'b1, 1'b0, 1'b0); // 1111_1111 -> 0111_1111, C=1
        check(4'hB, 1, 8'h02, 8'h00, 8'h01, 1'b0, 1'b0, 1'b0);

        // ------------------------------------------------------------
        // 2) Exhaustive sweep with an independent oracle
        //    (oracle computed in the testbench, unrelated to the implementation)
        // ------------------------------------------------------------
        $display("-- Exhaustive sweep ADD / SUB / CMP (65536 pairs) --");
        for (i = 0; i < 256; i = i + 1) begin
            for (j = 0; j < 256; j = j + 1) begin
                isum = i + j;                       // oracle ADD (32 bits)
                // C = carry-out of bit 7 of a+b  <=>  isum >= 256  <=>  isum[8]
                // V = signed overflow: same signs and different result.
                check_v(4'h5, 0, i[7:0], j[7:0],
                      isum[7:0], isum[8], (isum[7:0] == 0), isum[7],
                      ((i[7] == j[7]) && (isum[7] != i[7])));

                isub = i - j;                       // oracle SUB / CMP
                // C = 1 if there is NO borrow (a>=b) = carry-out of a+~b+1
                // V = signed overflow: different signs and result != a.
                check_v(4'h6, 0, i[7:0], j[7:0],
                      isub[7:0], (i >= j), (isub[7:0] == 0), isub[7],
                      ((i[7] != j[7]) && (isub[7] != i[7])));
                check_v(4'hA, 0, i[7:0], j[7:0],     // CMP: same diff and flags
                      isub[7:0], (i >= j), (isub[7:0] == 0), isub[7],
                      ((i[7] != j[7]) && (isub[7] != i[7])));
            end
        end

        $display("-- Exhaustive sweep AND / OR / XOR (65536 pairs) --");
        for (i = 0; i < 256; i = i + 1) begin
            for (j = 0; j < 256; j = j + 1) begin
                // Bit-by-bit oracle (Verilog operators, independent of the ALU)
                t = i[7:0] & j[7:0];
                check(4'h7, 0, i[7:0], j[7:0], t, 1'b0, (t == 0), t[7]);
                t = i[7:0] | j[7:0];
                check(4'h8, 0, i[7:0], j[7:0], t, 1'b0, (t == 0), t[7]);
                t = i[7:0] ^ j[7:0];
                check(4'h9, 0, i[7:0], j[7:0], t, 1'b0, (t == 0), t[7]);
            end
        end

        $display("-- Exhaustive sweep SHL / SHR (256 values) --");
        for (i = 0; i < 256; i = i + 1) begin
            t = i[7:0] << 1;            // SHL truncated to 8 bits: C = previous bit7
            check(4'hB, 0, i[7:0], 8'h00, t, i[7], (t == 0), t[7]);
            t = i[7:0] >> 1;            // SHR: C = previous bit0
            check(4'hB, 1, i[7:0], 8'h00, t, i[0], (t == 0), t[7]);
        end

        // ------------------------------------------------------------
        // MUL / DIV (Phase 9).  V does not take part (always 0).
        // ------------------------------------------------------------
        $display("-- MUL (directed) --");
        check_v(4'hC, 0, 8'h07, 8'h06, 8'h2A, 1'b0, 1'b0, 1'b0, 1'b0); // 7*6=42
        check_v(4'hC, 0, 8'h14, 8'h14, 8'h90, 1'b1, 1'b0, 1'b1, 1'b0); // 20*20=400 -> 0x90, C=1
        check_v(4'hC, 0, 8'h00, 8'h07, 8'h00, 1'b0, 1'b1, 1'b0, 1'b0); // 0*7=0, Z=1
        check_v(4'hC, 0, 8'hFF, 8'hFF, 8'h01, 1'b1, 1'b0, 1'b0, 1'b0); // 255*255=65025 -> 0x01, C=1

        $display("-- DIV (directed) --");
        check_v(4'hD, 0, 8'hC8, 8'h07, 8'h1C, 1'b0, 1'b0, 1'b0, 1'b0); // 200/7=28
        check_v(4'hD, 0, 8'h64, 8'h03, 8'h21, 1'b0, 1'b0, 1'b0, 1'b0); // 100/3=33
        check_v(4'hD, 0, 8'h09, 8'h00, 8'h00, 1'b1, 1'b1, 1'b0, 1'b0); // 9/0 -> 0, C=1
        check_v(4'hD, 0, 8'h05, 8'h08, 8'h00, 1'b0, 1'b1, 1'b0, 1'b0); // 5/8=0, Z=1

        $display("-- Exhaustive sweep MUL (65536 pairs) --");
        for (i = 0; i < 256; i = i + 1) begin
            for (j = 0; j < 256; j = j + 1) begin
                t = (i * j) & 8'hFF;   // product truncated to 8 bits
                check_v(4'hC, 0, i[7:0], j[7:0],
                        t, ((i * j) > 255), (t == 0), t[7], 1'b0);
            end
        end

        $display("-- Exhaustive sweep DIV (65536 pairs) --");
        for (i = 0; i < 256; i = i + 1) begin
            for (j = 0; j < 256; j = j + 1) begin
                if (j == 0) t = 8'h00;         // division by zero -> 0
                else        t = (i / j) & 8'hFF;
                check_v(4'hD, 0, i[7:0], j[7:0],
                        t, (j == 0), (t == 0), t[7], 1'b0);
            end
        end

        // ------------------------------------------------------------
        // Extended ALU operations (prefix 0xFA): NEG, NOT, ADC, SBC, ROL, ROR
        // ------------------------------------------------------------
        $display("-- NEG (0 - a) --");
        check_ac(4'h0, 0, 0, 8'h01, 8'h00, 8'hFF, 1'b0, 1'b0, 1'b1, 1'b0); // -1
        check_ac(4'h0, 0, 0, 8'h00, 8'h00, 8'h00, 1'b1, 1'b1, 1'b0, 1'b0); // 0 -> C=1,Z=1
        check_ac(4'h0, 0, 0, 8'h80, 8'h00, 8'h80, 1'b0, 1'b0, 1'b1, 1'b1); // -128 -> V=1
        check_ac(4'h0, 0, 0, 8'h7F, 8'h00, 8'h81, 1'b0, 1'b0, 1'b1, 1'b0);

        $display("-- NOT (~a; C=0, V=0) --");
        check_ac(4'h3, 0, 0, 8'h00, 8'h00, 8'hFF, 1'b0, 1'b0, 1'b1, 1'b0);
        check_ac(4'h3, 0, 0, 8'hFF, 8'h00, 8'h00, 1'b0, 1'b1, 1'b0, 1'b0);
        check_ac(4'h3, 0, 0, 8'hAA, 8'h00, 8'h55, 1'b0, 1'b0, 1'b0, 1'b0);

        $display("-- ROL / ROR (through carry) --");
        check_ac(4'hE, 0, 1'b0, 8'h81, 8'h00, 8'h02, 1'b1, 1'b0, 1'b0, 1'b0); // ROL 81 -> 02
        check_ac(4'hE, 0, 1'b1, 8'h80, 8'h00, 8'h01, 1'b1, 1'b0, 1'b0, 1'b0); // ROL, enter C
        check_ac(4'hE, 1, 1'b0, 8'h01, 8'h00, 8'h00, 1'b1, 1'b1, 1'b0, 1'b0); // ROR 01 -> 00
        check_ac(4'hE, 1, 1'b1, 8'h00, 8'h00, 8'h80, 1'b0, 1'b0, 1'b1, 1'b0); // ROR, enter C

        $display("-- ADC / SBC (directed) --");
        check_ac(4'h4, 0, 1'b0, 8'h05, 8'h03, 8'h08, 1'b0, 1'b0, 1'b0, 1'b0); // 5+3+0
        check_ac(4'h4, 0, 1'b1, 8'h05, 8'h03, 8'h09, 1'b0, 1'b0, 1'b0, 1'b0); // 5+3+1
        check_ac(4'h4, 0, 1'b1, 8'hFF, 8'h00, 8'h00, 1'b1, 1'b1, 1'b0, 1'b0); // 255+0+1
        check_ac(4'h4, 1, 1'b0, 8'h05, 8'h03, 8'h02, 1'b1, 1'b0, 1'b0, 1'b0); // 5-3-0
        check_ac(4'h4, 1, 1'b1, 8'h05, 8'h03, 8'h01, 1'b1, 1'b0, 1'b0, 1'b0); // 5-3-1
        check_ac(4'h4, 1, 1'b0, 8'h03, 8'h05, 8'hFE, 1'b0, 1'b0, 1'b1, 1'b0); // 3-5 borrow

        $display("-- Exhaustive sweep ADC / SBC (65536 pairs x 2 carry) --");
        for (i = 0; i < 256; i = i + 1) begin
            for (j = 0; j < 256; j = j + 1) begin
                for (k = 0; k < 2; k = k + 1) begin
                    isum = i + j + k;                 // ADC oracle (32-bit)
                    check_ac(4'h4, 0, k[0], i[7:0], j[7:0],
                             isum[7:0], isum[8], (isum[7:0] == 0), isum[7],
                             ((i[7] == j[7]) && (isum[7] != i[7])));
                    isub = i - j - k;                 // SBC oracle (32-bit signed)
                    check_ac(4'h4, 1, k[0], i[7:0], j[7:0],
                             isub[7:0], (isub >= 0), (isub[7:0] == 0), isub[7],
                             ((i[7] != j[7]) && (isub[7] != i[7])));
                end
            end
        end

        $display("-- Exhaustive sweep NEG / ROL / ROR (256 x 2 carry) --");
        for (i = 0; i < 256; i = i + 1) begin
            t = (256 - i) & 8'hFF;                    // NEG oracle
            check_ac(4'h0, 0, 0, i[7:0], 8'h00, t, (i == 0), (t == 0), t[7], (i == 128));
            for (k = 0; k < 2; k = k + 1) begin
                t = ((i[7:0] << 1) | k[0]);           // ROL oracle
                check_ac(4'hE, 0, k[0], i[7:0], 8'h00, t[7:0], i[7], (t[7:0] == 0), t[7], 1'b0);
                t = ((k[0] << 7) | (i[7:0] >> 1));    // ROR oracle
                check_ac(4'hE, 1, k[0], i[7:0], 8'h00, t[7:0], i[0], (t[7:0] == 0), t[7], 1'b0);
            end
        end

        // ------------------------------------------------------------
        // Summary
        // ------------------------------------------------------------
        if (errors == 0)
            $display("ALU: ALL TESTS PASSED");
        else
            $display("ALU: %0d FAILURES", errors);

        if (errors != 0) $fatal(1, "ALU: there are failures, check above");
        $finish;
    end

endmodule

`default_nettype wire
