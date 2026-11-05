`timescale 1ns / 1ps
`default_nettype none
// ============================================================================
//  top.v - FPGA implementation for the iCEstick (iCE40HX1K, TQ144)
//
//  It is the "board": it instantiates the CPU plus three peripherals behind
//  the I/O ports described in docs/ISA.md:
//
//      port 0  OUT -> 5 LEDs            IN -> Pmod byte (synchronized)
//      port 1  OUT -> start UART TX     IN -> last byte received by the UART
//      port 2  OUT -> timer period (ms) IN -> bit0: timer interrupt pending
//      port 3  OUT -> watchdog period (ms)  IN -> console status:
//                                            bit0 rx_ready
//                                            bit1 tx_busy
//                                            bit2 rx_overrun
//                                            bit3 rx_busy
//                                            bit4 watchdog timeout
//
//  Reading port 1 acknowledges the received byte (the CPU's `in_valid` is the
//  strobe).  Writing 0 to port 2 disables the timer and clears its interrupt.
//  The timer and the watchdog are the interrupt sources wired to the CPU.
//
//  The UART uses the second FT2232H channel, which the iCEstick exposes on
//  pins 8 (TX) and 9 (RX); it shows up as /dev/ttyUSB1 at 115200 8N1.  The
//  Pmod connector remains the 8-bit input of port 0, so no pin is sacrificed.
//
//  The program is loaded into the CPU RAM at synthesis time: ram.v includes a
//  $readmemh("fpga/program.hex") under `ifdef RAM_INIT (the Makefile defines
//  it).
// ============================================================================
module top #(
    parameter integer UART_DIV = 104,  // 12 MHz / 115200 = 104.17
    parameter integer TIMER_TICKS_PER_MS = 12_000  // clock cycles per ms
) (
    input  wire       clk,      // 12 MHz clock (pin 21 on the iCEstick)
    input  wire [7:0] pmod_in,  // Pmod data pins (see the PCF)
    input  wire       uart_rx,  // serial RX from the FT2232H (pin 9)
    output wire       uart_tx,  // serial TX to the FT2232H (pin 8)
    output wire [4:0] led       // 5 LEDs (D1..D5)
);

  // Power-on reset: rst=1 during the first 8 cycles after start-up.
  reg [3:0] por = 4'd0;
  wire rst = ~por[3];

  always @(posedge clk) if (por != 4'hF) por <= por + 4'd1;

  // The Pmod pins are asynchronous: two flip-flops resynchronize them to clk.
  // The PCF enables the internal pull-ups, so an unconnected bus reads 0xFF.
  reg [7:0] in_meta = 8'hFF;
  reg [7:0] in_sync = 8'hFF;

  always @(posedge clk) begin
    in_meta <= pmod_in;
    in_sync <= in_meta;
  end

  // ------------------------------------------------------------------
  //  CPU
  // ------------------------------------------------------------------
  wire       halted;
  wire       out_valid;
  wire [7:0] out_data;
  wire [1:0] out_port;
  wire [1:0] in_port;
  wire       in_valid;
  wire [7:0] in_data;

  wire       timer_irq;
  wire       wdog_irq;
  wire       wdog_timeout;
  wire       cpu_irq = timer_irq | wdog_irq;

  // Low power: once the CPU executes HLT it stops, so its clock can be frozen
  // (the peripherals keep their own clock and the device draws less dynamic
  // power).  HLT is terminal in this ISA, so there is no wake-up to support.
  wire       cpu_clk = clk & (rst | ~halted);

  cpu #(
      .IRQ_VECTOR(8'h08)
  ) cpu_i (
      .clk(cpu_clk),
      .rst(rst),
      .irq(cpu_irq),
      .halted(halted),
      .in_data(in_data),
      .out_data(out_data),
      .out_valid(out_valid),
      .out_port(out_port),
      .in_port(in_port),
      .in_valid(in_valid)
  );

  // ------------------------------------------------------------------
  //  UART console (port 1)
  // ------------------------------------------------------------------
  wire [7:0] rx_data;
  wire rx_ready, rx_overrun, rx_busy;
  wire tx_busy;

  uart_tx #(
      .DIV(UART_DIV)
  ) uart_tx_i (
      .clk(clk),
      .rst(rst),
      .start(out_valid && (out_port == 2'd1)),
      .data(out_data),
      .tx(uart_tx),
      .busy(tx_busy)
  );

  uart_rx #(
      .DIV(UART_DIV)
  ) uart_rx_i (
      .clk(clk),
      .rst(rst),
      .rx(uart_rx),
      .rd(in_valid && (in_port == 2'd1)),
      .data(rx_data),
      .ready(rx_ready),
      .overrun(rx_overrun),
      .busy(rx_busy)
  );

  // ------------------------------------------------------------------
  //  Programmable timer (port 2)
  // ------------------------------------------------------------------
  timer #(
      .TICKS_PER_MS(TIMER_TICKS_PER_MS)
  ) timer_i (
      .clk(clk),
      .rst(rst),
      .wr(out_valid && (out_port == 2'd2)),
      .period(out_data),
      .irq(timer_irq)
  );

  // ------------------------------------------------------------------
  //  Watchdog (port 6)
  // ------------------------------------------------------------------
  watchdog #(
      .TICKS_PER_MS(TIMER_TICKS_PER_MS)
  ) wdog_i (
      .clk(clk),
      .rst(rst),
      .wr(out_valid && (out_port == 2'd3)),
      .period(out_data),
      .irq(wdog_irq),
      .timeout(wdog_timeout)
  );

  // ------------------------------------------------------------------
  //  Input port mux
  // ------------------------------------------------------------------
  reg [7:0] in_mux;

  always @(*) begin
    case (in_port)
      2'd0: in_mux = in_sync;
      2'd1: in_mux = rx_data;
      2'd2: in_mux = {7'b0, timer_irq};
      2'd3: in_mux = {3'b0, wdog_timeout, rx_busy, rx_overrun, tx_busy, rx_ready};
      default: in_mux = 8'h00;
    endcase
  end

  assign in_data = in_mux;

  // ------------------------------------------------------------------
  //  LEDs: low bits of the last value written to port 0.  If the CPU has
  //  stopped (HLT), they all turn on.
  // ------------------------------------------------------------------
  reg [4:0] led_r = 5'b00000;

  always @(posedge clk) begin
    if (rst) led_r <= 5'b00000;
    else if (out_valid && (out_port == 2'd0)) led_r <= out_data[4:0];
  end

  assign led = halted ? 5'b11111 : led_r;

endmodule

`default_nettype wire
