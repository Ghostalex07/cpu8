`timescale 1ns/1ps
`default_nettype none
// ============================================================================
//  cpu_dump_tb.v - volcado MAQUINA-LEGIBLE del estado, para fuzz diferencial
//
//  Ejecuta un programa (``+hex=<ruta>``) y, por cada instruccion RETIRADA,
//  imprime una linea con el estado arquitectonico.  La salida tiene el mismo
//  formato que el modelo de referencia ``tools/iss.py``, de modo que
//  ``tools/difftest.py`` los compara linea a linea:
//
//      I <pc> <ir> <a> <b> <c> <d> <z> <cf> <n> <v> <sp> <pcnext> <ov> <odata> <oport>
//      M <256 bytes>                (contenido final de la RAM)
//      END <n_instrucciones>
//
//  Detalles:
//   - La RAM se pone a CERO antes de cargar el programa (ram.v no tiene reset,
//     asi que en iverilog las posiciones sin cargar valdrian X).  El ISS asume
//     tambien RAM a cero.
//   - Entrada como en los demas tb: in_data = 0x10 + puerto.
//   - irq se deja a 0 (el fuzz diferencial no cubre IRQ; eso lo hace irqtest).
// ============================================================================

module cpu_dump_tb;

    reg clk = 0, rst = 1;
    wire irq;
    reg [7:0] in_data = 8'h00;
    wire       halted, out_valid;
    wire [7:0] out_data;
    wire [1:0] in_port, out_port;

    cpu #(.IRQ_VECTOR(8'h08)) dut (
        .clk(clk), .rst(rst), .irq(irq),
        .halted(halted), .out_data(out_data), .out_valid(out_valid),
        .in_data(in_data), .in_port(in_port), .out_port(out_port)
    );

    always #5 clk = ~clk;

    // Entrada: valor del puerto pedido (puerto 0 -> 0x10, puerto 1 -> 0x11, ...).
    always @(*) in_data = 8'h10 + {6'b0, in_port};

    reg [8*256-1:0] hexfile;
    integer maxi, i, dummy;
    integer n = 0;
    // Nivel de irq: se activa cuando ya se han retirado >= irq_at instrucciones
    // (mismo convenio que tools/iss.py).  Por defecto irq_at es enorme => nunca
    // se atiende interrupcion, de modo que el comportamiento sin +irq no cambia.
    integer irq_at = 100000000;
    assign irq = (n >= irq_at);

    // PC de la instruccion en curso: se latchea al cargar el IR (S_FETCH).
    reg [7:0] trace_pc;
    always @(posedge clk) if (dut.ir_ld) trace_pc <= dut.pc_q;

    // La instruccion "retira" en el flanco en que se ejecuta S_EXEC; se detecta
    // en el negedge siguiente (los registros ya estan actualizados).
    reg [2:0] st_d = 3'd0;
    localparam [2:0] S_EXEC = 3'd2;

    task dump_mem;
        integer j;
        begin
            $write("M");
            for (j = 0; j < 256; j = j + 1) $write(" %02h", dut.u_ram.mem[j]);
            $write("\n");
        end
    endtask

    initial begin
        if (!$value$plusargs("hex=%s", hexfile)) hexfile = "programs/countdown.hex";
        maxi = 5000;
        dummy = $value$plusargs("max=%d", maxi);
        dummy = $value$plusargs("irq=%d", irq_at);
        for (i = 0; i < 256; i = i + 1) dut.u_ram.mem[i] = 8'h00;
        $readmemh(hexfile, dut.u_ram.mem);
        n = 0;
        rst = 1;
        repeat (2) @(posedge clk);
        @(negedge clk) rst = 0;
    end

    always @(negedge clk) begin
        #1;
        if (!rst) begin
            if (st_d == S_EXEC) begin
                $display("I %02h %02h %02h %02h %02h %02h %b %b %b %b %02h %02h %b %02h %02h",
                         trace_pc, dut.IR,
                         dut.u_rf.regs[0], dut.u_rf.regs[1],
                         dut.u_rf.regs[2], dut.u_rf.regs[3],
                         dut.flag_z, dut.flag_c, dut.flag_n, dut.flag_v,
                         dut.SP, dut.pc_q, out_valid, out_data, out_port);
                n = n + 1;
                if (n >= maxi) begin
                    $display("END %0d", n);
                    dump_mem;
                    $finish;
                end
            end
            st_d = dut.u_ctrl.state;
            if (halted) begin
                $display("END %0d", n);
                dump_mem;
                $finish;
            end
        end else begin
            st_d = dut.u_ctrl.state;
        end
    end

endmodule

`default_nettype wire
