// ============================================================================
//  regfile.v - Banco de registros de propósito general (A, B, C, D)
//
//  Cuatro registros de 8 bits. Tiene:
//    - 1 puerto de ESCRITURA síncrono (en flanco de subida), con permiso `we`.
//    - 2 puertos de LECTURA combinacionales, para poder leer a la vez `rd` y
//      `rs` (la ALU necesita ambos operandos en el mismo ciclo).
//
//  El reset es SÍNCRONO (activo alto) y deja los cuatro registros a 0.
//
//  Índices de registro (coinciden con el campo rd/rs de la ISA):
//    A = 00, B = 01, C = 10, D = 11
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module regfile (
    input  wire       clk,     // reloj del sistema
    input  wire       rst,     // reset síncrono, activo alto
    input  wire       we,      // permiso de escritura
    input  wire [1:0] waddr,   // índice del registro destino
    input  wire [7:0] wdata,   // dato a escribir
    input  wire [1:0] raddr1,  // dirección del puerto de lectura 1 (rs)
    input  wire [1:0] raddr2,  // dirección del puerto de lectura 2 (rd)
    output wire [7:0] rdata1,  // valor del registro raddr1
    output wire [7:0] rdata2   // valor del registro raddr2
);

    // Nombres simbólicos de los índices de registro.
    localparam [1:0] R_A = 2'b00;
    localparam [1:0] R_B = 2'b01;
    localparam [1:0] R_C = 2'b10;
    localparam [1:0] R_D = 2'b11;

    // Los cuatro registros. `regs[i]` es el registro de índice i.
    reg [7:0] regs [0:3];

    // Escritura y reset, ambos SÍNCRONOS (solo cambian en flanco de subida).
    // El reset tiene prioridad sobre la escritura.
    always @(posedge clk) begin
        if (rst) begin
            regs[R_A] <= 8'h00;
            regs[R_B] <= 8'h00;
            regs[R_C] <= 8'h00;
            regs[R_D] <= 8'h00;
        end else if (we) begin
            regs[waddr] <= wdata;
        end
    end

    // Lectura combinacional: el valor aparece en cuanto cambia la dirección.
    assign rdata1 = regs[raddr1];
    assign rdata2 = regs[raddr2];

endmodule

`default_nettype wire
