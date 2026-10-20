// ============================================================================
//  alu_fv.sv - Formal equivalence check of rtl/alu.v
//
//  The reference model below is written with plain Verilog operators (+, -,
//  *, /, shifts) and does NOT follow the implementation (no shared 9-bit
//  adder, no `es_resta` tricks).  The assertions compare every output of the
//  RTL against it for all possible inputs, so they cover all 16 `op` codes,
//  both shift directions and all 2^8 x 2^8 x 2 operand combinations.
//
//  Run with `make formal` (SymbiYosys, see formal/alu.sby).
// ============================================================================
`default_nettype none

module alu_fv (
    input wire [3:0] op,
    input wire       sh,
    input wire [7:0] a,
    input wire [7:0] b,
    input wire       cin
);

    wire [7:0] y;
    wire       c, v, z, n;

    alu dut (
        .op(op), .sh(sh), .a(a), .b(b), .cin(cin),
        .y(y), .c(c), .z(z), .n(n), .v(v)
    );

    reg [7:0]  ry;
    reg        rc, rv;
    reg [8:0]  suma;
    reg [15:0] producto;

    always @* begin
        // Defaults (pass-through case: LDI/MOV and reserved `op` codes).
        ry = b;
        rc = 1'b0;
        rv = 1'b0;

        case (op)
            4'h5: begin  // ADD
                suma = {1'b0, a} + {1'b0, b};
                ry   = suma[7:0];
                rc   = suma[8];
                rv   = (a[7] == b[7]) && (ry[7] != a[7]);
            end
            4'h6, 4'hA: begin  // SUB / CMP
                // 9-bit subtraction: bit 8 is the BORROW, so C (no borrow)
                // is its complement.
                suma = {1'b0, a} - {1'b0, b};
                ry   = suma[7:0];
                rc   = ~suma[8];
                rv   = (a[7] != b[7]) && (ry[7] != a[7]);
            end
            4'h7: ry = a & b;
            4'h8: ry = a | b;
            4'h9: ry = a ^ b;
            4'hB: begin  // SHL / SHR
                ry = sh ? (a >> 1) : (a << 1);
                rc = sh ? a[0] : a[7];
            end
            4'hC: begin  // MUL
                producto = a * b;
                ry = producto[7:0];
                rc = |producto[15:8];
            end
            4'hD: begin  // DIV
                if (b == 8'h00) begin
                    ry = 8'h00;
                    rc = 1'b1;      // division by zero sets C
                end else begin
                    ry = a / b;
                end
            end
            4'h0: begin  // NEG
                suma = 9'h000 - {1'b0, a};
                ry   = suma[7:0];
                rc   = ~suma[8];    // 1 when a == 0 (no borrow)
                rv   = (a == 8'h80);
            end
            4'h3: ry = ~a;          // NOT
            4'h4: begin  // ADC (sh=0) / SBC (sh=1)
                if (!sh) begin
                    suma = {1'b0, a} + {1'b0, b} + cin;
                end else begin
                    suma = {1'b0, a} - {1'b0, b} - cin;
                end
                ry = suma[7:0];
                rc = sh ? ~suma[8] : suma[8];
                rv = sh ? ((a[7] != b[7]) && (ry[7] != a[7]))
                        : ((a[7] == b[7]) && (ry[7] != a[7]));
            end
            4'hE: begin  // ROL (sh=0) / ROR (sh=1), both through carry
                ry = sh ? {cin, a[7:1]} : {a[6:0], cin};
                rc = sh ? a[0] : a[7];
            end
            default: ;  // pass-through
        endcase

        assert (y == ry);
        assert (c == rc);
        assert (v == rv);
        assert (z == (ry == 8'h00));
        assert (n == ry[7]);
    end

endmodule

`default_nettype wire
