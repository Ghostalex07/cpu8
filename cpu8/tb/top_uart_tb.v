`timescale 1ns / 1ps
`default_nettype none
// ============================================================================
//  top_uart_tb.v - UART console integration test
//
//  Phase 1 loads an echo program (IN 1,A / OUT 0,A / OUT 1,A / JMP) and sends
//  bytes through `uart_rx` at the same divisor the top uses (DIV=8 for speed).
//  It checks that each byte is echoed on `uart_tx`, shown on the LEDs and
//  acknowledged (so a second byte does not raise an overrun).
//
//  Phase 2 reloads RAM with a status-polling program (IN 3,A / OUT 0,A / JMP)
//  and sends two bytes without reading them between frames: the status port
//  must report rx_ready and rx_overrun, and must not clear them by itself.
// ============================================================================
module top_uart_tb;

  localparam integer DIV = 8;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg  [7:0] pmod_in = 8'hFF;
  reg        uart_rx = 1'b1;
  wire       uart_tx;
  wire [4:0] led;

  top #(
      .UART_DIV(DIV),
      .TIMER_TICKS_PER_MS(4)
  ) dut (
      .clk(clk),
      .pmod_in(pmod_in),
      .uart_rx(uart_rx),
      .uart_tx(uart_tx),
      .led(led)
  );

  integer errors = 0;
  integer k;

  task send_byte;
    input [7:0] value;
    integer i;
    begin
      uart_rx = 1'b0;  // start bit
      repeat (DIV) @(posedge clk);
      for (i = 0; i < 8; i = i + 1) begin
        uart_rx = value[i];
        repeat (DIV) @(posedge clk);
      end
      uart_rx = 1'b1;  // stop bit
      repeat (DIV) @(posedge clk);
    end
  endtask

  task recv_byte;
    output [7:0] value;
    integer i;
    begin
      @(negedge uart_tx);  // start bit
      repeat (DIV + DIV / 2) @(posedge clk);  // middle of bit 0
      for (i = 0; i < 8; i = i + 1) begin
        value[i] = uart_tx;
        repeat (DIV) @(posedge clk);
      end
      // The last repeat left us in the middle of the stop bit.
      if (uart_tx !== 1'b1) begin
        $display("  FAIL: UART TX stop bit is low");
        errors = errors + 1;
      end
    end
  endtask

  reg [7:0] prog[0:15];
  integer n;

  task load_program;
    begin
      for (k = 0; k < 256; k = k + 1) dut.cpu_i.u_ram.mem[k] = 8'h00;
      for (k = 0; k < n; k = k + 1) dut.cpu_i.u_ram.mem[k] = prog[k];
    end
  endtask

  task restart_cpu;
    begin
      repeat (2) @(posedge clk);
      dut.por = 4'h0;
      repeat (12) @(posedge clk);
      if (dut.rst !== 1'b0) begin
        $display("  FAIL: the CPU did not leave reset");
        errors = errors + 1;
      end
    end
  endtask

  reg [7:0] echoed;

  initial begin
    uart_rx = 1'b1;

    // ---------------------------------------------------------------
    //  Phase 1: poll rx_ready, then echo (IN 3,A / SHR A / JNC /
    //  IN 1,A / OUT 0,A / OUT 1,A / JMP).
    // ---------------------------------------------------------------
    n = 13;
    prog[0] = 8'hF9;
    prog[1] = 8'h03;
    prog[2] = 8'hB1;
    prog[3] = 8'hD3;
    prog[4] = 8'h00;
    prog[5] = 8'hF9;
    prog[6] = 8'h01;
    prog[7] = 8'hF8;
    prog[8] = 8'h00;
    prog[9] = 8'hF8;
    prog[10] = 8'h01;
    prog[11] = 8'hC0;
    prog[12] = 8'h00;
    load_program;
    wait (dut.rst == 1'b0);
    repeat (8) @(posedge clk);

    fork
      send_byte(8'h55);
      recv_byte(echoed);
    join
    if (echoed !== 8'h55) begin
      $display("  FAIL: sent 55, echoed %02X", echoed);
      errors = errors + 1;
    end
    if (dut.led !== 5'h15) begin
      $display("  FAIL: sent 55, LED=%02X", dut.led);
      errors = errors + 1;
    end

    fork
      send_byte(8'hA3);
      recv_byte(echoed);
    join
    if (echoed !== 8'hA3) begin
      $display("  FAIL: sent A3, echoed %02X", echoed);
      errors = errors + 1;
    end
    if (dut.led !== 5'h03) begin
      $display("  FAIL: sent A3, LED=%02X", dut.led);
      errors = errors + 1;
    end

    // ---------------------------------------------------------------
    //  Phase 2: status port (IN 3,A / OUT 0,A / JMP 0)
    // ---------------------------------------------------------------
    n = 6;
    prog[0] = 8'hF9;
    prog[1] = 8'h03;
    prog[2] = 8'hF8;
    prog[3] = 8'h00;
    prog[4] = 8'hC0;
    prog[5] = 8'h00;
    load_program;
    restart_cpu;
    repeat (8) @(posedge clk);

    // Two full frames without an acknowledgement in between: the first byte
    // sets rx_ready and the second one must raise rx_overrun.
    send_byte(8'h11);
    send_byte(8'h22);
    repeat (20) @(posedge clk);
    #1;
    if (dut.led !== 5'b00101) begin
      $display("  FAIL: status LED=%02X, expected 05 (ready + overrun)", dut.led);
      errors = errors + 1;
    end
    repeat (20) @(posedge clk);
    #1;
    if (dut.led !== 5'b00101) begin
      $display("  FAIL: status changed to %02X without an IN (cleared too early)", dut.led);
      errors = errors + 1;
    end

    if (errors == 0) $display("TOP UART: ALL TESTS PASSED");
    else $display("TOP UART: %0d FAILURES", errors);

    if (errors != 0) $fatal(1, "TOP UART: there are failures, check above");
    $finish;
  end

endmodule

`default_nettype wire
