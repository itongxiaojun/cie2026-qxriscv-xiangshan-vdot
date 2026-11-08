//=============================================================================
// VDot —— vdot.vv / vdot4x2.vv / vtdot.vv 功能单元（Chisel 主体实现）
//
// 与 rtl/verilog/VDot.v 为同一数据通路语义的两种实现：
//
//   mode=0  vdot.vv（INT8）
//     S = sum_{i=0..7} sext8(vs1[i]) * sext8(vs2[i])
//     vd[OUTW-1:0] = S, vd[VLEN-1:OUTW] = 0
//
//   mode=1  vdot4x2.vv（INT4 打包，双结果）
//     nibble n = bits[4n+3:4n]
//     r0 = sum_{n=0..7}  sext4(vs1[n]) * sext4(vs2[n])
//     r1 = sum_{n=8..15} sext4(vs1[n]) * sext4(vs2[n])
//     vd[31:0] = r0, vd[63:32] = r1, vd[127:64] = 0
//
//   mode=2  vtdot.vv（BitNet 1.58 三值权重，双结果）
//     a_i = sext8(vs1[8*i +: 8])，code_i = vs2[2*i +: 2]
//     code 00/11 -> 0，01 -> +a_i，10 -> -a_i
//     r0 = sum_{i=0..7} tern(a_i, code_i)，r1 = sum_{i=8..15} ...
//     vd[31:0] = r0, vd[63:32] = r1, vd[127:64] = 0
//
// 3 级流水：EX1 乘法/三值选择 / EX2 归约树 / WB 格式化写回；无状态，可背靠背发射
//
// 关键共享：INT4 与三值模式共用两棵 12-bit 8 输入归约树，仅 EX1 输入不同；
//           三值模式没有任何乘法器，只做取反/清零选择。
//
// 说明：本文件面向香山（Chisel）集成。已用 Chisel 6.6.0 + firtool 1.62.1 编译并生成
//       rtl/chisel/VDotCore.sv，经 VDotWrap.v 复用同一测试台完成三模式等价回归。
//=============================================================================
package vdot

import chisel3._
import chisel3.util._

/** 三种点积模式的 2-bit 编码 */
object VDotMode {
  val INT8    = 0.U(2.W)
  val INT4X2  = 1.U(2.W)
  val TERNARY = 2.U(2.W)
}

/** VDot 请求/写回接口（单元级，不含香山 VFu 框架字段） */
class VDotIO(val VLEN: Int = 128, val OUTW: Int = 32) extends Bundle {
  val in = Input(new Bundle {
    val valid  = Bool()
    val vs1    = UInt(VLEN.W)
    val vs2    = UInt(VLEN.W)
    val vlZero = Bool()          // vl == 0：不写回
    val vm     = Bool()          // vm == 1 才合法
    val sew    = UInt(3.W)       // vtype.vsew，0 = e8
    val lmul   = UInt(3.W)       // 0 = m1
    val mode   = UInt(2.W)       // 0=INT8，1=INT4X2，2=TERNARY，3=保留
  })
  val out = Output(new Bundle {
    val vd      = UInt(VLEN.W)
    val valid   = Bool()
    val illegal = Bool()
    val dirty   = Bool()
  })
}

