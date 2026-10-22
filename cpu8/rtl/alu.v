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
//  Extended operations (prefixed instructions, byte1 = 0xFA, see docs/ISA.md)
//  use the codes that do not collide with an opcode whose ALU result is used:
//  NEG=0, NOT=3, ADC/SBC=4, ROL/ROR=E.  They are selected explicitly by
//  control.v and never as a direct pass-through of an opcode nibble.
//
//  All additions/subtractions are done in 9 bits (8 + 1 carry) so as not to
//  lose the carry-out of bit 7.
//
//  Convention for C in subtraction (see docs/ISA.md §5): subtraction is
//  a + ~b + 1, so C (the carry-out of bit 7) is 1 when there is NO borrow
//  (a >= b) and 0 when there is one (a < b).  SBC uses the same adder with b
//  inverted and cin = ~carry_in, so that C = 1 means a >= b + carry_in.
//
//  Flag V (signed overflow, two's complement): V = c7 ^ c8 for ADD/SUB/CMP; for
//  the other operations it is 0.  It enables signed comparisons (§6).
//
//  `cin` is the carry/borrow input for ADC/SBC and the bit rotated in by
//  ROL/ROR (it is connected to flag C by cpu.v).
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module alu (
    input  wire [3:0] op,      // operation (see the localparams below)
    input  wire       sh,      // SHL/SHR direction; also ADC/SBC and ROL/ROR select
    input  wire [7:0] a,       // operand 1 (usually rd)
    input  wire [7:0] b,       // operand 2 (rs or immediate)
    input  wire       cin,     // carry/borrow in (ADC/SBC) and C for ROL/ROR
    output reg  [7:0] y,       // result
    output wire [7:0] y_addr,  // dedicated a+b, used for RAM addresses
    output reg        c,       // flag C: carry (add) / no-borrow (subtract)
    output reg        v,       // flag V: SIGNED overflow (two's complement)
    output wire       z,       // flag Z: result is zero
    output wire       n        // flag N: copy of bit 7 (sign in two's complement)
);

  // Operation codes. They intentionally match the ISA opcode.
  localparam [3:0] ALU_ADD = 4'h5;
  localparam [3:0] ALU_SUB = 4'h6;
  localparam [3:0] ALU_AND = 4'h7;
  localparam [3:0] ALU_OR = 4'h8;
  localparam [3:0] ALU_XOR = 4'h9;
  localparam [3:0] ALU_CMP = 4'hA;
  localparam [3:0] ALU_SHIFT = 4'hB;  // covers SHL and SHR (`sh` tells them apart)
  localparam [3:0] ALU_MUL = 4'hC;  // MUL rd,rs (Phase 9): rd <- (rd*rs)[7:0]
  localparam [3:0] ALU_DIV = 4'hD;  // DIV rd,rs (Phase 9): rd <- rd/rs

  // Extended operations (prefix 0xFA).  These codes are free because the
  // opcodes that share their number never use the ALU result (see control.v).
  localparam [3:0] ALU_NEG = 4'h0;  // NEG rd   : y = 0 - a
  localparam [3:0] ALU_NOT = 4'h3;  // NOT rd   : y = ~a
  localparam [3:0] ALU_ADC_SBC = 4'h4;  // sh=0 ADC: a+b+cin ; sh=1 SBC: a-b-cin
  localparam [3:0] ALU_ROT = 4'hE;  // sh=0 ROL, sh=1 ROR (through carry)

  // --- Combinational computations ---
  // A SINGLE 9-bit adder serves both ADD and SUB/CMP:
  //   ADD:     a + b + 0
  //   SUB/CMP: a + ~b + 1   (the same adder with b inverted and cin = 1).
  // This way synthesis implements a single carry chain instead of two.
  wire       es_resta = (op == ALU_SUB) || (op == ALU_CMP);
  wire [7:0] b_efectivo = es_resta ? ~b : b;
  wire [8:0] suma = {1'b0, a} + {1'b0, b_efectivo} + {8'b0, es_resta};

  // Dedicated address adder: LDW/STW only need a+b for ram_addr.  Keeping
  // this path out of the `y` mux removes the multiplier/divider from the
  // RAM-address timing cone.
  assign y_addr = a + b;

  // ADC/SBC: the same 9-bit adder with the incoming carry.  SBC (sh=1) is
  // a - b - cin = a + ~b + (1 - cin), that is, b inverted and cin inverted.
  wire [ 7:0] b_adcsbc = sh ? ~b : b;
  wire        cin_adcsbc = sh ? ~cin : cin;
  wire [ 8:0] suma_adcsbc = {1'b0, a} + {1'b0, b_adcsbc} + {8'b0, cin_adcsbc};

  // NEG: 0 - a with the same convention (C=1 only when a=0, i.e. no borrow).
  wire [ 8:0] suma_neg = {1'b0, 8'h00} + {1'b0, ~a} + 9'd1;

  // 1-bit shift (uses only operand A).
  wire [ 7:0] desl = sh ? (a >> 1) : (a << 1);
  wire        c_desl = sh ? a[0] : a[7];  // bit that "falls out" of the end

  // Rotations THROUGH the carry: the bit that enters is `cin` (flag C).
  wire [ 7:0] rot = sh ? {cin, a[7:1]} : {a[6:0], cin};
  wire        c_rot = sh ? a[0] : a[7];

  // 8x8 multiplication -> 16 (MUL).  The low byte is used and C indicates
  // whether the result does not fit in 8 bits (high byte != 0).
  wire [15:0] producto = a * b;

  // Unsigned integer division (DIV).  b==0 -> 0 and C=1 (error), so the
  // result is deterministic (in Verilog, a/0 is x).
  wire        div0 = (b == 8'h00);
  wire [ 7:0] cociente = div0 ? 8'h00 : (a / b);

  always @(*) begin
    // Default values: they avoid latches and define the "pass-through"
    // case, which the control unit will use for LDI/MOV (the value is in b).
    y = b;
    c = 1'b0;
    v = 1'b0;  // V only makes sense for ADD/SUB/CMP; elsewhere it is 0

    case (op)
      ALU_ADD, ALU_SUB, ALU_CMP: begin
        y = suma[7:0];
        c = suma[8];
        // Signed overflow (two's complement).  It only differs between
        // add and subtract in the term with the operand signs:
        //   ADD:     V = ~(a7^b7) & (a7^y7)
        //   SUB/CMP: V =  (a7^b7) & (a7^y7)
        // E.g.: 0x7F+0x01 = 0x80 -> V=1;  0x80-0x01 = 0x7F -> V=1.
        v = es_resta ? ((a[7] ^ b[7]) & (a[7] ^ y[7])) : (~(a[7] ^ b[7]) & (a[7] ^ y[7]));
      end
      ALU_AND: begin
        y = a & b;
      end
      ALU_OR: begin
        y = a | b;
      end
      ALU_XOR: begin
        y = a ^ b;
      end
      ALU_SHIFT: begin
        y = desl;
        c = c_desl;
      end
      ALU_MUL: begin
        y = producto[7:0];
        c = |producto[15:8];
      end
      ALU_DIV: begin
        y = cociente;
        c = div0;
      end
      ALU_NEG: begin
        y = suma_neg[7:0];
        c = suma_neg[8];  // 1 only when a==0 (no borrow)
        v = a[7] & y[7];  // -128 -> -128 is the only overflow
      end
      ALU_NOT: begin
        y = ~a;
        c = 1'b0;
        v = 1'b0;
      end
      ALU_ADC_SBC: begin
        y = suma_adcsbc[7:0];
        c = suma_adcsbc[8];
        // SBC is a subtraction (same V term as SUB); ADC as ADD.
        v = sh ? ((a[7] ^ b[7]) & (a[7] ^ y[7])) : (~(a[7] ^ b[7]) & (a[7] ^ y[7]));
      end
      ALU_ROT: begin
        y = rot;
        c = c_rot;
        v = 1'b0;
      end
      default: begin
        y = b;
        c = 1'b0;
      end  // pass-through
    endcase
  end

  // Flags that depend only on the result.
  assign z = (y == 8'h00);
  assign n = y[7];

endmodule

`default_nettype wire
