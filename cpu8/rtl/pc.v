// ============================================================================
//  pc.v - Contador de Programa (Program Counter) de 8 bits
//
//  Registro síncrono con tres acciones EXCLUYENTES, en orden de prioridad:
//    1) rst  -> PC = 0                (reset síncrono, activo alto)
//    2) load -> PC = d_in             (saltos: JMP / Jcc toman el destino)
//    3) inc  -> PC = PC + 1           (instrucción siguiente)
//    4) (ninguna) -> mantiene el valor
//
//  La unidad de control nunca activará `load` e `inc` a la vez; si lo hiciera,
//  gana `load` por este orden.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module pc (
    input  wire       clk,
    input  wire       rst,
    input  wire       load,
    input  wire       inc,
    input  wire [7:0] d_in,
    output reg  [7:0] q
);

    always @(posedge clk) begin
        if (rst)        q <= 8'h00;
        else if (load)  q <= d_in;
        else if (inc)   q <= q + 8'd1;
        // si no, mantiene el valor (no se escribe => no hace falta rama else)
    end

endmodule

`default_nettype wire
