// ============================================================================
//  i2c_master.v - I2C master, standard mode, single-byte read/write
//
//  Open-drain SDA: drive low when sda_oe=1, release otherwise.  sda_in is the
//  sampled SDA line (after the pull-up).  DIV = cycles per quarter SCL period.
// ============================================================================
`timescale 1ns / 1ps
`default_nettype none

module i2c_master #(
    parameter integer DIV = 4
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       start,
    input  wire       rw,
    input  wire [6:0] addr,
    input  wire [7:0] data_in,
    input  wire       sda_in,
    output reg  [7:0] data_out,
    output reg        busy,
    output reg        done,
    output reg        ack_error,
    output reg        scl,
    output reg        sda_oe
);

  localparam [3:0] S_IDLE = 4'd0;
  localparam [3:0] S_START = 4'd1;
  localparam [3:0] S_ADDR = 4'd2;
  localparam [3:0] S_ACK1 = 4'd3;
  localparam [3:0] S_DATA = 4'd4;
  localparam [3:0] S_ACK2 = 4'd5;
  localparam [3:0] S_STOP = 4'd6;
  localparam [3:0] S_DONE = 4'd7;

  reg  [ 3:0] state;
  reg  [ 1:0] phase;
  reg  [31:0] qcnt;
  reg  [ 3:0] bit_idx;
  reg  [ 7:0] sh;
  reg         read_mode;
  reg         ack_bit;
  reg  [ 7:0] rx_byte;

  // scl level from phase: high in phases 1,2; low in 0,3
  wire        scl_level = (phase == 2'd1) || (phase == 2'd2);

  always @(posedge clk) begin
    if (rst) begin
      state     <= S_IDLE;
      phase     <= 2'd0;
      qcnt      <= 32'd0;
      bit_idx   <= 4'd0;
      sh        <= 8'd0;
      read_mode <= 1'b0;
      ack_bit   <= 1'b0;
      rx_byte   <= 8'd0;
      busy      <= 1'b0;
      done      <= 1'b0;
      ack_error <= 1'b0;
      scl       <= 1'b1;
      sda_oe    <= 1'b0;
      data_out  <= 8'd0;
    end else begin
      done <= 1'b0;
      case (state)
        S_IDLE: begin
          scl    <= 1'b1;
          sda_oe <= 1'b0;
          busy   <= 1'b0;
          if (start) begin
            read_mode <= rw;
            sh        <= {addr, rw};
            busy      <= 1'b1;
            ack_error <= 1'b0;
            state     <= S_START;
            phase     <= 2'd0;
            qcnt      <= 32'd0;
          end
        end

        S_START: begin
          // SCL high phase 0/1, SDA high->low creates start
          scl    <= (phase >= 2'd2) ? 1'b0 : 1'b1;
          sda_oe <= (phase >= 2'd1) ? 1'b1 : 1'b0;
          if (qcnt == DIV - 1) begin
            qcnt <= 32'd0;
            if (phase == 2'd3) begin
              phase   <= 2'd0;
              bit_idx <= 4'd7;
              state   <= S_ADDR;
            end else phase <= phase + 2'd1;
          end else qcnt <= qcnt + 32'd1;
        end

        S_ADDR: begin
          scl    <= scl_level;
          // master drives SDA with current bit (0 -> drive low)
          sda_oe <= (sh[bit_idx]) ? 1'b0 : 1'b1;
          if (qcnt == DIV - 1) begin
            qcnt <= 32'd0;
            if (phase == 2'd3) begin
              phase <= 2'd0;
              if (bit_idx == 4'd0) state <= S_ACK1;
              else bit_idx <= bit_idx - 4'd1;
            end else phase <= phase + 2'd1;
          end else qcnt <= qcnt + 32'd1;
        end

        S_ACK1: begin
          // release SDA, sample ACK in phase 2
          sda_oe <= 1'b0;
          scl    <= scl_level;
          if (qcnt == DIV - 1) begin
            qcnt <= 32'd0;
            if (phase == 2'd2) begin
              ack_bit <= sda_in;  // 0 = ACK
            end
            if (phase == 2'd3) begin
              phase <= 2'd0;
              if (ack_bit) ack_error <= 1'b1;
              if (read_mode) begin
                bit_idx <= 4'd7;
                rx_byte <= 8'd0;
                state   <= S_DATA;
              end else begin
                bit_idx <= 4'd7;
                sh      <= data_in;
                state   <= S_DATA;
              end
            end else phase <= phase + 2'd1;
          end else qcnt <= qcnt + 32'd1;
        end

        S_DATA: begin
          if (read_mode) begin
            sda_oe <= 1'b0; // slave drives
            scl    <= scl_level;
            if (qcnt == DIV - 1) begin
              qcnt <= 32'd0;
              if (phase == 2'd2) begin
                rx_byte[bit_idx] <= sda_in;
              end
              if (phase == 2'd3) begin
                phase <= 2'd0;
                if (bit_idx == 4'd0) begin
                  data_out <= {rx_byte[7:1], sda_in};
                  state    <= S_ACK2;
                end else bit_idx <= bit_idx - 4'd1;
              end else phase <= phase + 2'd1;
            end else qcnt <= qcnt + 32'd1;
          end else begin
            scl    <= scl_level;
            sda_oe <= (sh[bit_idx]) ? 1'b0 : 1'b1;
            if (qcnt == DIV - 1) begin
              qcnt <= 32'd0;
              if (phase == 2'd3) begin
                phase <= 2'd0;
                if (bit_idx == 4'd0) state <= S_ACK2;
                else bit_idx <= bit_idx - 4'd1;
              end else phase <= phase + 2'd1;
            end else qcnt <= qcnt + 32'd1;
          end
        end

        S_ACK2: begin
          if (read_mode) begin
            // master sends NACK (release SDA high)
            sda_oe <= 1'b0;
          end else begin
            sda_oe <= 1'b0;  // release, slave ACKs
          end
          scl <= scl_level;
          if (qcnt == DIV - 1) begin
            qcnt <= 32'd0;
            if (phase == 2'd2) begin
              if (!read_mode) ack_bit <= sda_in;
            end
            if (phase == 2'd3) begin
              phase <= 2'd0;
              if (!read_mode && ack_bit) ack_error <= 1'b1;
              state <= S_STOP;
            end else phase <= phase + 2'd1;
          end else qcnt <= qcnt + 32'd1;
        end

        S_STOP: begin
          scl    <= (phase >= 2'd1) ? 1'b1 : 1'b0;
          sda_oe <= (phase >= 2'd2) ? 1'b0 : 1'b1;
          if (qcnt == DIV - 1) begin
            qcnt <= 32'd0;
            if (phase == 2'd3) begin
              phase <= 2'd0;
              busy  <= 1'b0;
              done  <= 1'b1;
              state <= S_DONE;
            end else phase <= phase + 2'd1;
          end else qcnt <= qcnt + 32'd1;
        end

        S_DONE: begin
          scl    <= 1'b1;
          sda_oe <= 1'b0;
          busy   <= 1'b0;
          state  <= S_IDLE;
        end

        default: state <= S_IDLE;
      endcase
    end
  end

endmodule

`default_nettype wire
