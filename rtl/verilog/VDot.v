//=============================================================================
// VDot —— 香山昆明湖 V2 自定义向量点积功能单元（模块级 RTL）
//
// 语义（SEW=8, VLEN=128, K=8）：
//   S = sum_{i=0..7} sext8(vs1[i]) * sext8(vs2[i])
//   vd[OUT_W-1:0] = S（32 bit 二补码），vd[VLEN-1:OUT_W] = 0
//
// 微架构：3 级流水（EX1 乘 / EX2 加法树 / WB 格式化写回），无状态，全流水
//
// 说明：本文件是可在独立仿真环境中验证的等价 Verilog 实现；
//       接入香山时由 Chisel 包装（见 rtl/chisel/VDot.scala）复用同一数据通路语义。
//=============================================================================
`timescale 1ns/1ps
`default_nettype none

module VDot #(
    parameter integer VLEN  = 128,   // 向量寄存器位宽
    parameter integer K     = 8,     // 点积分组长度
    parameter integer ACC_W = 20,    // 内部累加位宽（>= 19）
    parameter integer OUT_W = 32     // 输出元素位宽
) (
    input  logic              clk,
    input  logic              reset,        // 同步复位，高有效

    // 请求侧（由向量发射框架驱动）
    input  logic              in_valid,
    // 语义只取两个源寄存器的低 64 bit（8 个 int8）；VLEN=128 接口的高 64 bit
    // 按 RVV 整寄存器语义保留但本单元不解引用，属预期行为，故局部豁免该告警。
    /* verilator lint_off UNUSEDSIGNAL */
    input  logic [VLEN-1:0]   in_vs1,
    input  logic [VLEN-1:0]   in_vs2,
    /* verilator lint_on UNUSEDSIGNAL */
    input  logic              in_vl_zero,   // vl == 0：不写回
    input  logic              in_vm,        // vm == 1 才合法
    // vtype.vsew 为 3 bit：0=e8（唯一合法），1=e16，2=e32，3=e64，4..7 保留。
    // 接口必须保留全部 3 bit，否则保留编码（如 vsew=4）被截断成 0 而误判合法。
    input  logic [2:0]        in_sew,
    input  logic [2:0]        in_lmul,      // 0: m1（唯一合法）

    // 写回侧
    output logic [VLEN-1:0]   out_vd,
    output logic              out_valid,    // 写回有效
    output logic              out_illegal,  // 非法指令（不写回）
    output logic              out_dirty     // vd 整寄存器脏
);

  // 语义固定 K=8；参数越界在例化（仿真启动）时报错
  initial begin
    if (K != 8)       $fatal(1, "VDot: K 必须为 8");
    if (ACC_W < 19)   $fatal(1, "VDot: ACC_W 必须 >= 19");
    if (OUT_W < ACC_W) $fatal(1, "VDot: OUT_W 必须 >= ACC_W");
  end

  //--------------------------------------------------------------------------
  // 合法性判定：仅支持 vm=1 / SEW=8 / LMUL=1
  //--------------------------------------------------------------------------
  logic legal;
  assign legal = in_vm && (in_sew == 3'd0) && (in_lmul == 3'd0);

  //--------------------------------------------------------------------------
  // EX1：K 路有符号 8x8 乘法
  //--------------------------------------------------------------------------
  logic signed [7:0]  a    [K];
  logic signed [7:0]  b    [K];
  logic signed [15:0] prod [K];

  genvar gi;
  generate
    for (gi = 0; gi < K; gi++) begin : g_mul
      assign a[gi]    = in_vs1[8*gi +: 8];
      assign b[gi]    = in_vs2[8*gi +: 8];
      assign prod[gi] = a[gi] * b[gi];
    end
  endgenerate

  //--------------------------------------------------------------------------
  // 流水寄存器：EX1 -> EX2（保存乘积与控制）
  //
  // valid 不单独寄存：写回由 s1_write 编码，"有效但不写回"仅出现在 vl==0，
  // 因此 (write, illegal) 已足以表达全部状态，省去无读者的 valid 触发器。
  //--------------------------------------------------------------------------
  logic              s1_illegal, s1_write;
  logic signed [15:0] s1_prod [K];

  always_ff @(posedge clk) begin
    if (reset) begin
      s1_illegal <= 1'b0;
      s1_write   <= 1'b0;
      for (int j = 0; j < K; j++) s1_prod[j] <= '0;
    end else begin
      s1_illegal <= in_valid && !legal;
      s1_write   <= in_valid && legal && !in_vl_zero;
      for (int j = 0; j < K; j++) s1_prod[j] <= prod[j];
    end
  end

  //--------------------------------------------------------------------------
  // EX2：基于已寄存乘积的加法树（8 -> 4 -> 2 -> 1，常数索引便于时序分析）
  //--------------------------------------------------------------------------
  logic signed [ACC_W-1:0] u0 [0:K-1];

  generate
    for (gi = 0; gi < K; gi++) begin : g_tree2_init
      assign u0[gi] = {{(ACC_W-16){s1_prod[gi][15]}}, s1_prod[gi]};
    end
  endgenerate

  logic signed [ACC_W-1:0] u1_0, u1_1, u1_2, u1_3;
  logic signed [ACC_W-1:0] u2_0, u2_1;
  logic signed [ACC_W-1:0] sum2;

  assign u1_0  = u0[0] + u0[1];
  assign u1_1  = u0[2] + u0[3];
  assign u1_2  = u0[4] + u0[5];
  assign u1_3  = u0[6] + u0[7];
  assign u2_0  = u1_0 + u1_1;
  assign u2_1  = u1_2 + u1_3;
  assign sum2  = u2_0 + u2_1;

  logic              s2_illegal, s2_write;
  logic signed [ACC_W-1:0] s2_sum;

  always_ff @(posedge clk) begin
    if (reset) begin
      s2_illegal <= 1'b0;
      s2_write   <= 1'b0;
      s2_sum     <= '0;
    end else begin
      s2_illegal <= s1_illegal;
      s2_write   <= s1_write;
      s2_sum     <= sum2;
    end
  end

  //--------------------------------------------------------------------------
  // WB：符号扩展至 OUT_W，高位通道清零，写回
  //--------------------------------------------------------------------------
  logic [VLEN-1:0] vd_c;
  assign vd_c = {{(VLEN-OUT_W){1'b0}},
                 {{(OUT_W-ACC_W){s2_sum[ACC_W-1]}}, s2_sum}};

  always_ff @(posedge clk) begin
    if (reset) begin
      out_vd      <= '0;
      out_valid   <= 1'b0;
      out_illegal <= 1'b0;
      out_dirty   <= 1'b0;
    end else begin
      out_vd      <= vd_c;
      out_valid   <= s2_write;
      out_illegal <= s2_illegal;
      out_dirty   <= s2_write;
    end
  end

  //--------------------------------------------------------------------------
  // 仿真断言（Verilator --assert）
  //--------------------------------------------------------------------------
  // synopsys translate_off
  always_ff @(posedge clk) begin
    if (!reset && out_valid) begin
      assert (out_vd[VLEN-1:OUT_W] == '0)
        else $error("VDot: high lanes of vd are not zero");
      assert (out_illegal == 1'b0)
        else $error("VDot: illegal and valid asserted together");
    end
    if (!reset && out_dirty && !out_valid) begin
      $error("VDot: dirty asserted without a valid writeback");
    end
  end
  // synopsys translate_on

endmodule

`default_nettype wire
