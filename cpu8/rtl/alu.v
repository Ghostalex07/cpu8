// ============================================================================
//  alu.v - 8-bit Arithmetic-Logic Unit
//
//  It is a COMBINATIONAL block (it has no clock): it receives two operands and
//  an operation selector, and returns the result and the flags.
//
//  The `op` selector uses the SAME codes as the ISA opcode field
//  (ADD=5, SUB=6, AND=7, OR=8, XOR=9, CMP=A, SHL/SHR=B) so that the control
//  unit can connect IR[7:4] directly.
//
//  All additions/subtractions are done in 9 bits (8 + 1 carry) so as not to
//  lose the carry-out of bit 7.
//
//  Convention for C in subtraction (see docs/ISA.md §5): subtraction is
//  a + ~b + 1, so C (the carry-out of bit 7) is 1 when there is NO borrow
//  (a >= b) and 0 when there is one (a < b).
//
//  Flag V (signed overflow, two's complement): V = c7 ^ c8 for ADD/SUB/CMP; for
//  the other operations it is 0.  It enables signed comparisons (§6).
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module alu (
    input  wire [3:0] op,   // operation (see the localparams below)
    input  wire       sh,   // SHL/SHR only: 0 = SHL (left), 1 = SHR (right)
    input  wire [7:0] a,    // operand 1 (usually rd)
    input  wire [7:0] b,    // operand 2 (rs or immediate)
    output reg  [7:0] y,    // result
    output reg        c,    // flag C: carry (add) / no-borrow (subtract)
    output reg        v,    // flag V: SIGNED overflow (two's complement)
    output wire       z,    // flag Z: result is zero
    output wire       n     // flag N: copy of bit 7 (sign in two's complement)
);

    // Operation codes. They intentionally match the ISA opcode.
    localparam [3:0] ALU_ADD = 4'h5;
    localparam [3:0] ALU_SUB = 4'h6;
    localparam [3:0] ALU_AND = 4'h7;
    localparam [3:0] ALU_OR  = 4'h8;
    localparam [3:0] ALU_XOR = 4'h9;
    localparam [3:0] ALU_CMP = 4'hA;
    localparam [3:0] ALU_SHIFT = 4'hB; // covers SHL and SHR (`sh` tells them apart)
    localparam [3:0] ALU_MUL = 4'hC;   // MUL rd,rs (Phase 9): rd <- (rd*rs)[7:0]
    localparam [3:0] ALU_DIV = 4'hD;   // DIV rd,rs (Phase 9): rd <- rd/rs

    // --- Combinational computations ---
    // A SINGLE 9-bit adder serves both ADD and SUB/CMP:
    //   ADD:     a + b + 0
    //   SUB/CMP: a + ~b + 1   (the same adder with b inverted and cin = 1).
    // This way synthesis implements a single carry chain instead of two.
    wire       es_resta   = (op == ALU_SUB) || (op == ALU_CMP);
    wire [8:0] b_efectivo = es_resta ? {1'b0, ~b} : {1'b0, b};
    wire [8:0] suma       = {1'b0, a} + b_efectivo + {8'b0, es_resta};

    // 1-bit shift (uses only operand A).
    wire [7:0] desl   = sh ? (a >> 1) : (a << 1);
    wire       c_desl = sh ? a[0] : a[7]; // bit that "falls out" of the end

    // 8x8 multiplication -> 16 (MUL).  The low byte is used and C indicates
    // whether the result does not fit in 8 bits (high byte != 0).
    wire [15:0] producto = a * b;

    // Unsigned integer division (DIV).  b==0 -> 0 and C=1 (error), so the
    // result is deterministic (in Verilog, a/0 is x).
    wire        div0     = (b == 8'h00);
    wire [7:0]  cociente = div0 ? 8'h00 : (a / b);

    always @(*) begin
        // Default values: they avoid latches and define the "pass-through"
        // case, which the control unit will use for LDI/MOV (the value is in b).
        y = b;
        c = 1'b0;
        v = 1'b0;   // V only makes sense for ADD/SUB/CMP; elsewhere it is 0

        case (op)
            ALU_ADD,
            ALU_SUB,
            ALU_CMP:      begin
                y = suma[7:0];
                c = suma[8];
                // Signed overflow (two's complement).  It only differs between
                // add and subtract in the term with the operand signs:
                //   ADD:     V = ~(a7^b7) & (a7^y7)
                //   SUB/CMP: V =  (a7^b7) & (a7^y7)
                // E.g.: 0x7F+0x01 = 0x80 -> V=1;  0x80-0x01 = 0x7F -> V=1.
                v = es_resta ? ((a[7] ^ b[7]) & (a[7] ^ y[7]))
                             : (~(a[7] ^ b[7]) & (a[7] ^ y[7]));
            end
            ALU_AND:      begin y = a & b;                  end
            ALU_OR:       begin y = a | b;                  end
            ALU_XOR:      begin y = a ^ b;                  end
            ALU_SHIFT:    begin y = desl;       c = c_desl;  end
            ALU_MUL:      begin y = producto[7:0]; c = |producto[15:8]; end
            ALU_DIV:      begin y = cociente;   c = div0;    end
            default:      begin y = b;          c = 1'b0;    end // pass-through
        endcase
    end

    // Flags that depend only on the result.
    assign z = (y == 8'h00);
    assign n = y[7];

endmodule

`default_nettype wire
