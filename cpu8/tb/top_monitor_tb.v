`timescale 1ns / 1ps
`default_nettype none
// ============================================================================
//  top_monitor_tb.v - integration test for programs/monitor.asm
//
//  The top runs the mini serial monitor.  The bench sends 'H' on the UART RX
//  line and captures the TX line, checking that the banner and the help line
//  are printed.  UART_DIV is reduced to 4 to keep the simulation short; the
//  monitor logic itself is baud-independent.
// ============================================================================
module top_monitor_tb;

  localparam integer DIV = 4;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg  [7:0] pmod_in = 8'hFF;
  reg        rx_line = 1'b1;
  wire [4:0] led;
  wire       uart_tx;

  top #(
      .UART_DIV(DIV)
  ) dut (
      .clk(clk),
      .pmod_in(pmod_in),
      .uart_rx(rx_line),
      .uart_tx(uart_tx),
      .led(led)
  );

  // Capture the TX line with a second UART receiver at the same divisor.
  wire [7:0] cap_data;
  wire cap_ready, cap_overrun;
  reg cap_rd = 1'b0;

  uart_rx #(
      .DIV(DIV)
  ) cap (
      .clk(clk),
      .rst(1'b0),
      .rx(uart_tx),
      .rd(cap_rd),
      .data(cap_data),
      .ready(cap_ready),
      .overrun(cap_overrun),
      .busy()
  );

  reg [7:0] rxbuf[0:255];
  integer n = 0;

  always @(posedge clk) begin
    if (cap_ready && !cap_rd) begin
      rxbuf[n] = cap_data;
      n        = n + 1;
      cap_rd <= 1'b1;
    end else begin
      cap_rd <= 1'b0;
    end
  end

  task send_byte(input [7:0] b);
    integer i;
    begin
      rx_line = 1'b0;
      repeat (DIV) @(posedge clk);
      for (i = 0; i < 8; i = i + 1) begin
        rx_line = b[i];
        repeat (DIV) @(posedge clk);
      end
      rx_line = 1'b1;
      repeat (DIV) @(posedge clk);
    end
  endtask

  // Expected byte strings (NUL terminators are not transmitted).  Written as
  // numeric bytes because some simulators do not support "\r" in literals.
  localparam integer BANNER_N = 14;
  localparam integer HELP_N = 20;
  reg [7:0] exp_banner[0:BANNER_N-1];
  reg [7:0] exp_help[0:HELP_N-1];

  integer errors = 0;
  integer i;
  integer guard;

  initial begin
    exp_banner[0] = 8'h63;
    exp_banner[1] = 8'h70;
    exp_banner[2] = 8'h75;
    exp_banner[3] = 8'h38;
    exp_banner[4] = 8'h20;
    exp_banner[5] = 8'h6D;
    exp_banner[6] = 8'h6F;
    exp_banner[7] = 8'h6E;
    exp_banner[8] = 8'h69;
    exp_banner[9] = 8'h74;
    exp_banner[10] = 8'h6F;
    exp_banner[11] = 8'h72;
    exp_banner[12] = 8'h0D;
    exp_banner[13] = 8'h0A;

    exp_help[0] = 8'h63;
    exp_help[1] = 8'h6F;
    exp_help[2] = 8'h6D;
    exp_help[3] = 8'h6D;
    exp_help[4] = 8'h61;
    exp_help[5] = 8'h6E;
    exp_help[6] = 8'h64;
    exp_help[7] = 8'h73;
    exp_help[8] = 8'h3A;
    exp_help[9] = 8'h20;
    exp_help[10] = 8'h48;
    exp_help[11] = 8'h20;
    exp_help[12] = 8'h3D;
    exp_help[13] = 8'h20;
    exp_help[14] = 8'h68;
    exp_help[15] = 8'h65;
    exp_help[16] = 8'h6C;
    exp_help[17] = 8'h70;
    exp_help[18] = 8'h0D;
    exp_help[19] = 8'h0A;

    $readmemh("programs/monitor.hex", dut.cpu_i.u_ram.mem);

    // Wait for the POR and for the banner to be captured.
    wait (n >= BANNER_N);
    repeat (40) @(posedge clk);

    send_byte(8'h48);  // 'H'

    guard = 0;
    while (n < (BANNER_N + 1 + HELP_N) && guard < 20000) begin
      @(posedge clk);
      guard = guard + 1;
    end
    repeat (200) @(posedge clk);

    for (i = 0; i < BANNER_N; i = i + 1)
    if (rxbuf[i] != exp_banner[i]) begin
      $display("  FAIL: banner[%0d]=%02X expected %02X", i, rxbuf[i], exp_banner[i]);
      errors = errors + 1;
    end

    if (rxbuf[BANNER_N] != 8'h48) begin
      $display("  FAIL: echo=%02X expected 48", rxbuf[BANNER_N]);
      errors = errors + 1;
    end

    for (i = 0; i < HELP_N; i = i + 1)
    if (rxbuf[BANNER_N+1+i] != exp_help[i]) begin
      $display("  FAIL: help[%0d]=%02X expected %02X", i, rxbuf[BANNER_N+1+i], exp_help[i]);
      errors = errors + 1;
    end

    $display("  bytes received: %0d", n);
    if (errors == 0) $display("MONITOR: ALL TESTS PASSED");
    else $display("MONITOR: %0d FAILURES", errors);
    $finish;
  end

endmodule

`default_nettype wire