class VDotCore(
  val VLEN: Int = 128,
  val K:    Int = 8,
  val ACCW: Int = 20,
  val OUTW: Int = 32,
  val DUALW: Int = 12,
  val TERNW: Int = 9
) extends Module {
  require(VLEN == 128, "赛题固定 VLEN=128")
  require(K == 8, "vdot.vv 语义固定 K=8")
  require(ACCW >= 19, "8 项和上界 +131072，需 >= 19 bit 有符号")
  require(OUTW >= ACCW, "OUT_W 必须能容纳累加结果")
  require(DUALW >= 12, "INT4/三值 8 项和上界 +1024，需 >= 12 bit 有符号")
  require(TERNW >= 9, "三值选择值在 a=-128 取反后为 +128，需 9 bit 有符号")
  require(VLEN >= 2 * OUTW, "双结果写回需要 VLEN >= 2*OUT_W")

  val io = IO(new VDotIO(VLEN, OUTW))

  /** 取第 i 个 int8 lane 并解释为有符号数 */
  private def laneSInt(x: UInt, i: Int): SInt = x(8 * i + 7, 8 * i).asSInt

  /** 取第 i 个 4-bit nibble 并解释为有符号数 */
  private def nibSInt(x: UInt, i: Int): SInt = x(4 * i + 3, 4 * i).asSInt

  /** 符号扩展到指定位宽 */
  private def ext(x: SInt, w: Int): SInt = {
    val pad = w - x.getWidth
    require(pad >= 0, s"ext: $w < ${x.getWidth}")
    Cat(Fill(pad, x(x.getWidth - 1)), x).asSInt
  }

  /** 树形归约（log2(K) 级），每级显式截断到 w，保证结果位宽可静态推断 */
  private def treeSum(ps: Seq[SInt], w: Int): SInt = {
    var cur: Seq[SInt] = ps.map(p => ext(p, w))
    while (cur.length > 1) {
      cur = cur.grouped(2).map {
        case Seq(a, b) => (a +& b)(w - 1, 0).asSInt
        case Seq(a)    => a
      }.toSeq
    }
    cur.head
  }

  //--------------------------------------------------------------------------
  // EX1-A：INT8，K 路有符号 8x8 乘法
  //--------------------------------------------------------------------------
  val prod8 = VecInit(Seq.tabulate(K)(i => laneSInt(io.in.vs1, i) * laneSInt(io.in.vs2, i)))

  //--------------------------------------------------------------------------
  // EX1-B：INT4，16 路有符号 4x4 乘法
  //--------------------------------------------------------------------------
  val prod4 = VecInit(Seq.tabulate(16)(i => nibSInt(io.in.vs1, i) * nibSInt(io.in.vs2, i)))

  //--------------------------------------------------------------------------
  // EX1-C：BitNet 1.58 三值，16 路符号选择/清零
  //--------------------------------------------------------------------------
  val act8  = VecInit(Seq.tabulate(16)(i => laneSInt(io.in.vs1, i)))
  val tcode = VecInit(Seq.tabulate(16)(i => io.in.vs2(2 * i + 1, 2 * i)))
  val act9  = VecInit(act8.map(a => Cat(a(7), a).asSInt))
  val neg9  = VecInit(act9.map(a => (0.S(9.W) - a)(8, 0).asSInt))
  val tern9 = VecInit(Seq.tabulate(16) { i =>
    Mux(tcode(i) === 1.U, act9(i),
      Mux(tcode(i) === 2.U, neg9(i), 0.S(9.W)))
  })

  /** 双结果归约树的公共输入：INT4 乘积或三值选择值（均为 9-bit 有符号） */
  val dual9 = VecInit(Seq.tabulate(16) { i =>
    Mux(io.in.mode === VDotMode.INT4X2,  ext(prod4(i), 9),
      Mux(io.in.mode === VDotMode.TERNARY, tern9(i), 0.S(9.W)))
  })

  val legal = io.in.vm && io.in.sew === 0.U && io.in.lmul === 0.U &&
              io.in.mode =/= 3.U

  //--------------------------------------------------------------------------
  // 流水寄存器
  //--------------------------------------------------------------------------
  val s1Mode    = RegNext(io.in.mode, VDotMode.INT8)
  val s1Illegal = RegNext(io.in.valid && !legal, false.B)
  val s1Write   = RegNext(io.in.valid && legal && !io.in.vlZero, false.B)
  val s1Prod8   = RegNext(prod8)
  val s1Dual9   = RegNext(dual9)

  // EX2：INT8 归约树 + 两棵共享双结果归约树
  val sum8 = treeSum(s1Prod8.toSeq, ACCW)
  val r0   = treeSum(s1Dual9.slice(0, 8).toSeq, DUALW)
  val r1   = treeSum(s1Dual9.slice(8, 16).toSeq, DUALW)

  val s2Mode    = RegNext(s1Mode, VDotMode.INT8)
  val s2Illegal = RegNext(s1Illegal, false.B)
  val s2Write   = RegNext(s1Write, false.B)
  // 累加结果为宽度推断节点；显式 RegInit 固定寄存器位宽，避免 RegNext 继承未知位宽
  val s2Sum = RegInit(0.S(ACCW.W));  s2Sum := sum8
  val s2R0  = RegInit(0.S(DUALW.W)); s2R0  := r0
  val s2R1  = RegInit(0.S(DUALW.W)); s2R1  := r1

  // WB：符号扩展 + 高位清零
  val out8    = Cat(0.U((VLEN - OUTW).W),   ext(s2Sum, OUTW).asUInt)
  val outDual = Cat(0.U((VLEN - 2 * OUTW).W), ext(s2R1, OUTW).asUInt, ext(s2R0, OUTW).asUInt)
  val vdPayload = Mux(s2Mode === VDotMode.INT8, out8, outDual)

  io.out.vd      := RegNext(vdPayload)
  io.out.valid   := RegNext(s2Write, false.B)
  io.out.illegal := RegNext(s2Illegal, false.B)
  io.out.dirty   := RegNext(s2Write, false.B)
  val outMode    = RegNext(s2Mode)

  //--------------------------------------------------------------------------
  // 仿真断言
  //--------------------------------------------------------------------------
  when(io.out.valid) {
    // 断言消息必须是 ASCII：firtool 1.62.1 不支持 SystemVerilog 字符串中的 Unicode 转义
    when(outMode === VDotMode.INT8) {
      assert(io.out.vd(VLEN - 1, OUTW) === 0.U, "VDot: high lanes of vd must be zero (INT8)")
    }.otherwise {
      assert(io.out.vd(VLEN - 1, 2 * OUTW) === 0.U, "VDot: high lanes of vd must be zero (dual)")
    }
    assert(!io.out.illegal, "VDot: valid and illegal must not be together")
  }
}
