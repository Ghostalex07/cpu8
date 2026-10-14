// ============================================================================
//  ram.v - Memoria de datos/programa (von Neumann) de 256 x 8 bits
//
//  Un único puerto:
//    - ESCRITURA síncrona (en flanco de subida y solo si `we` = 1).
//    - LECTURA registrada en flanco de BAJADA: el dato aparece a mitad de ciclo
//      y queda disponible para el datapath (que registra en flanco de subida)
//      antes del próximo posedge.  Es transparente para el CPU (ve el dato en
//      el mismo ciclo en que direcciona), pero permite mapear la memoria a las
//      BRAM de la iCE40 (SB_RAM40_4K), que tienen reloj de lectura propio, en
//      lugar de usar lógica distribuida (ver fpga, Fase 7.6).
//
//  La memoria se inicializa con `$readmemh("archivo.hex", ram.mem)`, que carga
//  un byte por línea (formato que generará nuestro ensamblador). No tiene reset:
//  el contenido es el que cargue $readmemh (o indefinido si no se carga).
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module ram (
    input  wire       clk,     // reloj del sistema
    input  wire       we,      // permiso de escritura (activo alto)
    input  wire [7:0] addr,    // dirección (0..255)
    input  wire [7:0] wdata,   // dato a escribir
    output reg  [7:0] rdata    // dato leído (registrado en flanco de bajada)
);

    // 256 posiciones de 8 bits.
`ifdef FPGA_RAM64
    reg [7:0] mem [0:63];
`else
    reg [7:0] mem [0:255];
`endif

`ifdef RAM_INIT
    // Inicializacion SOLO para sintesis en FPGA (Fase 7.6): carga el programa
    // desde "fpga/program.hex".  En iverilog y Verilator NO se define RAM_INIT,
    // asi que el testbench cargue la RAM como siempre.
    initial $readmemh("fpga/program.hex", mem);
`endif

    // Escritura síncrona.
    always @(posedge clk) begin
        if (we) mem[addr] <= wdata;
    end

    // Lectura registrada en flanco de bajada (media latencia de ciclo): el
    // datapath registra en posedge, así que ve mem[addr] en el mismo ciclo.
    always @(negedge clk) begin
        rdata <= mem[addr];
    end

endmodule

`default_nettype wire
