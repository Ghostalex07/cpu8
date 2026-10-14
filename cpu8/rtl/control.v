// ============================================================================
//  control.v - Unidad de control de la CPU cpu8 (maquina de estados)
//
//  Decodifica la instruccion en curso (`instr`) y los flags, y genera todas
//  las senales de control del datapath.  El datapath (cpu.v) no decide nada.
//
//  FSM de 5 estados.  La longitud de la instruccion se decide en el propio
//  FETCH a partir del byte que se acaba de leer de la RAM (`fetched`), asi que
//  no hace falta un estado DECODE aparte: la instruccion ya se carga en IR en
//  ese mismo ciclo.  No se forma lazo combinacional porque durante el FETCH
//  `ram_addr` es el PC (independiente de la lectura) y `fetched` solo alimenta
//  la transicion de estado (registrada), nunca `ram_addr`:
//      S_FETCH  -> (flag_i && irq) ? S_IRQ : (needs_operand ? S_OPR : S_EXEC)
//      S_IRQ    -> S_FETCH             (apila el PC y salta al vector)
//      S_OPR    -> S_EXEC
//      S_EXEC   -> (instr == HLT ? S_HLT : S_FETCH)
//      S_HLT    -> S_HLT
//
//  Interrupciones: si el flag I (activado por EI=0xF2) esta a 1 y la entrada
//  irq a 1 al comienzo de una instruccion, se atiende en S_IRQ: se apila el PC
//  de retorno, se baja I y se salta al vector IRQ_VECTOR.  El manejador acaba
//  con RET.  Solo se salva el PC (no los flags).
//
//  Grupo de opcode 0x0 (1 byte): suboperacion en rd[3:2], registro en rs[1:0]:
//      00 = INC, 01 = DEC, 10 = PUSH, 11 = POP
//
//  Grupo de opcode 0xF: HLT=0xF0, RET=0xF1, EI=0xF2, DI=0xF3, LD/ST indirecto
//  (0xF4/0xF5, 2 bytes).  Por eso HLT se detecta como la instruccion exacta
//  0xF0 y no como el opcode 0xF.
//
//  Opcode 0xC (2 bytes): rs=00 -> JMP, rs=01 -> CALL (guarda el retorno en la
//  pila antes de saltar).
// ============================================================================

`timescale 1ns/1ps
`default_nettype none

