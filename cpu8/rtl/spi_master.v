// ============================================================================
//  spi.v - SPI master (mode 0, MSB first, 8 bits)
//
//  Minimal SPI master for the FPGA I/O bus.  It is started by a one-cycle
//  pulse on `start`; it drives `cs_n` low for the whole transfer, toggles
//  `sclk` (idle low, mode 0) and shifts out `tx_data` on `mosi` while
//  sampling `miso` into `rx_data`.  `busy` is high during the transfer and
//  `done` pulses one cycle when it completes.
//
//  SCLK = clk / (2*DIV).  DIV must be >= 1.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module spi_master #(
    parameter integer DIV = 4
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       start,
    input  wire [7:0] tx_data,
    output reg        mosi,
    input  wire       miso,
    output reg        sclk,
    output reg        cs_n,
    output reg        busy,
    output reg        done,
    output reg  [7:0] rx_data
);

  localparam [1:0] S_IDLE = 2'd0;
  localparam [1:0] S_RUN = 2'd1;
  localparam [1:0] S_DONE = 2'd2;

  reg [1:0] state;
  reg [7:0] sh_tx;
  reg [7:0] sh_rx;
  reg [2:0] bit_idx;
  reg [3:0] div_cnt;
  reg [3:0] half_cnt;

  always @(posedge clk) begin
    if (rst) begin
      state    <= S_IDLE;
      mosi     <= 1'b0;
      sclk     <= 1'b0;
      cs_n     <= 1'b1;
      busy     <= 1'b0;
      done     <= 1'b0;
      rx_data  <= 8'h00;
      sh_tx    <= 8'h00;
      sh_rx    <= 8'h00;
      bit_idx  <= 3'd7;
      div_cnt  <= 4'd0;
      half_cnt <= 4'd0;
    end else begin
      done <= 1'b0;
      case (state)
        S_IDLE: begin
          cs_n <= 1'b1;
          sclk <= 1'b0;
          busy <= 1'b0;
          if (start) begin
            sh_tx   <= tx_data;
            sh_rx   <= 8'h00;
            bit_idx <= 3'd7;
            mosi    <= tx_data[7];
            cs_n    <= 1'b0;
            busy    <= 1'b1;
            div_cnt <= 4'd0;
            half_cnt <= 4'd0;
            state   <= S_RUN;
          end
        end
        S_RUN: begin
          if (div_cnt == DIV - 1) begin
            div_cnt <= 4'd0;
            sclk <= ~sclk;
            if (sclk == 1'b0) begin
              // rising edge: sample MISO into the current bit
              sh_rx[bit_idx] <= miso;
            end else begin
              // falling edge: advance to the next bit
              if (bit_idx != 3'd0) begin
                bit_idx <= bit_idx - 3'd1;
                mosi    <= sh_tx[bit_idx - 3'd1];
              end
            end
            if (half_cnt == 4'd15) begin
              state <= S_DONE;
            end else begin
              half_cnt <= half_cnt + 4'd1;
            end
          end else begin
            div_cnt <= div_cnt + 4'd1;
          end
        end
        S_DONE: begin
          cs_n    <= 1'b1;
          sclk    <= 1'b0;
          busy    <= 1'b0;
          mosi    <= 1'b1;
          rx_data <= sh_rx;
          done    <= 1'b1;
          state   <= S_IDLE;
        end
        default: state <= S_IDLE;
      endcase
    end
  end

endmodule

`default_nettype wire
