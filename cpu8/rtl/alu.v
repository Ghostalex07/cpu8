// ============================================================================
//  alu.v - Unidad Aritmético-Lógica de 8 bits
//
//  Es un bloque COMBINACIONAL (no tiene reloj): recibe dos operandos y un
//  selector de operación, y devuelve el resultado y los flags.
//
//  El selector `op` usa los MISMOS códigos que el campo opcode de la ISA
//  (ADD=5, SUB=6, AND=7, OR=8, XOR=9, CMP=A, SHL/SHR=B) para que la unidad
//  de control pueda conectar directamente IR[7:4].
//
//  Todas las sumas/restas se hacen en 9 bits (8 + 1 de acarreo) para no perder
//  el carry-out del bit 7.
//
//  Convenio de C en la resta (ver docs/ISA.md §5): la resta es a + ~b + 1, así
//  que C (el carry-out del bit 7) vale 1 cuando NO hay borrow (a >= b) y 0
//  cuando sí lo hay (a < b).
//
//  Flag V (desbordamiento con signo, Ca2): V = c7 ^ c8 para ADD/SUB/CMP; en el
//  resto de operaciones vale 0.  Permite comparaciones con signo (§6).
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module alu (
    input  wire [3:0] op,   // operación (ver localparams de abajo)
    input  wire       sh,   // solo SHL/SHR: 0 = SHL (izquierda), 1 = SHR (derecha)
    input  wire [7:0] a,    // operando 1 (normalmente rd)
    input  wire [7:0] b,    // operando 2 (rs o inmediato)
    output reg  [7:0] y,    // resultado
    output reg        c,    // flag C: acarreo (suma) / no-borrow (resta)
    output reg        v,    // flag V: desbordamiento CON SIGNO (Ca2)
    output wire       z,    // flag Z: resultado cero
    output wire       n     // flag N: copia del bit 7 (signo en Ca2)
);

    // Códigos de operación. Coinciden a propósito con el opcode de la ISA.
    localparam [3:0] ALU_ADD = 4'h5;
    localparam [3:0] ALU_SUB = 4'h6;
    localparam [3:0] ALU_AND = 4'h7;
    localparam [3:0] ALU_OR  = 4'h8;
    localparam [3:0] ALU_XOR = 4'h9;
    localparam [3:0] ALU_CMP = 4'hA;
    localparam [3:0] ALU_SHIFT = 4'hB; // cubre SHL y SHR (los distingue `sh`)
    localparam [3:0] ALU_MUL = 4'hC;   // MUL rd,rs (Fase 9): rd <- (rd*rs)[7:0]
    localparam [3:0] ALU_DIV = 4'hD;   // DIV rd,rs (Fase 9): rd <- rd/rs

    // --- Cálculos combinacionales ---
    // Un ÚNICO sumador de 9 bits sirve para ADD y para SUB/CMP:
    //   ADD:     a + b + 0
    //   SUB/CMP: a + ~b + 1   (el mismo sumador con b invertido y cin = 1).
    // Así la síntesis implementa un solo acarreo-propagado en vez de dos.
    wire       es_resta   = (op == ALU_SUB) || (op == ALU_CMP);
    wire [8:0] b_efectivo = es_resta ? {1'b0, ~b} : {1'b0, b};
    wire [8:0] suma       = {1'b0, a} + b_efectivo + {8'b0, es_resta};

    // Desplazamiento de 1 bit (usa solo el operando A).
    wire [7:0] desl   = sh ? (a >> 1) : (a << 1);
    wire       c_desl = sh ? a[0] : a[7]; // bit que "sale" por el extremo

    // Multiplicacion 8x8 -> 16 (MUL).  Se usa el byte bajo y C indica si el
    // resultado no cabe en 8 bits (byte alto != 0).
    wire [15:0] producto = a * b;

    // Division entera sin signo (DIV).  b==0 -> 0 y C=1 (error), asi el
    // resultado es determinista (en Verilog, a/0 es x).
    wire        div0     = (b == 8'h00);
    wire [7:0]  cociente = div0 ? 8'h00 : (a / b);

    always @(*) begin
        // Valores por defecto: evitan latches y definen el caso "pass-through",
        // que la unidad de control usará para LDI/MOV (el valor va en b).
        y = b;
        c = 1'b0;
        v = 1'b0;   // V solo tiene sentido en ADD/SUB/CMP; en el resto vale 0

        case (op)
            ALU_ADD,
            ALU_SUB,
            ALU_CMP:      begin
                y = suma[7:0];
                c = suma[8];
                // Desbordamiento con signo (Ca2).  Solo difiere entre suma y
                // resta en el termino de los signos de los operandos:
                //   ADD:     V = ~(a7^b7) & (a7^y7)
                //   SUB/CMP: V =  (a7^b7) & (a7^y7)
                // Ej.: 0x7F+0x01 = 0x80 -> V=1;  0x80-0x01 = 0x7F -> V=1.
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

    // Flags que dependen solo del resultado.
    assign z = (y == 8'h00);
    assign n = y[7];

endmodule

`default_nettype wire
