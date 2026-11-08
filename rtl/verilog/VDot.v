//=============================================================================
// VDot —— 香山昆明湖 V2 自定义向量点积功能单元（模块级 RTL）
//
// 三模式统一数据通路（共享三级流水、控制与双结果写回格式）：
//
//   mode=0  vdot.vv      （INT8，原基线）
//     S = sum_{i=0..7} sext8(vs1[i]) * sext8(vs2[i])
//     vd[OUT_W-1:0]   = S
//     vd[VLEN-1:OUT_W] = 0
//
//   mode=1  vdot4x2.vv   （INT4 打包，双结果双累加流）
//     每字节拆成 2 个 4-bit 有符号二补码 nibble，nibble n = bits[4n+3:4n]
//     r0 = sum_{n=0..7}  sext4(vs1[n]) * sext4(vs2[n])
//     r1 = sum_{n=8..15} sext4(vs1[n]) * sext4(vs2[n])
//     vd[31:0]   = r0
//     vd[63:32]  = r1
//     vd[127:64] = 0
//
//   mode=2  vtdot.vv     （BitNet 1.58 三值权重，双结果双累加流）
//     vs1 的 16 个 int8 激活：a_i = sext8(vs1[8*i +: 8])
//     vs2 低 32 bit 中每 2 bit 一个三值码：code_i = vs2[2*i +: 2]
//       code=00/11 -> 0, code=01 -> +a_i, code=10 -> -a_i
//     r0 = sum_{i=0..7}  tern(a_i, code_i)
//     r1 = sum_{i=8..15} tern(a_i, code_i)
//     vd[31:0]   = r0
//     vd[63:32]  = r1
//     vd[127:64] = 0
//
// 微架构：
//   - 三级流水（EX1 乘法/三值选择 → EX2 归约树 → WB 格式化写回），无状态，全流水
//   - mode=1/2 共用两棵 8 输入有符号归约树（DUAL_W=12），只是 EX1 的输入不同：
//       INT4  → 16 个 4x4 乘法器
//       vtdot → 16 个“取反/清零”选择器（无乘法器）
//   - mode=0 保留原有 8 个 8x8 乘法器与 20-bit 归约树，行为逐位不变
//
// 位宽论证：
//   INT4  ：nibble ∈ [-8,7]，乘积 ∈ [-56,64]，8 项和 ∈ [-448,512]，12 bit 足够
//   vtdot ：a ∈ [-128,127]，+128 需 9 bit；8 项和 ∈ [-1024,1024]，12 bit 足够
//   双结果均以 32 bit 二补码写回，高位通道清零
//
// 说明：本文件是可在独立仿真环境中验证的等价 Verilog 实现；
//       接入香山时由 Chisel 包装（见 rtl/chisel/VDot.scala）复用同一数据通路语义。
//=============================================================================
`timescale 1ns/1ps
`default_nettype none

