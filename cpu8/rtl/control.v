// ============================================================================
//  control.v - Control unit of the cpu8 CPU (state machine)
//
//  Decodes the current instruction (`instr`) and the flags, and generates all
//  the control signals of the datapath.  The datapath (cpu.v) decides nothing.
//
//  5-state FSM.  The instruction length is decided in FETCH itself from the
//  byte that was just read from RAM (`fetched`), so a separate DECODE state is
//  not needed: the instruction is already loaded into IR in that same cycle.
//  No combinational loop is formed because during FETCH `ram_addr` is the PC
//  (independent of the read) and `fetched` only feeds the (registered) state
//  transition, never `ram_addr`:
//      S_FETCH  -> (flag_i && irq) ? S_IRQ : (needs_operand ? S_OPR : S_EXEC)
//      S_IRQ    -> S_FETCH             (pushes the PC and jumps to the vector)
//      S_OPR    -> S_EXEC
//      S_EXEC   -> (instr == HLT ? S_HLT : S_FETCH)
//      S_HLT    -> S_HLT
//
//  Interrupts: if flag I (enabled by EI=0xF2) is 1 and the irq input is 1 at
//  the beginning of an instruction, it is serviced in S_IRQ: the return PC is
//  pushed, I is cleared and it jumps to IRQ_VECTOR.  The handler ends with RET.
//  Only the PC is saved (not the flags).
//
//  Opcode group 0x0 (1 byte): suboperation in rd[3:2], register in rs[1:0]:
//      00 = INC, 01 = DEC, 10 = PUSH, 11 = POP
//
//  Opcode group 0xF: HLT=0xF0, RET=0xF1, EI=0xF2, DI=0xF3, indirect LD/ST
//  (0xF4/0xF5, 2 bytes).  That is why HLT is detected as the exact instruction
//  0xF0 and not as opcode 0xF.
//
//  Opcode 0xC (2 bytes): rs=00 -> JMP, rs=01 -> CALL (stores the return address
//  on the stack before jumping).
// ============================================================================

`timescale 1ns/1ps
`default_nettype none

