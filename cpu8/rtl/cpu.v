// ============================================================================
//  cpu.v - complete cpu8 CPU (datapath + control unit)
//
//  Ties the pieces together (ALU, register file, RAM, PC) with the internal
//  registers (IR, operand, flags, SP, output).  It does not decode: control.v
//  does that.
//
//  Stack: 8-bit SP register (starts at 0xF0).  It is a DESCENDING stack that
//  points to the free slot:
//       PUSH v  ->  mem[SP] = v ; SP = SP - 1
//       POP  rd ->  SP = SP + 1 ; rd = mem[SP]
//       RET     ->  SP = SP + 1 ; PC = mem[SP]
//       PUSHF   ->  mem[SP] = flags ; SP = SP - 1
//       POPF    ->  SP = SP + 1 ; flags = mem[SP]
//  That is why in PUSH the RAM is addressed with SP, and in POP/RET with SP+1.
//
//  Extended pair ops (ADCW/SUBW, prefix 0xFA): they take TWO EXEC cycles
//  (S_EXEC adds/subtracts the low bytes and S_EXEC2 the high ones); c16/z16
//  carry the low-byte carry and zero-ness between both.
//
//  CALL (0xC1): besides jumping, it writes the return PC (addr_CALL+2) onto the
//  stack.  Indirect addressing (0xF4/0xF5): the register indices go in the 2nd
//  byte (`operand`), so the register file addresses are switched and the RAM is
//  addressed with the VALUE of register rs.
//
//  Interrupts: flag I (enabled by EI=0xF2, disabled by DI=0xF3).  If I=1 and
//  irq=1 at the beginning of an instruction, the CPU pushes the return PC,
//  clears I and jumps to IRQ_VECTOR.  On entering the interrupt I is cleared, so
//  as long as irq stays high no other one is serviced until EI is executed again.
// ============================================================================
`timescale 1ns/1ps
`default_nettype none

