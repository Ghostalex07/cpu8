`timescale 1ns/1ps
`default_nettype none
// ============================================================================
//  top.v - Implementacion en FPGA (Fase 7.6) para la iCEstick (iCE40HX1K, TQ144)
//
//  Es la "placa": instancia la CPU, genera el reset de encendido a partir del
//  reloj y muestra las 5 salidas OUT de menor peso en los 5 LEDs.
//
//  El programa se carga en la RAM del CPU al sintetizar: ram.v incluye un
//  $readmemh("fpga/program.hex") bajo `ifdef RAM_INIT` (lo define el Makefile).
// ============================================================================
module top (
    input  wire       clk,        // reloj de 12 MHz (pin 21 en la iCEstick)
    output wire [4:0] led         // 5 LEDs (D1..D5)
);

    // Reset de encendido: rst=1 durante los primeros 8 ciclos tras arrancar.
    reg [3:0] por = 4'd0;
    wire rst = ~por[3];

    always @(posedge clk)
        if (!por[3]) por <= por + 4'd1;

    // La CPU (sin interrupciones en esta demo).
    wire        halted;
    wire        out_valid;
    wire [7:0]  out_data;
    wire [1:0]  in_port;

    cpu #(.IRQ_VECTOR(8'h08)) cpu_i (
        .clk(clk),
        .rst(rst),
        .irq(1'b0),
        .halted(halted),
        .out_data(out_data),
        .out_valid(out_valid),
        .in_data(8'h00),      // sin entradas cableadas en esta demo
        .in_port(in_port)
    );

    // Los 5 LEDs muestran los bits bajos del ultimo valor enviado por OUT.
    // Si la CPU ha parado (HLT), se encienden todos.
    assign led = halted ? 5'b11111 : out_data[4:0];

endmodule

`default_nettype wire