module control (
    input  wire       clk,
    input  wire       rst,         // synchronous reset, active high
    input  wire [7:0] instr,       // current instruction (IR register)
    input  wire [7:0] fetched,     // byte read from RAM[PC] in this FETCH
    input  wire       flag_z,
    input  wire       flag_c,
    input  wire       flag_n,      // N (sign): used by the signed jumps
    input  wire       flag_v,      // V (signed overflow, two's complement)
    input  wire       flag_i,      // interrupts enabled (set by EI)
    input  wire       irq,         // interrupt request (level, active high)

    output reg        ir_ld,       // IR <= RAM[PC]
    output reg        opr_ld,      // operand <= RAM[PC]
    output reg        pc_as_addr,  // RAM is addressed with PC
    output reg        pc_inc,      // PC <= PC + 1
    output reg        pc_load,     // PC <= d_in (jump / RET)
    output reg        rf_we,       // write to the register file
    output reg [1:0]  rf_waddr,    // destination register
    output reg        ram_we,      // write to RAM
    output reg        flags_we,    // update Z and N
    output reg        out_wr,      // register an output (OUT)
    output reg [3:0]  alu_op,      // ALU operation
    output reg        alu_sh,      // 0 = SHL, 1 = SHR
    output reg        sel_imm,     // the ALU takes the immediate (`operand`)
    output reg        sel_mem,     // the destination register takes the data from RAM
    output reg        sel_a_rs,    // the ALU takes rs as the first operand (INC/DEC)
    output reg        sel_one,     // the ALU takes the constant 1 as the second operand
    output reg        flags_c_we,  // ALSO update flag C
    output reg        sp_inc,      // SP <= SP + 1 (POP/RET)
    output reg        sp_dec,      // SP <= SP - 1 (PUSH)
    output reg        sp_as_addr,  // RAM is addressed with SP (stack)
    output reg        sel_ram_rs,  // the data written to RAM is rs (PUSH) and not rd (ST)
    output reg        pc_from_mem, // PC <= RAM[SP+1] (RET) and not `operand`
    output reg        sel_ram_pc,  // the data written to RAM is PC (CALL)
    output reg        ind,         // indirect addressing LD/ST rd,[rs]
    output reg        idx,         // indexed addressing LD/ST rd,[rs+off]
    output reg        pc_from_vec, // PC <= IRQ_VECTOR (interrupt handling)
    output reg        flag_i_set,  // EI: flag I <= 1
    output reg        flag_i_clear,// DI or interrupt: flag I <= 0
    output reg        sel_in,      // the destination register takes in_data (IN)
    output reg        io_op,       // ported form: the port goes in operand[1:0]

    output wire       halted       // 1 when the CPU is stopped (after HLT)
);

    // --- Opcode codes (match docs/ISA.md) ---
    localparam [3:0] OP_GRP0  = 4'h0,   // INC/DEC/PUSH/POP (subop in rd, reg in rs)
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

    // ALU operation codes that do NOT match an opcode (used by group 0xF:
    // 0xF6 MUL, 0xF7 DIV).  They must match alu.v.
    localparam [3:0] ALU_MUL  = 4'hC,
                     ALU_DIV  = 4'hD;

    localparam [2:0] S_FETCH  = 3'd0,
                     S_OPR    = 3'd1,
                     S_EXEC   = 3'd2,
                     S_IRQ    = 3'd3,
                     S_HLT    = 3'd4;

    // --- Instruction fields ---
    wire [3:0] opcode = instr[7:4];
    wire [1:0] rd     = instr[3:2];
    wire [1:0] rs     = instr[1:0];

    // Instructions that carry a second byte (immediate or address).  It is
    // computed from `fetched` (the byte just brought from RAM[PC]) in order to
    // decide the length already in FETCH, with no DECODE state.
    wire [3:0] fop = fetched[7:4];
    wire needs_operand = (fop == OP_LDI) || (fop == OP_LD) ||
                         (fop == OP_ST)  || (fop == OP_JMP) ||
                         (fop == OP_JCC) ||
                         (fetched == 8'hF4) || (fetched == 8'hF5) ||
                         (fetched == 8'hF6) || (fetched == 8'hF7) ||
                         (fetched == 8'hF8) || (fetched == 8'hF9); // ported MUL/DIV/OUT/IN

    // Branch condition for Jcc.  The `rd` field of the Jcc selects the family:
    //   rd=00 -> unsigned (JZ/JNZ/JC/JNC, backward compatible)
    //   rd=01 -> signed (rs=00 JLT, 01 JGE, 10 JLE, 11 JGT) using N and V
    //   rd=10 -> state (rs=00 JVS, 01 JVC, 10 JMI, 11 JPL)
    // `signed_lt` (N != V) is the "less than" condition in two's complement.
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

    // Suboperation of group 0x0 (goes in rd; the affected register goes in rs).
    wire is_inc  = (opcode == OP_GRP0) && (rd == 2'b00);
    wire is_dec  = (opcode == OP_GRP0) && (rd == 2'b01);
    wire is_push = (opcode == OP_GRP0) && (rd == 2'b10);
    wire is_pop  = (opcode == OP_GRP0) && (rd == 2'b11);

    // HLT is exactly 0xF0: group 0xF includes RET/EI/DI/indirect.
    wire is_hlt = (instr == 8'hF0);

    // --- State register ---
    reg [2:0] state, nstate;

    always @(posedge clk) begin
        if (rst) state <= S_FETCH;
        else     state <= nstate;
    end

    // --- Control logic (combinational) ---
    always @(*) begin
        // Default values: all signals to "nothing enabled".
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

            // ---- Fetch the instruction and decide its length ----
            // `fetched` is the byte just read from RAM[PC]; it is used to decide
            // already whether the instruction carries an operand (2 bytes) or not (1 byte).
            S_FETCH: begin
                if (flag_i && irq) begin
                    // Interrupt pending: it is serviced instead of fetching.
                    nstate = S_IRQ;
                end else begin
                    ir_ld      = 1'b1;   // IR      <= RAM[PC]
                    pc_as_addr = 1'b1;
                    pc_inc     = 1'b1;   // PC      <= PC + 1
                    nstate     = needs_operand ? S_OPR : S_EXEC;
                end
            end

            // ---- Service the interrupt (1 cycle) ----
            // Pushes the return PC, clears flag I and jumps to the vector.
            S_IRQ: begin
                ram_we       = 1'b1;
                sel_ram_pc   = 1'b1;   // the return PC is written
                sp_as_addr   = 1'b1;
                sp_dec       = 1'b1;
                pc_load      = 1'b1;
                pc_from_vec  = 1'b1;   // PC <= IRQ_VECTOR
                flag_i_clear = 1'b1;   // prevents nested interrupts
                nstate       = S_FETCH;
            end

            // ---- Fetch the operand (2-byte instructions) ----
            S_OPR: begin
                opr_ld     = 1'b1;   // operand <= RAM[PC]
                pc_as_addr = 1'b1;
                pc_inc     = 1'b1;   // PC      <= PC + 1
                nstate     = S_EXEC;
            end

            // ---- Execute ----
            S_EXEC: begin
                case (opcode)
                    OP_LDI:   begin
                        // Suboperation in `rs`: 00 LDI, 01 ADDI, 10 SUBI, 11 CMPI.
                        // In all of them, the ALU takes the immediate (`operand`) as b.
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
                    // LD/ST: rs=00 -> absolute address (`operand`); rs!=00 ->
                    // indexed rd,[rs+off], with base = rs (B/C/D) and off = operand.
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

                    // --- Group 0x0: INC/DEC/PUSH/POP (register in rs) ----
                    // INC/DEC: rs+1 / rs-1 with the ALU; they update Z and N (not C).
                    // PUSH:    mem[SP] <= rs; SP <= SP-1.
                    // POP:     SP <= SP+1; rs <= mem[SP+1].
                    OP_GRP0: begin
                        if (is_inc || is_dec) begin
                            alu_op   = is_inc ? OP_ADD : OP_SUB;
                            sel_a_rs = 1'b1;
                            sel_one  = 1'b1;
                            rf_we    = 1'b1;
                            rf_waddr = rs;
                            flags_we = 1'b1;     // Z and N yes; C no (no flags_c_we)
                        end else if (is_push) begin
                            ram_we     = 1'b1;
                            sel_ram_rs = 1'b1;   // data = rs
                            sp_as_addr = 1'b1;
                            sp_dec     = 1'b1;
                        end else if (is_pop) begin
                            rf_we      = 1'b1;
                            rf_waddr   = rs;
                            sel_mem    = 1'b1;   // data = RAM
                            sp_as_addr = 1'b1;
                            sp_inc     = 1'b1;
                        end
                    end

                    // Page 0xE: suboperation in `rs`.
                    //   rs=00 -> OUT rd (port 0); rs=01 -> IN rd (port 0).
                    OP_OUT:   begin
                        case (rs)
                            2'b00: out_wr = 1'b1;                          // OUT rd
                            2'b01: begin rf_we=1'b1; rf_waddr=rd;          // IN rd
                                          sel_in=1'b1; end
                            default: ;
                        endcase
                    end
                    OP_JMP:   begin
                        // rs=00 -> JMP; rs=01 -> CALL (stores the return address).
                        if (rs == 2'b01) begin
                            ram_we     = 1'b1;
                            sel_ram_pc = 1'b1;  // PC is written (return address)
                            sp_as_addr = 1'b1;
                            sp_dec     = 1'b1;
                        end
                        pc_load = 1'b1;
                    end
                    OP_JCC:   begin pc_load=branch_cond; end

                    // ---- Group 0xF: HLT (0xF0), RET (0xF1), indirect ----
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
                        end else if (instr == 8'hF2) begin  // EI: enables IRQ
                            flag_i_set   = 1'b1;
                        end else if (instr == 8'hF3) begin  // DI: disables IRQ
                            flag_i_clear = 1'b1;
                        end else if (instr == 8'hF6) begin  // MUL rd,rs (2 bytes)
                            // rd and rs come from the 2nd byte (`operand`); the
                            // `ind` mechanism is reused to address the registers.
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
                            ind    = 1'b1;   // rd comes from operand[3:2]
                            io_op  = 1'b1;   // port = operand[1:0]
                            out_wr = 1'b1;
                        end else if (instr == 8'hF9) begin  // IN n,rd (2 bytes)
                            ind    = 1'b1;
                            io_op  = 1'b1;
                            rf_we  = 1'b1;
                            sel_in = 1'b1;
                        end
                        // 0xF0 HLT: the FSM stops via is_hlt
                    end

                    default:  ;
                endcase
                nstate = is_hlt ? S_HLT : S_FETCH;
            end

            // ---- Stop after HLT ----
            S_HLT: begin
                nstate = S_HLT;
            end

            default: nstate = S_FETCH;
        endcase
    end

    assign halted = (state == S_HLT);

endmodule

`default_nettype wire