module cpu #(
    parameter [7:0] IRQ_VECTOR = 8'h08   // address of the IRQ handler
) (
    input  wire       clk,
    input  wire       rst,        // synchronous reset, active high
    input  wire       irq,        // interrupt request (level, active high)
    output wire       halted,     // 1 when the CPU is stopped (after HLT)
    input  wire [7:0] in_data,    // input bus (value of port `in_port`)
    output reg  [7:0] out_data,   // last value sent by OUT
    output reg        out_valid,  // 1-cycle pulse when OUT is executed
    output reg  [1:0] out_port,   // port of the last OUT
    output wire [1:0] in_port     // port read by the current IN instruction
);

    // ------------------------------------------------------------------
    //  Internal registers
    // ------------------------------------------------------------------
    reg [7:0] IR;        // current instruction
    reg [7:0] operand;   // second byte (immediate or address)
    reg [7:0] xop;       // second byte of a prefixed (0xFA) instruction
    reg       flag_z;    // Z (zero)
    reg       flag_c;    // C (carry / no-borrow)
    reg       flag_n;    // N (negative)
    reg       flag_v;    // V (signed overflow)
    reg       flag_i;    // I (interrupts enabled)
    reg       c16;       // carry of the low-byte add of ADCW/SUBW (S_EXEC2)
    reg       z16;       // "low byte == 0" of ADCW/SUBW (S_EXEC2 -> Z)
    reg [7:0] SP;        // stack pointer (starts at 0xF0)

    // ------------------------------------------------------------------
    //  control -> datapath signals
    // ------------------------------------------------------------------
    wire       ir_ld, opr_ld, pc_as_addr, pc_inc, pc_load;
    wire       rf_we, ram_we, flags_we, out_wr;
    wire [1:0] rf_waddr;
    wire [3:0] alu_op;
    wire       alu_sh, sel_imm, sel_mem;
    wire       sel_a_rs, sel_one, flags_c_we;
    wire       sp_inc, sp_dec, sp_as_addr, sel_ram_rs, pc_from_mem;
    wire       sel_ram_pc, ind, idx;
    wire       ext, xop_ld, rf_we2, addr_alu;
    wire       flag_ld, sel_ram_fl, pair16_ld, pair16_hi;
    wire       pc_from_vec, flag_i_set, flag_i_clear;
    wire       sel_in, io_op;

    // Current instruction: always from the IR register.  Decoding from
    // IR (and not from RAM) avoids a combinational loop control <-> RAM.
    wire [7:0] instr = IR;

    // ------------------------------------------------------------------
    //  Internal buses
    // ------------------------------------------------------------------
    wire [7:0] rf_rdata_rd;   // read of register rd (port 1)
    wire [7:0] rf_rdata_rs;   // read of register rs (port 2)
    wire [7:0] alu_a, alu_b, alu_y;
    wire       alu_c, alu_z, alu_n, alu_v;
    wire [7:0] ram_addr, ram_wdata, ram_rdata;
    wire [7:0] pc_q;

    // ------------------------------------------------------------------
    //  Control unit
    // ------------------------------------------------------------------
    control u_ctrl (
        .clk(clk), .rst(rst), .instr(instr), .fetched(ram_rdata), .xsub(xop[7:4]),
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
        .ext(ext), .xop_ld(xop_ld), .rf_we2(rf_we2), .addr_alu(addr_alu),
        .flag_ld(flag_ld), .sel_ram_fl(sel_ram_fl),
        .pair16_ld(pair16_ld), .pair16_hi(pair16_hi),
        .pc_from_vec(pc_from_vec), .flag_i_set(flag_i_set),
        .flag_i_clear(flag_i_clear),
        .sel_in(sel_in), .io_op(io_op),
        .halted(halted)
    );

    // ------------------------------------------------------------------
    //  ALU.  a = rd (or rs in INC/DEC); b = immediate, rs or the constant 1.
    // ------------------------------------------------------------------
    assign alu_a = sel_a_rs ? rf_rdata_rs : rf_rdata_rd;
    assign alu_b = sel_one  ? 8'd1 :
                   sel_imm  ? operand : rf_rdata_rs;

    // ADCW/SUBW: on the 2nd cycle the ALU takes the captured carry of the low
    // byte.  For SUBW it is inverted because c16 means "no borrow".
    wire alu_cin = pair16_hi ? (alu_sh ? ~c16 : c16) : flag_c;

    alu u_alu (
        .op(alu_op), .sh(alu_sh), .a(alu_a), .b(alu_b), .cin(alu_cin),
        .y(alu_y), .c(alu_c), .v(alu_v), .z(alu_z), .n(alu_n)
    );

    // ------------------------------------------------------------------
    //  Register file.  rd on port 1, rs on port 2.
    //  The data to write comes from RAM (LD/POP) or from the ALU.
    // ------------------------------------------------------------------
    wire [7:0] rf_wdata = sel_in  ? in_data :
                          sel_mem ? ram_rdata : alu_y;

    // ------------------------------------------------------------------
    //  I/O ports.  The ported form (0xF8 OUT / 0xF9 IN) takes the
    //  port from `operand[1:0]`; the 1-byte ones (OUT/IN) use port 0.
    // ------------------------------------------------------------------
    wire [1:0] io_port = io_op ? operand[1:0] : 2'b00;
    assign in_port = io_port;

    // ------------------------------------------------------------------
    //  RAM.  Address = PC (FETCH/OPR), SP (stack), rs indirect, or
    //  `operand` (EXEC).  Data written = rd (ST), rs (PUSH), PC (CALL) or the
    //  flags byte (PUSHF).
    // ------------------------------------------------------------------
    wire [7:0] sp_addr = sp_inc ? (SP + 8'd1) : SP;  // POP/RET read SP+1

    assign ram_addr  = addr_alu ? alu_y
                     : ind ? rf_rdata_rs
                     : idx ? (rf_rdata_rs + operand)
                     : (pc_as_addr ? pc_q : (sp_as_addr ? sp_addr : operand));
    // Flags byte pushed by PUSHF: bit0 C, bit1 Z, bit2 N, bit3 V, bit4 I.
    wire [7:0] flags_byte = {3'b000, flag_i, flag_v, flag_n, flag_z, flag_c};

    assign ram_wdata = sel_ram_fl ? flags_byte :
                       sel_ram_rs ? rf_rdata_rs
                     : (sel_ram_pc ? pc_q : rf_rdata_rd);

    ram u_ram (
        .clk(clk), .we(ram_we), .addr(ram_addr), .wdata(ram_wdata), .rdata(ram_rdata)
    );

    // ------------------------------------------------------------------
    //  Register file.  In indirect mode the indices come from the 2nd byte;
    //  in prefixed (ext) mode they come from `xop` (rd = xop[3:2], rs = xop[1:0]).
    //  On the 2nd cycle of ADCW/SUBW (pair16_hi) both addresses point to the
    //  HIGH register of the pair (low | 1).
    // ------------------------------------------------------------------
    wire [1:0] rf_raddr1 = pair16_hi ? {xop[3], 1'b1} :
                           ext ? xop[3:2] : ind ? operand[3:2] : instr[3:2];
    wire [1:0] rf_raddr2 = pair16_hi ? {xop[1], 1'b1} :
                           ext ? xop[1:0] : ind ? operand[1:0] : instr[1:0];
    wire [1:0] rf_waddr_m = pair16_hi ? {xop[3], 1'b1} :
                            ext ? xop[3:2] : ind ? operand[3:2] : rf_waddr;

    regfile u_rf (
        .clk(clk), .rst(rst), .we(rf_we), .waddr(rf_waddr_m), .wdata(rf_wdata),
        .we2(rf_we2), .waddr2(xop[1:0]), .wdata2(rf_rdata_rd),
        .raddr1(rf_raddr1), .rdata1(rf_rdata_rd),
        .raddr2(rf_raddr2), .rdata2(rf_rdata_rs)
    );

    // ------------------------------------------------------------------
    //  PC.  Jumps to `operand` (JMP/Jcc) or to the value from the stack (RET).
    // ------------------------------------------------------------------
    wire [7:0] pc_din = pc_from_vec ? IRQ_VECTOR :
                        pc_from_mem ? ram_rdata : operand;

    pc u_pc (
        .clk(clk), .rst(rst), .load(pc_load), .inc(pc_inc), .d_in(pc_din), .q(pc_q)
    );

    // ------------------------------------------------------------------
    //  Synchronous registers
    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (rst) begin
            IR       <= 8'h00;
            operand  <= 8'h00;
            xop      <= 8'h00;
            flag_z   <= 1'b0;
            flag_c   <= 1'b0;
            flag_n   <= 1'b0;
            flag_v   <= 1'b0;
            flag_i   <= 1'b0;
            c16      <= 1'b0;
            z16      <= 1'b0;
`ifdef FPGA_RAM64
            SP       <= 8'h3F;   // stack in reduced RAM (64 bytes)
`else
            SP       <= 8'hF0;   // stack in full RAM (256 bytes)
`endif
            out_data <= 8'h00;
            out_valid<= 1'b0;
            out_port <= 2'b00;
        end else begin
            if (ir_ld)    IR      <= ram_rdata;
            if (opr_ld)   operand <= ram_rdata;
            if (xop_ld)   xop     <= ram_rdata;
            if (pair16_ld) begin   // ADCW/SUBW: carry and "low == 0" of S_EXEC
                c16 <= alu_c;
                z16 <= alu_z;
            end
            if (flags_we) begin
                // On the 2nd cycle of ADCW/SUBW Z is the 16-bit zero.
                flag_z <= pair16_hi ? (z16 & alu_z) : alu_z;
                flag_n <= alu_n;
                flag_v <= alu_v;
            end
            if (flags_c_we)  flag_c <= alu_c;
            if (flag_i_set)   flag_i <= 1'b1;
            if (flag_i_clear) flag_i <= 1'b0;
            if (flag_ld) begin      // POPF: flags byte taken from the stack
                flag_c <= ram_rdata[0];
                flag_z <= ram_rdata[1];
                flag_n <= ram_rdata[2];
                flag_v <= ram_rdata[3];
                flag_i <= ram_rdata[4];
            end
            if (sp_dec)      SP <= SP - 8'd1;
            else if (sp_inc) SP <= SP + 8'd1;
            if (out_wr) begin
                out_data <= rf_rdata_rd;
                out_port <= io_port;
            end
            out_valid <= out_wr;   // one-cycle pulse after OUT
        end
    end

endmodule

`default_nettype wire
