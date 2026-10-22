// ============================================================================
//  regfile_fv.sv - Formal properties of the register file (rtl/regfile.v)
//
//  A small shadow model with the documented behaviour (synchronous reset, two
//  write ports where port 2 wins on a collision, untouched registers hold) is
//  compared against both combinational read ports for every possible read
//  address.  This checks the reset, the write enables and the hold behaviour
//  without relying on hierarchical references into the memory array.
//
//  Run with `make formal` (SymbiYosys, see formal/regfile.sby, BMC depth 5).
// ============================================================================
`default_nettype none

module regfile_fv (
    input wire       clk,
    input wire       rst,
    input wire       we,
    input wire [1:0] waddr,
    input wire [7:0] wdata,
    input wire       we2,
    input wire [1:0] waddr2,
    input wire [7:0] wdata2,
    input wire [1:0] raddr1,
    input wire [1:0] raddr2
);

    wire [7:0] rdata1, rdata2;

    regfile dut (
        .clk   (clk),
        .rst   (rst),
        .we    (we),
        .waddr (waddr),
        .wdata (wdata),
        .we2   (we2),
        .waddr2(waddr2),
        .wdata2(wdata2),
        .raddr1(raddr1),
        .raddr2(raddr2),
        .rdata1(rdata1),
        .rdata2(rdata2)
    );

    // Shadow model: same reset and write rules as the RTL.  Port 2 is written
    // after port 1 so it wins when both select the same register.
    reg [7:0] model[0:3];
    reg model_valid = 1'b0;

    always @(posedge clk) begin
        if (rst) begin
            model[0] <= 8'h00;
            model[1] <= 8'h00;
            model[2] <= 8'h00;
            model[3] <= 8'h00;
            model_valid <= 1'b1;
        end else begin
            if (we) model[waddr] <= wdata;
            if (we2) model[waddr2] <= wdata2;
        end
    end

    initial assume (rst);

    always @* begin
        if (model_valid) begin
            assert (rdata1 == model[raddr1]);
            assert (rdata2 == model[raddr2]);
        end
    end

endmodule

`default_nettype wire