module VDot #(
    parameter integer VLEN   = 128,   // 向量寄存器位宽
    parameter integer K      = 8,     // INT8 点积分组长度
    parameter integer ACC_W  = 20,    // INT8 内部累加位宽（>= 19）
    parameter integer OUT_W  = 32,    // 输出元素位宽
    parameter integer DUAL_W = 12,    // INT4 / 三值双结果归约树位宽
    parameter integer TERN_W = 9      // 三值选择值位宽（-128 取反需 9 bit）
) (
    input  logic              clk,
    input  logic              reset,        // 同步复位，高有效

    // 请求侧（由向量发射框架驱动）
    input  logic              in_valid,
    input  logic [VLEN-1:0]   in_vs1,
    // in_vs2[127:64] 在三模式下均不使用：INT8/INT4/三值都只消费低 64 bit
    // （INT4=8 字节 nibble，三值=32 个 2-bit 码）。这是题面固定布局，非遗漏。
    /* verilator lint_off UNUSEDSIGNAL */
    input  logic [VLEN-1:0]   in_vs2,
    /* verilator lint_on UNUSEDSIGNAL */
    input  logic              in_vl_zero,   // vl == 0：不写回
    input  logic              in_vm,        // vm == 1 才合法
    // vtype.vsew 为 3 bit：0=e8（唯一合法），1=e16，2=e32，3=e64，4..7 保留。
    // 接口必须保留全部 3 bit，否则保留编码（如 vsew=4）被截断成 0 而误判合法。
    input  logic [2:0]        in_sew,
    input  logic [2:0]        in_lmul,      // 0: m1（唯一合法）
    // 0=INT8 点积，1=INT4 打包双结果，2=BitNet 三值双结果，3=保留（非法）
    input  logic [1:0]        in_mode,

    // 写回侧
    output logic [VLEN-1:0]   out_vd,
    output logic              out_valid,    // 写回有效
    output logic              out_illegal,  // 非法指令（不写回）
    output logic              out_dirty     // vd 整寄存器脏
);

  localparam logic [1:0] MODE_INT8    = 2'd0;
  localparam logic [1:0] MODE_INT4X2  = 2'd1;
  localparam logic [1:0] MODE_TERNARY = 2'd2;

  // 语义固定 K=8；参数越界在例化（仿真启动）时报错
  initial begin
    if (K != 8)          $fatal(1, "VDot: K 必须为 8");
    if (ACC_W < 19)      $fatal(1, "VDot: ACC_W 必须 >= 19");
    if (OUT_W < ACC_W)   $fatal(1, "VDot: OUT_W 必须 >= ACC_W");
    if (DUAL_W < 12)     $fatal(1, "VDot: DUAL_W 必须 >= 12");
    if (TERN_W < 9)       $fatal(1, "VDot: TERN_W 必须 >= 9");
  end

  //--------------------------------------------------------------------------
  // 合法性判定：仅支持 vm=1 / SEW=8 / LMUL=1，且模式编码不为保留值
  //--------------------------------------------------------------------------
  logic legal;
  assign legal = in_vm && (in_sew == 3'd0) && (in_lmul == 3'd0) &&
                 (in_mode != 2'd3);

  //--------------------------------------------------------------------------
  // EX1-A：INT8 路径，K 路有符号 8x8 乘法（行为与基线逐位一致）
  //--------------------------------------------------------------------------
  logic signed [7:0]  a8   [K];
  logic signed [7:0]  b8   [K];
  logic signed [15:0] prod8 [K];

  genvar gi;
  generate
    for (gi = 0; gi < K; gi++) begin : g_mul8
      assign a8[gi]    = in_vs1[8*gi +: 8];
      assign b8[gi]    = in_vs2[8*gi +: 8];
      assign prod8[gi] = a8[gi] * b8[gi];
    end
  endgenerate

  //--------------------------------------------------------------------------
  // EX1-B：INT4 打包路径，16 路 4x4 有符号乘法
  //   nibble n = bits[4n+3:4n]；n=0..7 属于低 32 bit（结果 r0），
  //   n=8..15 属于高 32 bit（结果 r1）
  //--------------------------------------------------------------------------
  logic signed [3:0]  a4   [16];
  logic signed [3:0]  b4   [16];
  logic signed [7:0]  prod4 [16];

  generate
    for (gi = 0; gi < 16; gi++) begin : g_mul4
      assign a4[gi]    = in_vs1[4*gi +: 4];
      assign b4[gi]    = in_vs2[4*gi +: 4];
      assign prod4[gi] = a4[gi] * b4[gi];
    end
  endgenerate

  //--------------------------------------------------------------------------
  // EX1-C：BitNet 1.58 三值路径，16 路“符号选择/清零”，无乘法器
  //   a_i = sext8(vs1[8*i +: 8])，code_i = vs2[2*i +: 2]
  //   选择值用 9 bit 保存：a_i=-128 且 code=-1 时得到 +128
  //--------------------------------------------------------------------------
  logic signed [7:0]  act8  [16];
  logic        [1:0]  tcode [16];
  logic signed [8:0]  act9  [16];
  logic signed [8:0]  tern9 [16];

  generate
    for (gi = 0; gi < 16; gi++) begin : g_tern
      assign act8[gi]  = in_vs1[8*gi +: 8];
      assign tcode[gi] = in_vs2[2*gi +: 2];
      assign act9[gi]  = {act8[gi][7], act8[gi]};
      assign tern9[gi] = (tcode[gi] == 2'b01) ? act9[gi] :
                         (tcode[gi] == 2'b10) ? -act9[gi] : 9'sd0;
    end
  endgenerate

  //--------------------------------------------------------------------------
  // 双结果归约树的公共输入（9 bit 有符号）：
  //   INT4 模式装载 4x4 乘积；三值模式装载 ±a/0。INT8 模式下该路径不写回。
  //--------------------------------------------------------------------------
  logic signed [8:0] dual9 [16];

  generate
    for (gi = 0; gi < 16; gi++) begin : g_dual
      assign dual9[gi] = (in_mode == MODE_INT4X2)  ? {prod4[gi][7], prod4[gi]} :
                         (in_mode == MODE_TERNARY) ? tern9[gi] : 9'sd0;
    end
  endgenerate

  //--------------------------------------------------------------------------
  // 流水寄存器：EX1 -> EX2（保存乘积/选择值与控制）
  //
  // valid 不单独寄存：写回由 s1_write 编码，"有效但不写回"仅出现在 vl==0，
  // 因此 (write, illegal) 已足以表达全部状态，省去无读者的 valid 触发器。
  //--------------------------------------------------------------------------
  logic [1:0]         s1_mode;
  logic               s1_illegal, s1_write;
  logic signed [15:0] s1_prod8 [K];
  logic signed [8:0]  s1_dual9 [16];

  always_ff @(posedge clk) begin
    if (reset) begin
      s1_mode    <= MODE_INT8;
      s1_illegal <= 1'b0;
      s1_write   <= 1'b0;
      for (int j = 0; j < K; j++)  s1_prod8[j] <= '0;
      for (int j = 0; j < 16; j++) s1_dual9[j] <= '0;
    end else begin
      s1_mode    <= in_mode;
      s1_illegal <= in_valid && !legal;
      s1_write   <= in_valid && legal && !in_vl_zero;
      for (int j = 0; j < K; j++)  s1_prod8[j] <= prod8[j];
      for (int j = 0; j < 16; j++) s1_dual9[j] <= dual9[j];
    end
  end

  //--------------------------------------------------------------------------
  // EX2-A：INT8 归约树（8 -> 4 -> 2 -> 1，ACC_W 位）
  //--------------------------------------------------------------------------
  logic signed [ACC_W-1:0] u0 [0:K-1];

  generate
    for (gi = 0; gi < K; gi++) begin : g_tree8_init
      assign u0[gi] = {{(ACC_W-16){s1_prod8[gi][15]}}, s1_prod8[gi]};
    end
  endgenerate

  logic signed [ACC_W-1:0] u1_0, u1_1, u1_2, u1_3;
  logic signed [ACC_W-1:0] u2_0, u2_1;
  logic signed [ACC_W-1:0] sum8;

  assign u1_0 = u0[0] + u0[1];
  assign u1_1 = u0[2] + u0[3];
  assign u1_2 = u0[4] + u0[5];
  assign u1_3 = u0[6] + u0[7];
  assign u2_0 = u1_0 + u1_1;
  assign u2_1 = u1_2 + u1_3;
  assign sum8 = u2_0 + u2_1;

  //--------------------------------------------------------------------------
  // EX2-B：INT4 / 三值共用的两棵 8 输入归约树（DUAL_W 位）
  //   低位组：n=0..7（INT4）或 i=0..7（三值） -> r0
  //   高位组：n=8..15 / i=8..15                -> r1
  //--------------------------------------------------------------------------
  logic signed [DUAL_W-1:0] d0 [0:7];
  logic signed [DUAL_W-1:0] d1 [0:7];

  generate
    for (gi = 0; gi < 8; gi++) begin : g_dual_init
      assign d0[gi] = {{(DUAL_W-TERN_W){s1_dual9[gi][TERN_W-1]}},    s1_dual9[gi]};
      assign d1[gi] = {{(DUAL_W-TERN_W){s1_dual9[gi+8][TERN_W-1]}},  s1_dual9[gi+8]};
    end
  endgenerate

  logic signed [DUAL_W-1:0] v1_0, v1_1, v1_2, v1_3;
  logic signed [DUAL_W-1:0] v2_0, v2_1;
  logic signed [DUAL_W-1:0] r0_sum;
  logic signed [DUAL_W-1:0] w1_0, w1_1, w1_2, w1_3;
  logic signed [DUAL_W-1:0] w2_0, w2_1;
  logic signed [DUAL_W-1:0] r1_sum;

  assign v1_0 = d0[0] + d0[1];
  assign v1_1 = d0[2] + d0[3];
  assign v1_2 = d0[4] + d0[5];
  assign v1_3 = d0[6] + d0[7];
  assign v2_0 = v1_0 + v1_1;
  assign v2_1 = v1_2 + v1_3;
  assign r0_sum = v2_0 + v2_1;

  assign w1_0 = d1[0] + d1[1];
  assign w1_1 = d1[2] + d1[3];
  assign w1_2 = d1[4] + d1[5];
  assign w1_3 = d1[6] + d1[7];
  assign w2_0 = w1_0 + w1_1;
  assign w2_1 = w1_2 + w1_3;
  assign r1_sum = w2_0 + w2_1;

  //--------------------------------------------------------------------------
  // 流水寄存器：EX2 -> WB
  //--------------------------------------------------------------------------
  logic [1:0]              s2_mode;
  logic                    s2_illegal, s2_write;
  logic signed [ACC_W-1:0] s2_sum8;
  logic signed [DUAL_W-1:0] s2_r0, s2_r1;

  always_ff @(posedge clk) begin
    if (reset) begin
      s2_mode    <= MODE_INT8;
      s2_illegal <= 1'b0;
      s2_write   <= 1'b0;
      s2_sum8    <= '0;
      s2_r0      <= '0;
      s2_r1      <= '0;
    end else begin
      s2_mode    <= s1_mode;
      s2_illegal <= s1_illegal;
      s2_write   <= s1_write;
      s2_sum8    <= sum8;
      s2_r0      <= r0_sum;
      s2_r1      <= r1_sum;
    end
  end

  //--------------------------------------------------------------------------
  // WB：按模式格式化
  //   INT8    : vd[31:0] = S
  //   双结果  : vd[31:0] = r0，vd[63:32] = r1
  //--------------------------------------------------------------------------
  logic signed [OUT_W-1:0] out8, out0, out1;
  logic [VLEN-1:0] vd_c;
  logic [1:0]      out_mode;      // 与 out_vd 对齐的模式（仅用于断言/调试）

  assign out8 = {{(OUT_W-ACC_W){s2_sum8[ACC_W-1]}}, s2_sum8};
  assign out0 = {{(OUT_W-DUAL_W){s2_r0[DUAL_W-1]}}, s2_r0};
  assign out1 = {{(OUT_W-DUAL_W){s2_r1[DUAL_W-1]}}, s2_r1};

  always_comb begin
    case (s2_mode)
      MODE_INT8:    vd_c = {{(VLEN-OUT_W){1'b0}}, out8};
      MODE_INT4X2,
      MODE_TERNARY: vd_c = {{(VLEN-2*OUT_W){1'b0}}, out1, out0};
      default:      vd_c = '0;
    endcase
  end

  always_ff @(posedge clk) begin
    if (reset) begin
      out_vd      <= '0;
      out_mode    <= MODE_INT8;
      out_valid   <= 1'b0;
      out_illegal <= 1'b0;
      out_dirty   <= 1'b0;
    end else begin
      out_vd      <= vd_c;
      out_mode    <= s2_mode;
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
      // INT8 只有 vd[31:0] 有效；双结果模式 vd[63:0] 均有效，但 [127:64] 必须为 0
      if (out_mode == MODE_INT8) begin
        assert (out_vd[VLEN-1:OUT_W] == '0)
          else $error("VDot: high lanes of vd are not zero (INT8)");
      end else begin
        assert (out_vd[VLEN-1:2*OUT_W] == '0)
          else $error("VDot: high lanes of vd are not zero (dual)");
      end
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
