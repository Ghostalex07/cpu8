`timescale 1ns / 1ps
`default_nettype none
// ============================================================================
//  cpu_dump_tb.v - MACHINE-READABLE dump of the state, for differential fuzz
//
//  Runs a program (``+hex=<path>``) and, for each instruction RETIRED,
//  prints a line with the architectural state.  The output has the same
//  format as the reference model ``tools/iss.py``, so that
//  ``tools/difftest.py`` compares them line by line:
//
//      I <pc> <ir> <a> <b> <c> <d> <z> <cf> <n> <v> <sp> <pcnext> <ov> <odata> <oport>
//      M <256 bytes>                (final RAM contents)
//      END <n_instructions>
//
//  Details:
//   - The RAM is set to ZERO before loading the program (ram.v has no reset,
//     so in iverilog the unloaded locations would be X).  The ISS also assumes
//     RAM at zero.
//   - Input as in the other tbs: in_data = 0x10 + port.
//   - irq is left at 0 (the differential fuzz does not cover IRQ; irqtest does).
// ============================================================================

module cpu_dump_tb;

  reg clk = 0, rst = 1;
  wire irq;
  reg [7:0] in_data = 8'h00;
  wire halted, out_valid;
  wire [7:0] out_data;
  wire [1:0] in_port, out_port;

  cpu #(
      .IRQ_VECTOR(8'h08)
  ) dut (
      .clk(clk),
      .rst(rst),
      .irq(irq),
      .halted(halted),
      .out_data(out_data),
      .out_valid(out_valid),
      .in_data(in_data),
      .in_port(in_port),
      .out_port(out_port)
  );

  always #5 clk = ~clk;

  // Input: value of the requested port (port 0 -> 0x10, port 1 -> 0x11, ...).
  always @(*) in_data = 8'h10 + {6'b0, in_port};

  reg [8*256-1:0] hexfile;
  integer maxi, i, dummy;
  integer n = 0;
  // irq level: it is asserted once >= irq_at instructions have been retired
  // (same convention as tools/iss.py).  By default irq_at is huge => no
  // interrupt is ever serviced, so the behaviour without +irq does not change.
  integer irq_at = 100000000;
  assign irq = (n >= irq_at);

  // PC of the current instruction: latched when the IR is loaded (S_FETCH).
  reg [7:0] trace_pc;
  always @(posedge clk) if (dut.ir_ld) trace_pc <= dut.pc_q;

  // The instruction "retires" on the edge in which S_EXEC is executed; it is
  // detected on the following negedge (the registers are already updated).
  // Pair ops (ADCW/SUBW) run one extra cycle in S_EXEC2 and IN runs one extra
  // cycle in S_IN, so for them the sample is deferred to the negedge after
  // that cycle.
  reg [2:0] st_d = 3'd0;
  localparam [2:0] S_EXEC = 3'd2, S_EXEC2 = 3'd6, S_IN = 3'd7;

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
    maxi  = 5000;
    dummy = $value$plusargs("max=%d", maxi);
    dummy = $value$plusargs("irq=%d", irq_at);
    for (i = 0; i < 256; i = i + 1) dut.u_ram.mem[i] = 8'h00;
    $readmemh(hexfile, dut.u_ram.mem);
    n   = 0;
    rst = 1;
    repeat (2) @(posedge clk);
    @(negedge clk) rst = 0;
  end

  always @(negedge clk) begin
    #1;
    if (!rst) begin
      if ((st_d == S_EXEC && dut.u_ctrl.state != S_EXEC2 &&
           dut.u_ctrl.state != S_IN) || st_d == S_EXEC2 || st_d == S_IN) begin
        $display("I %02h %02h %02h %02h %02h %02h %b %b %b %b %02h %02h %b %02h %02h", trace_pc,
                 dut.IR, dut.u_rf.regs[0], dut.u_rf.regs[1], dut.u_rf.regs[2], dut.u_rf.regs[3],
                 dut.flag_z, dut.flag_c, dut.flag_n, dut.flag_v, dut.SP, dut.pc_q, out_valid,
                 out_data, out_port);
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
