// Chisel 生成 RTL 的单元级适配壳：端口命名与 rtl/verilog/VDot.v 对齐，便于复用同一测试台
`timescale 1ns/1ps
`default_nettype none
module VDot #(
    parameter integer VLEN  = 128,
    parameter integer K     = 8,
    parameter integer ACC_W = 20,
    parameter integer OUT_W = 32
) (
    input  logic            clk,
    input  logic            reset,
    input  logic            in_valid,
    input  logic [VLEN-1:0] in_vs1,
    input  logic [VLEN-1:0] in_vs2,
    input  logic            in_vl_zero,
    input  logic            in_vm,
    input  logic [2:0]      in_sew,
    input  logic [2:0]      in_lmul,
    input  logic [1:0]      in_mode,
    output logic [VLEN-1:0] out_vd,
    output logic            out_valid,
    output logic            out_illegal,
    output logic            out_dirty
);
  VDotCore u_vdot_core (
    .clock            (clk),
    .reset            (reset),
    .io_in_valid      (in_valid),
    .io_in_vs1        (in_vs1),
    .io_in_vs2        (in_vs2),
    .io_in_vlZero     (in_vl_zero),
    .io_in_vm         (in_vm),
    .io_in_sew        (in_sew),
    .io_in_lmul       (in_lmul),
    .io_in_mode       (in_mode),
    .io_out_vd        (out_vd),
    .io_out_valid     (out_valid),
    .io_out_illegal   (out_illegal),
    .io_out_dirty     (out_dirty)
  );
endmodule
`default_nettype wire
