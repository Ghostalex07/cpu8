// ============================================================================
//  irq_tb.v - Testbench de las interrupciones (Fase 7.5)
//
//  Igual que cpu_tb.v pero ademas:
//    - instancia la CPU con IRQ_VECTOR = 0x10,
//  y - mantiene la entrada irq alta tras el reset.
//
//  El programa (por defecto programs/irq.hex, o +hex=<ruta>) habilita las
//  interrupciones con EI; al bajar I tras atender la primera, se atiende una
//  sola aunque irq siga alto.  Se compara la salida con +exp.
//
//  Genera build/irq_tb.vcd para verlo en GTKWave.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module irq_tb;

    reg clk = 0, rst = 1;
    reg irq = 0;        // nivel de peticion de interrupcion

    wire       halted, out_valid;
    wire [7:0] out_data;

    wire [1:0] in_port;
    wire [7:0] in_data = 8'h10 + {6'b0, in_port};

    cpu #(.IRQ_VECTOR(8'h10)) dut (
        .clk(clk), .rst(rst), .irq(irq),
        .halted(halted), .out_data(out_data), .out_valid(out_valid),
        .in_data(in_data), .in_port(in_port)
    );

    always #5 clk = ~clk;

    reg [1023:0] hexfile;
    reg [1023:0] expfile;
    integer nlen;
    integer errors = 0, nout = 0, i;
    reg use_exp;

    reg [7:0] expmem [0:255];
    integer   nexp;

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
            hexfile = "programs/irq.hex";

        $dumpfile("build/irq_tb.vcd");
        $dumpvars(0, irq_tb);

        contar_tokens(hexfile, nlen);
        if (nlen == 0) begin
            $display("ERROR: el programa %0s esta vacio", hexfile);
            $fatal(1, "programa vacio");
        end
        // RAM a 0 antes de cargar (posiciones no cubiertas por el .hex).
        for (i = 0; i < 256; i = i + 1) dut.u_ram.mem[i] = 8'h00;
        $readmemh(hexfile, dut.u_ram.mem, 0, nlen - 1);

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

        $display("=== Simulacion de IRQ (programa %0s, %0d bytes) ===", hexfile, nlen);

        // Reset sincrono 2 ciclos y, despues, irq en alto durante todo el test.
        rst = 1;
        repeat (2) @(posedge clk);
        @(negedge clk) begin rst = 0; irq = 1; end

        i = 0;
        while (!halted && i < 500000) begin
            @(posedge clk);
            #1;
            if (out_valid) begin
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
                nout = nout + 1;
            end
            i = i + 1;
        end

        if (!halted) begin
            $display("  FALLO: la CPU no llego a HLT (posible bucle infinito)");
            errors = errors + 1;
        end

        $display("  Salidas emitidas: %0d (esperadas: %0d)", nout, nexp);
        if (nout !== nexp) errors = errors + 1;

        if (errors == 0) $display("IRQ: TODOS LOS TESTS PASARON");
        else             $display("IRQ: %0d FALLOS", errors);

        if (errors != 0) $fatal(1, "IRQ: hay fallos, revisa arriba");
        $finish;
    end

endmodule

`default_nettype wire