module control (
    input  wire       clk,
    input  wire       rst,         // reset sincrono, activo alto
    input  wire [7:0] instr,       // instruccion en curso (registro IR)
    input  wire [7:0] fetched,     // byte leido de RAM[PC] en este FETCH
    input  wire       flag_z,
    input  wire       flag_c,
    input  wire       flag_n,      // N (signo): lo usan los saltos con signo
    input  wire       flag_v,      // V (desbordamiento con signo, Ca2)
    input  wire       flag_i,      // interrupciones habilitadas (lo pone EI)
    input  wire       irq,         // peticion de interrupcion (nivel, activo alto)

    output reg        ir_ld,       // IR <= RAM[PC]
    output reg        opr_ld,      // operand <= RAM[PC]
    output reg        pc_as_addr,  // la RAM se direcciona con PC
    output reg        pc_inc,      // PC <= PC + 1
    output reg        pc_load,     // PC <= d_in (salto / RET)
    output reg        rf_we,       // escritura en el banco de registros
    output reg [1:0]  rf_waddr,    // registro destino
    output reg        ram_we,      // escritura en RAM
    output reg        flags_we,    // actualizar Z y N
    output reg        out_wr,      // registrar una salida (OUT)
    output reg [3:0]  alu_op,      // operacion de la ALU
    output reg        alu_sh,      // 0 = SHL, 1 = SHR
    output reg        sel_imm,     // la ALU toma el inmediato (`operand`)
    output reg        sel_mem,     // el registro destino toma el dato de RAM
    output reg        sel_a_rs,    // la ALU toma rs como primer operando (INC/DEC)
    output reg        sel_one,     // la ALU toma la constante 1 como segundo operando
    output reg        flags_c_we,  // actualizar TAMBIEN el flag C
    output reg        sp_inc,      // SP <= SP + 1 (POP/RET)
    output reg        sp_dec,      // SP <= SP - 1 (PUSH)
    output reg        sp_as_addr,  // la RAM se direcciona con SP (pila)
    output reg        sel_ram_rs,  // el dato escrito en RAM es rs (PUSH) y no rd (ST)
    output reg        pc_from_mem, // PC <= RAM[SP+1] (RET) y no `operand`
    output reg        sel_ram_pc,  // el dato escrito en RAM es PC (CALL)
    output reg        ind,         // direccionamiento indirecto LD/ST rd,[rs]
    output reg        idx,         // direccionamiento indexado LD/ST rd,[rs+off]
    output reg        pc_from_vec, // PC <= IRQ_VECTOR (atencion de interrupcion)
    output reg        flag_i_set,  // EI: flag I <= 1
    output reg        flag_i_clear,// DI o interrupcion: flag I <= 0
    output reg        sel_in,      // el registro destino toma in_data (IN)
    output reg        io_op,       // forma portada: el puerto va en operand[1:0]

    output wire       halted       // 1 cuando la CPU esta parada (tras HLT)
);

    // --- Codigos de opcode (coinciden con docs/ISA.md) ---
    localparam [3:0] OP_GRP0  = 4'h0,   // INC/DEC/PUSH/POP (subop en rd, reg en rs)
                     OP_LDI   = 4'h1,
                     OP_MOV   = 4'h2,
                     OP_LD    = 4'h3,
                     OP_ST    = 4'h4,
                     OP_ADD   = 4'h5,
                     OP_SUB   = 4'h6,
                     OP_AND   = 4'h7,
                     OP_OR    = 4'h8,
                     OP_XOR   = 4'h9,
                     OP_CMP   = 4'hA,
                     OP_SHIFT = 4'hB,
                     OP_JMP   = 4'hC,
                     OP_JCC   = 4'hD,
                     OP_OUT   = 4'hE,
                     OP_HLT   = 4'hF;

    // Codigos de operacion de la ALU que NO coinciden con un opcode (los usa
    // el grupo 0xF: 0xF6 MUL, 0xF7 DIV).  Deben coincidir con alu.v.
    localparam [3:0] ALU_MUL  = 4'hC,
                     ALU_DIV  = 4'hD;

    localparam [2:0] S_FETCH  = 3'd0,
                     S_OPR    = 3'd1,
                     S_EXEC   = 3'd2,
                     S_IRQ    = 3'd3,
                     S_HLT    = 3'd4;

    // --- Campos de la instruccion ---
    wire [3:0] opcode = instr[7:4];
    wire [1:0] rd     = instr[3:2];
    wire [1:0] rs     = instr[1:0];

    // Instrucciones que llevan un segundo byte (inmediato o direccion).  Se
    // calcula sobre `fetched` (el byte que se acaba de traer de RAM[PC]) para
    // poder decidir la longitud ya en el FETCH, sin estado DECODE.
    wire [3:0] fop = fetched[7:4];
    wire needs_operand = (fop == OP_LDI) || (fop == OP_LD) ||
                         (fop == OP_ST)  || (fop == OP_JMP) ||
                         (fop == OP_JCC) ||
                         (fetched == 8'hF4) || (fetched == 8'hF5) ||
                         (fetched == 8'hF6) || (fetched == 8'hF7) ||
                         (fetched == 8'hF8) || (fetched == 8'hF9); // MUL/DIV/OUT/IN portados

    // Condicion de salto para Jcc.  El campo `rd` del Jcc selecciona la familia:
    //   rd=00 -> sin signo (JZ/JNZ/JC/JNC, retrocompatible)
    //   rd=01 -> con signo (rs=00 JLT, 01 JGE, 10 JLE, 11 JGT) usando N y V
    //   rd=10 -> estado (rs=00 JVS, 01 JVC, 10 JMI, 11 JPL)
    // `menor_que` (N != V) es la condicion "menor que" en complemento a dos.
    wire signed_lt = flag_n ^ flag_v;
    wire [1:0] jc_fam = rd;
    wire branch_cond =
        (jc_fam == 2'b00) ? ((rs == 2'b00) ?  flag_z :
                             (rs == 2'b01) ? ~flag_z :
                             (rs == 2'b10) ?  flag_c : ~flag_c) :
        (jc_fam == 2'b01) ? ((rs == 2'b00) ?  signed_lt :          // JLT
                             (rs == 2'b01) ? ~signed_lt :         // JGE
                             (rs == 2'b10) ? (flag_z | signed_lt) : // JLE
                                             (~flag_z & ~signed_lt)) : // JGT
                            ((rs == 2'b00) ?  flag_v :            // JVS
                             (rs == 2'b01) ? ~flag_v :            // JVC
                             (rs == 2'b10) ?  flag_n :            // JMI
                                             ~flag_n);            // JPL

    // Suboperacion del grupo 0x0 (va en rd; el registro afectado va en rs).
    wire is_inc  = (opcode == OP_GRP0) && (rd == 2'b00);
    wire is_dec  = (opcode == OP_GRP0) && (rd == 2'b01);
    wire is_push = (opcode == OP_GRP0) && (rd == 2'b10);
    wire is_pop  = (opcode == OP_GRP0) && (rd == 2'b11);

    // HLT es exactamente 0xF0: el grupo 0xF incluye RET/EI/DI/indirecto.
    wire is_hlt = (instr == 8'hF0);

    // --- Registro de estado ---
    reg [2:0] state, nstate;

    always @(posedge clk) begin
        if (rst) state <= S_FETCH;
        else     state <= nstate;
    end

    // --- Logica de control (combinacional) ---
    always @(*) begin
        // Valores por defecto: todas las senales a "nada activado".
        nstate      = state;
        ir_ld       = 1'b0;
        opr_ld      = 1'b0;
        pc_as_addr  = 1'b0;
        pc_inc      = 1'b0;
        pc_load     = 1'b0;
        rf_we       = 1'b0;
        rf_waddr    = rd;
        ram_we      = 1'b0;
        flags_we    = 1'b0;
        out_wr      = 1'b0;
        alu_op      = opcode;
        alu_sh      = 1'b0;
        sel_imm     = 1'b0;
        sel_mem     = 1'b0;
        sel_a_rs    = 1'b0;
        sel_one     = 1'b0;
        flags_c_we  = 1'b0;
        sp_inc      = 1'b0;
        sp_dec      = 1'b0;
        sp_as_addr  = 1'b0;
        sel_ram_rs  = 1'b0;
        pc_from_mem = 1'b0;
        sel_ram_pc  = 1'b0;
        ind         = 1'b0;
        idx         = 1'b0;
        pc_from_vec = 1'b0;
        flag_i_set  = 1'b0;
        flag_i_clear= 1'b0;
        sel_in      = 1'b0;
        io_op       = 1'b0;

        case (state)

            // ---- Busca la instruccion y decide su longitud ----
            // `fetched` es el byte recien leido de RAM[PC]; con el se decide ya
            // si la instruccion lleva operando (2 bytes) o no (1 byte).
            S_FETCH: begin
                if (flag_i && irq) begin
                    // Interrupcion pendiente: se atiende en vez de buscar.
                    nstate = S_IRQ;
                end else begin
                    ir_ld      = 1'b1;   // IR      <= RAM[PC]
                    pc_as_addr = 1'b1;
                    pc_inc     = 1'b1;   // PC      <= PC + 1
                    nstate     = needs_operand ? S_OPR : S_EXEC;
                end
            end

            // ---- Atiende la interrupcion (1 ciclo) ----
            // Apila el PC de retorno, baja el flag I y salta al vector.
            S_IRQ: begin
                ram_we       = 1'b1;
                sel_ram_pc   = 1'b1;   // se escribe el PC de retorno
                sp_as_addr   = 1'b1;
                sp_dec       = 1'b1;
                pc_load      = 1'b1;
                pc_from_vec  = 1'b1;   // PC <= IRQ_VECTOR
                flag_i_clear = 1'b1;   // evita interrupciones anidadas
                nstate       = S_FETCH;
            end

            // ---- Busca el operando (instrucciones de 2 bytes) ----
            S_OPR: begin
                opr_ld     = 1'b1;   // operand <= RAM[PC]
                pc_as_addr = 1'b1;
                pc_inc     = 1'b1;   // PC      <= PC + 1
                nstate     = S_EXEC;
            end

            // ---- Ejecuta ----
            S_EXEC: begin
                case (opcode)
                    OP_LDI:   begin
                        // Suboperacion en `rs`: 00 LDI, 01 ADDI, 10 SUBI, 11 CMPI.
                        // En todos, la ALU toma el inmediato (`operand`) como b.
                        sel_imm = 1'b1;
                        case (rs)
                            2'b00: begin rf_we=1'b1; rf_waddr=rd; end                 // LDI
                            2'b01: begin alu_op=OP_ADD; rf_we=1'b1; rf_waddr=rd;
                                          flags_we=1'b1; flags_c_we=1'b1; end         // ADDI
                            2'b10: begin alu_op=OP_SUB; rf_we=1'b1; rf_waddr=rd;
                                          flags_we=1'b1; flags_c_we=1'b1; end         // SUBI
                            2'b11: begin alu_op=OP_CMP;
                                          flags_we=1'b1; flags_c_we=1'b1; end         // CMPI
                        endcase
                    end
                    OP_MOV:   begin rf_we=1'b1; rf_waddr=rd; end
                    // LD/ST: rs=00 -> direccion absoluta (`operand`); rs!=00 ->
                    // indexado rd,[rs+off], con base = rs (B/C/D) y off = operand.
                    OP_LD:    begin rf_we=1'b1; rf_waddr=rd; sel_mem=1'b1;
                                    if (rs != 2'b00) idx=1'b1; end
                    OP_ST:    begin ram_we=1'b1;
                                    if (rs != 2'b00) idx=1'b1; end
                    OP_ADD, OP_SUB, OP_AND, OP_OR, OP_XOR:
                              begin rf_we=1'b1; rf_waddr=rd; flags_we=1'b1;
                                    flags_c_we=1'b1; end
                    OP_CMP:   begin flags_we=1'b1; flags_c_we=1'b1; end
                    OP_SHIFT: begin rf_we=1'b1; rf_waddr=rd; flags_we=1'b1;
                                      flags_c_we=1'b1; alu_sh=rs[0]; end

                    // --- Grupo 0x0: INC/DEC/PUSH/POP (registro en rs) ----
                    // INC/DEC: rs+1 / rs-1 con la ALU; actualizan Z y N (no C).
                    // PUSH:    mem[SP] <= rs; SP <= SP-1.
                    // POP:     SP <= SP+1; rs <= mem[SP+1].
                    OP_GRP0: begin
                        if (is_inc || is_dec) begin
                            alu_op   = is_inc ? OP_ADD : OP_SUB;
                            sel_a_rs = 1'b1;
                            sel_one  = 1'b1;
                            rf_we    = 1'b1;
                            rf_waddr = rs;
                            flags_we = 1'b1;     // Z y N si; C no (sin flags_c_we)
                        end else if (is_push) begin
                            ram_we     = 1'b1;
                            sel_ram_rs = 1'b1;   // dato = rs
                            sp_as_addr = 1'b1;
                            sp_dec     = 1'b1;
                        end else if (is_pop) begin
                            rf_we      = 1'b1;
                            rf_waddr   = rs;
                            sel_mem    = 1'b1;   // dato = RAM
                            sp_as_addr = 1'b1;
                            sp_inc     = 1'b1;
                        end
                    end

                    // Pagina 0xE: suboperacion en `rs`.
                    //   rs=00 -> OUT rd (puerto 0); rs=01 -> IN rd (puerto 0).
                    OP_OUT:   begin
                        case (rs)
                            2'b00: out_wr = 1'b1;                          // OUT rd
                            2'b01: begin rf_we=1'b1; rf_waddr=rd;          // IN rd
                                          sel_in=1'b1; end
                            default: ;
                        endcase
                    end
                    OP_JMP:   begin
                        // rs=00 -> JMP; rs=01 -> CALL (guarda el retorno).
                        if (rs == 2'b01) begin
                            ram_we     = 1'b1;
                            sel_ram_pc = 1'b1;  // se escribe PC (dir. de retorno)
                            sp_as_addr = 1'b1;
                            sp_dec     = 1'b1;
                        end
                        pc_load = 1'b1;
                    end
                    OP_JCC:   begin pc_load=branch_cond; end

                    // ---- Grupo 0xF: HLT (0xF0), RET (0xF1), indirecto ----
                    OP_HLT: begin
                        if (instr == 8'hF1) begin   // RET: PC <= mem[SP+1]; SP++
                            sp_as_addr  = 1'b1;
                            sp_inc      = 1'b1;
                            pc_load     = 1'b1;
                            pc_from_mem = 1'b1;
                        end else if (instr == 8'hF4) begin  // LD rd,[rs]
                            ind     = 1'b1;
                            rf_we   = 1'b1;
                            sel_mem = 1'b1;
                        end else if (instr == 8'hF5) begin  // ST rd,[rs]
                            ind     = 1'b1;
                            ram_we  = 1'b1;
                        end else if (instr == 8'hF2) begin  // EI: habilita IRQ
                            flag_i_set   = 1'b1;
                        end else if (instr == 8'hF3) begin  // DI: inhabilita IRQ
                            flag_i_clear = 1'b1;
                        end else if (instr == 8'hF6) begin  // MUL rd,rs (2 bytes)
                            // rd y rs vienen del 2o byte (`operand`); se reutiliza
                            // el mecanismo `ind` para direccionar los registros.
                            ind      = 1'b1;
                            alu_op   = ALU_MUL;
                            rf_we    = 1'b1;
                            flags_we = 1'b1;
                            flags_c_we = 1'b1;
                        end else if (instr == 8'hF7) begin  // DIV rd,rs (2 bytes)
                            ind      = 1'b1;
                            alu_op   = ALU_DIV;
                            rf_we    = 1'b1;
                            flags_we = 1'b1;
                            flags_c_we = 1'b1;
                        end else if (instr == 8'hF8) begin  // OUT n,rd (2 bytes)
                            ind    = 1'b1;   // rd sale de operand[3:2]
                            io_op  = 1'b1;   // puerto = operand[1:0]
                            out_wr = 1'b1;
                        end else if (instr == 8'hF9) begin  // IN n,rd (2 bytes)
                            ind    = 1'b1;
                            io_op  = 1'b1;
                            rf_we  = 1'b1;
                            sel_in = 1'b1;
                        end
                        // 0xF0 HLT: la FSM se detiene por is_hlt
                    end

                    default:  ;
                endcase
                nstate = is_hlt ? S_HLT : S_FETCH;
            end

            // ---- Parada tras HLT ----
            S_HLT: begin
                nstate = S_HLT;
            end

            default: nstate = S_FETCH;
        endcase
    end

    assign halted = (state == S_HLT);

endmodule

`default_nettype wire
