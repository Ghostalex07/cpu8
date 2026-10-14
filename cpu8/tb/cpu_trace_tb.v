`timescale 1ns/1ps
`default_nettype none
// ============================================================================
//  cpu_trace_tb.v - Debugger de traza (Fase 9)
//
//  Ejecuta un programa y muestra UNA linea por instruccion retirada, con el
//  estado de la CPU *despues* de ejecutarla:
//
//      PC   IR   A  B  C  D   Z C N V  SP
//
//  Uso (via `make trace PROG=programs/xxx`):
//      vvp build/trace.vvp +hex=programs/xxx.hex
//
//  No forma parte de `make test`: es una herramienta interactiva de depuracion.
// ============================================================================

module cpu_trace_tb;

    reg clk = 0, rst = 1, irq = 0;
    reg [7:0] in_data = 8'h00;      // entrada fija (puerto 0..3 -> igual valor)
    wire       halted, out_valid;
    wire [7:0] out_data;
    wire [1:0] in_port, out_port;

    cpu dut (
        .clk(clk), .rst(rst), .irq(irq),
        .halted(halted), .out_data(out_data), .out_valid(out_valid),
        .in_data(in_data), .in_port(in_port), .out_port(out_port)
    );

    always #5 clk = ~clk;

    reg [8*256-1:0] hexfile;
    integer n = 0;
    localparam integer MAX_INSTR = 20000;   // tope de seguridad

    initial begin
        if (!$value$plusargs("hex=%s", hexfile)) hexfile = "programs/countdown.hex";
        if (!$value$plusargs("in=%d", in_data)) in_data = 8'h00;
        $readmemh(hexfile, dut.u_ram.mem);
        $display("=== traza de %0s ===", hexfile);
        $display("    PC   IR   A    B    C    D    Z C N V  SP");
        rst = 1;
        repeat (2) @(posedge clk);
        @(negedge clk) rst = 0;
    end

    // PC de la instruccion en curso: se latchea al cargar el IR (S_FETCH).
    reg [7:0] trace_pc;
    always @(posedge clk) if (dut.ir_ld) trace_pc <= dut.pc_q;

    // Una instruccion "retira" en el flanco de subida en que se ejecuta S_EXEC
    // (estado 3'd2).  Se detecta en el negedge siguiente, cuando los registros
    // y flags ya estan actualizados.
    reg [2:0] st_d = 3'd0;
    always @(negedge clk) begin
        if (rst) begin
            st_d <= dut.u_ctrl.state;
        end else begin
            if (st_d == 3'd2) begin
                $display("  %02h   %02h   %02h   %02h   %02h   %02h   %b %b %b %b  %02h%s",
                         trace_pc, dut.IR,
                         dut.u_rf.regs[0], dut.u_rf.regs[1],
                         dut.u_rf.regs[2], dut.u_rf.regs[3],
                         dut.flag_z, dut.flag_c, dut.flag_n, dut.flag_v, dut.SP,
                         out_valid ? "   OUT" : "");
                n = n + 1;
                if (n >= MAX_INSTR) begin
                    $display("(tope de %0d instrucciones alcanzado)", MAX_INSTR);
                    $finish;
                end
            end
            st_d <= dut.u_ctrl.state;
            if (halted) begin
                if (out_valid) $display("    (ULTIMO OUT: %02h por puerto %0d)", out_data, out_port);
                $display("(HLT tras %0d instrucciones)", n);
                $finish;
            end
        end
    end

endmodule

`default_nettype wire
