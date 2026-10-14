// ============================================================================
//  cpu_tb.v - Testbench de la CPU completa
//
//  Carga un programa .hex en la RAM (por defecto programs/fase4.hex, o el que
//  se pase con +hex=<ruta>), suelta el reset y ejecuta hasta que la CPU
//  ejecuta HLT.  Recoge todo lo que sale por el puerto OUT.
//
//  Si se pasa +exp=<ruta>, compara cada salida con la lista esperada que hay
//  en ese fichero (un valor hex por linea, sin comentarios).  Sin +exp solo
//  imprime las salidas, sin comprobar nada.
//
//  Tambien genera build/cpu_tb.vcd para ver el ciclo fetch/decode/execute en
//  GTKWave.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module cpu_tb;

    reg clk = 0, rst = 1;

    wire       halted, out_valid;
    wire [7:0] out_data;

    // Entrada: valor del puerto pedido por la instruccion IN (puerto 0 -> 0x10,
    // puerto 1 -> 0x11, ...).  Solo lo usan los programas con IN.
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

    // Salidas esperadas leidas de +exp (en hexadecimal por $readmemh).  Las
    // posiciones no usadas se quedan en 'x' para poder contarlas.
    reg [7:0] expmem [0:255];
    integer   nexp;

    // Cuenta cuantos "tokens" (palabras separadas por blancos) hay en un
    // fichero de texto.  Lo usamos para saber cuantos bytes tiene el programa
    // y cuantas salidas esperadas hay, y asi cargar solo ese rango con
    // $readmemh (evita el aviso "Not enough words...").
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
                $display("ERROR: no se pudo abrir %0s", fname);
                $fatal(1, "fichero no encontrado");
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

        // Formas de onda para GTKWave.
        $dumpfile("build/cpu_tb.vcd");
        $dumpvars(0, cpu_tb);

        // --- Cuantos bytes tiene el programa (para cargar solo ese rango) ---
        // $fscanf("%h") no funciona en iverilog 11, asi que contamos palabras
        // leyendo el fichero caracter a caracter: cada byte del .hex es un token.
        contar_tokens(hexfile, nlen);
        if (nlen == 0) begin
            $display("ERROR: el programa %0s esta vacio", hexfile);
            $fatal(1, "programa vacio");
        end
        // Deja la RAM a 0 antes de cargar: las posiciones no cubiertas por el
        // .hex quedarian en 'x' y cualquier lectura de datos no inicializados
        // seria indeterminada.  Con 0 el comportamiento es determinista.
        for (i = 0; i < 256; i = i + 1) dut.u_ram.mem[i] = 8'h00;
        $readmemh(hexfile, dut.u_ram.mem, 0, nlen - 1);

        // --- Salidas esperadas (+exp) ---
        use_exp = $value$plusargs("exp=%s", expfile);
        nexp    = 0;
        if (use_exp) begin
            contar_tokens(expfile, nexp);
            if (nexp == 0) begin
                $display("ERROR: la lista esperada %0s esta vacia", expfile);
                $fatal(1, "lista esperada vacia");
            end
            $readmemh(expfile, expmem, 0, nexp - 1);
        end

        $display("=== Simulacion de la CPU (programa %0s, %0d bytes) ===", hexfile, nlen);

        // Reset sincrono 2 ciclos.
        rst = 1;
        repeat (2) @(posedge clk);
        @(negedge clk) rst = 0;

        // Bucle con timeout hasta HLT, recogiendo las salidas OUT.
        i = 0;
        while (!halted && i < 500000) begin
            @(posedge clk);
            #1;
            if (out_valid) begin
                if (use_exp) begin
                    if (nout < nexp) begin
                        if (out_data !== expmem[nout]) begin
                            $display("  OUT[%0d] = %0d   ESPERADO %0d   <-- MAL",
                                     nout, out_data, expmem[nout]);
                            errors = errors + 1;
                        end else begin
                            $display("  OUT[%0d] = %0d   ok", nout, out_data);
                        end
                    end else begin
                        $display("  OUT[%0d] = %0d   <-- salida de mas", nout, out_data);
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
            $display("  FALLO: la CPU no llego a HLT (posible bucle infinito)");
            errors = errors + 1;
        end

        if (use_exp) begin
            $display("  Salidas emitidas: %0d (esperadas: %0d)", nout, nexp);
            if (nout !== nexp) errors = errors + 1;
        end else begin
            $display("  Salidas emitidas: %0d (sin lista esperada, no se compara)", nout);
        end

        if (errors == 0) $display("CPU: TODOS LOS TESTS PASARON");
        else             $display("CPU: %0d FALLOS", errors);

        if (errors != 0) $fatal(1, "CPU: hay fallos, revisa arriba");
        $finish;
    end

endmodule

`default_nettype wire
