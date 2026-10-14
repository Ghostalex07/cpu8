// ============================================================================
//  cpu.v - CPU cpu8 completa (datapath + unidad de control)
//
//  Une las piezas (ALU, banco de registros, RAM, PC) con los registros internos
//  (IR, operand, flags, SP, salida).  No decodifica: eso lo hace control.v.
//
//  Pila: registro SP de 8 bits (arranca en 0xF0).  Es una pila DESCENDENTE que
//  apunta al hueco libre:
//       PUSH v  ->  mem[SP] = v ; SP = SP - 1
//       POP  rd ->  SP = SP + 1 ; rd = mem[SP]
//       RET     ->  SP = SP + 1 ; PC = mem[SP]
//  Por eso en PUSH se direcciona la RAM con SP, y en POP/RET con SP+1.
//
//  CALL (0xC1): ademas de saltar, escribe el PC de retorno (dir_CALL+2) en la
//  pila.  Direccionamiento indirecto (0xF4/0xF5): los indices de registro van
//  en el 2o byte (`operand`), asi que se conmutan las direcciones del banco de
//  registros y la RAM se direcciona con el VALOR del registro rs.
//
//  Interrupciones: flag I (lo activa EI=0xF2, lo desactiva DI=0xF3).  Si I=1 e
//  irq=1 al comienzo de una instruccion, la CPU apila el PC de retorno, baja I
//  y salta a IRQ_VECTOR.  Al entrar en la interrupcion I queda a 0, de modo que
//  mientras irq siga alto no se atiende otra hasta volver a hacer EI.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module cpu #(
    parameter [7:0] IRQ_VECTOR = 8'h08   // direccion del manejador de IRQ
) (
    input  wire       clk,
    input  wire       rst,        // reset sincrono, activo alto
    input  wire       irq,        // peticion de interrupcion (nivel, activo alto)
    output wire       halted,     // 1 cuando la CPU esta parada (tras HLT)
    input  wire [7:0] in_data,    // bus de entrada (valor del puerto `in_port`)
    output reg  [7:0] out_data,   // ultimo valor enviado por OUT
    output reg        out_valid,  // pulso de 1 ciclo al ejecutar OUT
    output reg  [1:0] out_port,   // puerto del ultimo OUT
    output wire [1:0] in_port     // puerto que lee la instruccion IN en curso
);

    // ------------------------------------------------------------------
    //  Registros internos
    // ------------------------------------------------------------------
    reg [7:0] IR;        // instruccion en curso
    reg [7:0] operand;   // segundo byte (inmediato o direccion)
    reg       flag_z;    // Z (cero)
    reg       flag_c;    // C (acarreo / no-borrow)
    reg       flag_n;    // N (negativo)
    reg       flag_v;    // V (desbordamiento con signo)
    reg       flag_i;    // I (interrupciones habilitadas)
    reg [7:0] SP;        // puntero de pila (arranca en 0xF0)

    // ------------------------------------------------------------------
    //  Senales control -> datapath
    // ------------------------------------------------------------------
    wire       ir_ld, opr_ld, pc_as_addr, pc_inc, pc_load;
    wire       rf_we, ram_we, flags_we, out_wr;
    wire [1:0] rf_waddr;
    wire [3:0] alu_op;
    wire       alu_sh, sel_imm, sel_mem;
    wire       sel_a_rs, sel_one, flags_c_we;
    wire       sp_inc, sp_dec, sp_as_addr, sel_ram_rs, pc_from_mem;
    wire       sel_ram_pc, ind, idx;
    wire       pc_from_vec, flag_i_set, flag_i_clear;
    wire       sel_in, io_op;

    // Instruccion en curso: siempre desde el registro IR.  Decodificar desde
    // IR (y no desde la RAM) evita un lazo combinacional control <-> RAM.
    wire [7:0] instr = IR;

    // ------------------------------------------------------------------
    //  Buses internos
    // ------------------------------------------------------------------
    wire [7:0] rf_rdata_rd;   // lectura del registro rd (puerto 1)
    wire [7:0] rf_rdata_rs;   // lectura del registro rs (puerto 2)
    wire [7:0] alu_a, alu_b, alu_y;
    wire       alu_c, alu_z, alu_n, alu_v;
    wire [7:0] ram_addr, ram_wdata, ram_rdata;
    wire [7:0] pc_q;

    // ------------------------------------------------------------------
    //  Unidad de control
    // ------------------------------------------------------------------
    control u_ctrl (
        .clk(clk), .rst(rst), .instr(instr), .fetched(ram_rdata),
        .flag_z(flag_z), .flag_c(flag_c), .flag_n(flag_n),
        .flag_v(flag_v), .flag_i(flag_i), .irq(irq),
        .ir_ld(ir_ld), .opr_ld(opr_ld), .pc_as_addr(pc_as_addr),
        .pc_inc(pc_inc), .pc_load(pc_load),
        .rf_we(rf_we), .rf_waddr(rf_waddr),
        .ram_we(ram_we), .flags_we(flags_we), .out_wr(out_wr),
        .alu_op(alu_op), .alu_sh(alu_sh),
        .sel_imm(sel_imm), .sel_mem(sel_mem),
        .sel_a_rs(sel_a_rs), .sel_one(sel_one), .flags_c_we(flags_c_we),
        .sp_inc(sp_inc), .sp_dec(sp_dec), .sp_as_addr(sp_as_addr),
        .sel_ram_rs(sel_ram_rs), .pc_from_mem(pc_from_mem),
        .sel_ram_pc(sel_ram_pc), .ind(ind), .idx(idx),
        .pc_from_vec(pc_from_vec), .flag_i_set(flag_i_set),
        .flag_i_clear(flag_i_clear),
        .sel_in(sel_in), .io_op(io_op),
        .halted(halted)
    );

    // ------------------------------------------------------------------
    //  ALU.  a = rd (o rs en INC/DEC); b = inmediato, rs o la constante 1.
    // ------------------------------------------------------------------
    assign alu_a = sel_a_rs ? rf_rdata_rs : rf_rdata_rd;
    assign alu_b = sel_one  ? 8'd1 :
                   sel_imm  ? operand : rf_rdata_rs;

    alu u_alu (
        .op(alu_op), .sh(alu_sh), .a(alu_a), .b(alu_b),
        .y(alu_y), .c(alu_c), .v(alu_v), .z(alu_z), .n(alu_n)
    );

    // ------------------------------------------------------------------
    //  Banco de registros.  rd en el puerto 1, rs en el puerto 2.
    //  El dato a escribir viene de la RAM (LD/POP) o de la ALU.
    // ------------------------------------------------------------------
    wire [7:0] rf_wdata = sel_in  ? in_data :
                          sel_mem ? ram_rdata : alu_y;

    // ------------------------------------------------------------------
    //  Puertos de E/S.  La forma portada (0xF8 OUT / 0xF9 IN) toma el
    //  puerto de `operand[1:0]`; las de 1 byte (OUT/IN) usan el puerto 0.
    // ------------------------------------------------------------------
    wire [1:0] io_port = io_op ? operand[1:0] : 2'b00;
    assign in_port = io_port;

    // ------------------------------------------------------------------
    //  RAM.  Direccion = PC (FETCH/OPR), SP (pila), rs indirecto, u
    //  `operand` (EXEC).  Dato escrito = rd (ST), rs (PUSH) o PC (CALL).
    // ------------------------------------------------------------------
    wire [7:0] sp_addr = sp_inc ? (SP + 8'd1) : SP;  // POP/RET leen SP+1

    assign ram_addr  = ind ? rf_rdata_rs
                     : idx ? (rf_rdata_rs + operand)
                     : (pc_as_addr ? pc_q : (sp_as_addr ? sp_addr : operand));
    assign ram_wdata = sel_ram_rs ? rf_rdata_rs
                     : (sel_ram_pc ? pc_q : rf_rdata_rd);

    ram u_ram (
        .clk(clk), .we(ram_we), .addr(ram_addr), .wdata(ram_wdata), .rdata(ram_rdata)
    );

    // ------------------------------------------------------------------
    //  Banco de registros.  En modo indirecto los indices salen del 2o byte.
    // ------------------------------------------------------------------
    wire [1:0] rf_raddr1 = ind ? operand[3:2] : instr[3:2];
    wire [1:0] rf_raddr2 = ind ? operand[1:0] : instr[1:0];
    wire [1:0] rf_waddr_m = ind ? operand[3:2] : rf_waddr;

    regfile u_rf (
        .clk(clk), .rst(rst), .we(rf_we), .waddr(rf_waddr_m), .wdata(rf_wdata),
        .raddr1(rf_raddr1), .rdata1(rf_rdata_rd),
        .raddr2(rf_raddr2), .rdata2(rf_rdata_rs)
    );

    // ------------------------------------------------------------------
    //  PC.  Salta a `operand` (JMP/Jcc) o al valor de la pila (RET).
    // ------------------------------------------------------------------
    wire [7:0] pc_din = pc_from_vec ? IRQ_VECTOR :
                        pc_from_mem ? ram_rdata : operand;

    pc u_pc (
        .clk(clk), .rst(rst), .load(pc_load), .inc(pc_inc), .d_in(pc_din), .q(pc_q)
    );

    // ------------------------------------------------------------------
    //  Registros sincronos
    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (rst) begin
            IR       <= 8'h00;
            operand  <= 8'h00;
            flag_z   <= 1'b0;
            flag_c   <= 1'b0;
            flag_n   <= 1'b0;
            flag_v   <= 1'b0;
            flag_i   <= 1'b0;
`ifdef FPGA_RAM64
            SP       <= 8'h3F;   // pila en RAM reducida (64 bytes)
`else
            SP       <= 8'hF0;   // pila en RAM completa (256 bytes)
`endif
            out_data <= 8'h00;
            out_valid<= 1'b0;
            out_port <= 2'b00;
        end else begin
            if (ir_ld)    IR      <= ram_rdata;
            if (opr_ld)   operand <= ram_rdata;
            if (flags_we) begin
                flag_z <= alu_z;
                flag_n <= alu_n;
                flag_v <= alu_v;
            end
            if (flags_c_we)  flag_c <= alu_c;
            if (flag_i_set)   flag_i <= 1'b1;
            if (flag_i_clear) flag_i <= 1'b0;
            if (sp_dec)      SP <= SP - 8'd1;
            else if (sp_inc) SP <= SP + 8'd1;
            if (out_wr) begin
                out_data <= rf_rdata_rd;
                out_port <= io_port;
            end
            out_valid <= out_wr;   // pulso de un ciclo tras OUT
        end
    end

endmodule

`default_nettype wire
