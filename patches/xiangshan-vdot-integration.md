# 香山昆明湖 V2 集成说明（VDot / vdot.vv）

> **状态：已执行并验证（2026-11-03，VERIFIED）**
> 已在 `build/xs-work/XiangShan` @ `16ae9dd`（昆明湖 V2 基线，`DefaultConfig`，VLEN=128）完成 I1–I7：新增 `FuType.vdot`、
> 译码 pattern、`VdotCfg`/VFEX0 注册与 `VDotUnit`（`VecPipedFuncUnit`），重新生成 RTL 并重建 emu。
> 系统级结果：定向用例 7/7（difftest 0 mismatch）、非法配置 5/5、性能四内核全部 `PERF result=OK`。
> 可复现改动：本目录 [`xiangshan-vdot.patch`](xiangshan-vdot.patch)（5 文件 +119/−7，基于 `16ae9dd`，`git apply -p1` 即可；说明见 [`xiangshan-vdot-patch.md`](xiangshan-vdot-patch.md)，脚本 `scripts/apply_xiangshan_patch.sh`）。
>
> 实际文件与符号见 §8 核对表；实测数据与证据链见 §10。文中 §2/§3/§5 的示例代码是**原始设计意图**，
> 落地时有两处必须按 §5 的修正说明实现（`vtype` 来源、`vl==0` 写回），否则会出现 D-07/D-08 两个集成缺陷。
>
> 已冻结、可直接复用的部分是数据通路本身：[rtl/verilog/VDot.v](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v)（三模式，已验证）与 [rtl/chisel/VDot.scala](file:///home/dbqxxs/xsriscv/cieriscv/rtl/chisel/VDot.scala)（已编译并生成 `VDotCore.sv`，475 行，同向量等价回归 3047/3047，见 `docs/phase2/logs/09_chisel_equiv.log`）。

> **三模式更新（2026-11-08）**：译码新增 `vdot4x2.vv`/`vtdot.vv` 两个 `BitPat`，`FuType.vdot` 保持不变，用 `fuOpType[1:0]=0/1/2` 区分；`VDotUnit` 已重写为三模式共享数据通路，并通过 `mill -i xiangshan.compile`（573 任务 0 error）。本说明下方若出现"单一 `vdot.vv`"的表述，均按此追补理解。

---

## 0. 前置条件

| 项 | 要求 | 检查命令 |
|---|---|---|
| 宿主机 | Linux x86_64，≥32 GB 内存，≥50 GB 磁盘 | `free -g; df -h .` |
| 工具链 | 按 `xs-env` 官方说明安装（mill / firtool / verilator / riscv64-gcc / NEMU） | `mill -i --version`、`verilator --version`、`riscv64-unknown-elf-gcc --version` |
| 源码 | 昆明湖 V2 对应分支，commit 需在报告"版本锁定表"登记 | `git -C XiangShan log -1 --format='%H %s'` |
| 基线 | 集成前先跑通一次既有向量冒烟测试并留档 | 见 §7 步骤 B0 |

**版本锁定要求**：集成前把 `XiangShan`、`NEMU`、`xs-env`、`riscv-tests` 的 commit 记进 README 的版本锁定表。否则后续任何回归失败都无法区分是"我们的改动"还是"上游漂移"。

---

## 1. 定位集成点（先查再改）

在 `XiangShan/` 根目录依次执行，把结果回填到本文件 §8 的核对表：

```bash
# I1 译码：找向量整数指令的 pattern 定义处
grep -rn "vadd.vv\|VADD" src/main/scala --include=*.scala | head -30

# I2 uop 类型：找向量功能单元类型枚举
grep -rn "object VFuType\|VFuType" src/main/scala --include=*.scala | head -20

# I3 功能单元：找既有乘法单元（作为模板）
grep -rn "class VMul\|class VAlu" src/main/scala --include=*.scala | head -20

# I4 发射/忙表：找 VFu 注册与端口绑定位置
grep -rn "VFuType\.\|isVFu" src/main/scala --include=*.scala | head -40

# I5 写回：找向量写回端口与 dirty 标记
grep -rn "vecWriteback\|VecWB\|dirty" src/main/scala --include=*.scala | head -30

# I6 非法指令：找 vtype 校验与 illegal 抛出路径
grep -rn "illegalInst\|vtype\|VConfig" src/main/scala --include=*.scala | head -40
```

**原则**：每个集成点只做"新增 + 注册"，不改既有 VFu 内部逻辑。若发现某点必须改动既有逻辑（例如写回端口不能新增来源），先记录在 §9 风险表，再评估是否改用"映射到既有整型 VFu"的降级方案（见 `ipd/01` ADR-02）。

---

## 2. Step A：新增功能单元模块

1. 复制 `rtl/chisel/VDot.scala` 到香山功能单元目录（以 grep 到的 `VMul` 所在目录为准，常见为 `src/main/scala/xiangshan/backend/fu/`）。
2. 改成香山 `VFu` 基类形态：按同目录既有单元的模板补 `implicit p: Parameters`、`io.req`/`io.resp` 映射、`ModuleName` 常量。
3. **只把 `VDotCore` 当纯组合+寄存的数据通路来调用**，不改其语义：

```scala
// 伪代码：字段名以实际 VFu 基类为准，不可直接编译
class VDot(implicit p: Parameters) extends VFu()(implicitly) {
  val core = Module(new VDotCore(VLEN = 128, K = 8, ACCW = 20, OUTW = 32))

  core.io.in.valid  := io.in.valid
  core.io.in.vs1    := io.in.bits.src(0)   // 具体字段以基类为准
  core.io.in.vs2    := io.in.bits.src(1)
  core.io.in.vlZero := io.in.bits.vlZero   // 若无此信号，用 uop.vl === 0 生成
  core.io.in.vm     := io.in.bits.vm
  core.io.in.sew    := io.in.bits.sew
  core.io.in.lmul   := io.in.bits.lmul

  io.out.valid  := core.io.out.valid
  io.out.bits.data := core.io.out.vd
  io.out.bits.dirty := core.io.out.dirty
  io.out.bits.illegal := core.io.out.illegal
}
```

> 若基类的响应位宽不是 128 bit，按 `VLEN` 裁剪 `vd`，不要改 `VDotCore` 的输出布局。

---

## 3. Step B：译码与 uop 类型（I1/I2）

1. 在译码表中新增一条 `vdot.vv`：`opcode=0x57`、`funct3=000`、`funct6=111111`、`vm=1`。
2. 新增 `VFuType.VDot`（或按既有枚举风格命名），并把它加入"向量指令"集合，使其走向量发射路径。
3. **冲突检查（必做）**：新增 funct6 前，先确认该编码在所用香山版本中未被占用：

```bash
grep -rn "100000\|funct6\|Pattern(" src/main/scala/xiangshan/frontend --include=*.scala | head -40
```

若冲突，改用官方/团队约定的浮点或自定义保留空间，并同步更新 `ipd/01` §2.2 与本项目所有 RTL 常量。

---

## 4. Step C：发射、忙表与写回（I4/I5）

| 动作 | 要点 |
|---|---|
| 端口绑定 | 把 `VDot` 实例绑定到向量发射端口；`vdot` uop 的 `VFuType` 必须映射到该端口 |
| 忙表 | 复用既有机制：目标 `vd` 忙至写回完成；单元本身无内部状态，不需要额外释放条件 |
| 写回 | 复用向量写回端口，携带整寄存器 dirty（`vd[127:0]` 全部有效） |
| 依赖 | 不内部旁路；RAW 由既有记分牌保证 |

**注意**：`out_dirty` 必须映射到香山的"整寄存器写"语义（而非按元素掩码写），因为本指令写满 128 bit 且尾通道固定为 0。

---

## 5. Step D：配置校验（I6）

`SEW != 8`、`LMUL != 1`、`vm == 0`、`vill`、`vstart != 0` 必须在**功能单元输出级**上报 illegal-instruction
（香山昆明湖 V2 的向量 FU 允许在写回端口携带 `exceptionVec(illegalInstr)`，提交时抛异常）。

### 5.1 vtype 必须取自控制通路，不能取自 `VlData`

`FuConfig` 里 `vconfigWakeUp = true` 时，`VecPipedFuncUnit.outVConfig` 来自数据源
`DataConfig.VlData`。但 **`VlData` 宽度只有 8 bit（只承载 `vl`）**：

```scala
// DataConfig.scala
object VlData extends DataConfig("Vl", 0, Some(Log2Up(VecData().dataWidth) + 1)) // = 8
```

因此 `outData.getSrcVConfig.asTypeOf(new VConfig)` 的 `vtype` 字段恒为 0，firtool 会把它整个优化掉——
生成的 `VDotUnit.sv` 里根本没有 `vsew/vlmul/vill` 端口，`illegalOut` 退化成 `~vm | (|vstart)`（缺陷 D-08）。

正确来源是控制通路（与 `VIAluFix` 一致）：

```scala
private val cfgIllegal = outVecCtrl.vill ||
  outVecCtrl.vsew =/= VSew.e8 ||
  outVlmul        =/= VLmul.m1 ||
  !outVm
```

### 5.2 `vl == 0` 不能屏蔽写回，必须回写 `oldVd`

`vl == 0` 是合法指令，但"不产生写回"在香山行不通：提交阶段会把架构 `vd` 的映射改到重命名后的
物理寄存器，而该寄存器从未被写 → 架构值变成随机数（缺陷 D-07，emu 上表现为 `v3` 为随机值）。

正确写法与 `VIAluFix` 相同——写回端口保持有效，只把数据换成旧值：

```scala
private val outVstartGeVl = outVstart >= outVl
io.out.bits.res.data := Mux(outVstartGeVl, outOldVd, vdOut)
io.out.bits.ctrl.exceptionVec.get(illegalInstr) := cfgIllegal || (outVstart =/= 0.U)
io.out.bits.ctrl.vecWen.foreach(_ := outCtrl.vecWen.get)   // 不再用 vl/illegal 抑制
```

非法配置时仍然写回，但提交阶段抛异常、不更新架构状态，因此无副作用。

---

## 6. Step E：构建与仿真

本轮实际使用（在 `build/xs-work/XiangShan` 下）：

```bash
export NOOP_HOME=$(pwd) JAVA_HOME=$PWD/../../../.tools/jdk
export PATH=$PWD/../../../.tools/verilator/bin:$PWD/../../../.tools/bin:$PATH

# RTL（约 7 min 增量 / 27 min 全量，取决于主机负载）
mill -i -Djvm-xmx=12G -Djvm-xss=256m xiangshan.test.runMain top.SimTop \
  --target-dir build/rtl --config DefaultConfig --issue E.b --num-cores 1 \
  --dump-fir --target systemverilog --split-verilog --enable-difftest --full-stacktrace \
  --firtool-opt "--repl-seq-mem --repl-seq-mem-file=SimTop.sv.conf" \
  --firtool-opt "-O=release --disable-annotation-unknown --lowering-options=explicitBitcast,disallowLocalVariables,disallowPortDeclSharing,locationInfoStyle=none"

# emu（verilator 生成 + C++ 编译，-j48 约 35 min）
rm -rf build/emu-compile
make -C ./difftest emu -j48 SIM_TOP=SimTop DESIGN_DIR=$(pwd) NUM_CORES=1 RTL_SUFFIX=sv
```

**两个易踩的坑**：① 不设 `NOOP_HOME` 时 difftest 的 `FileControl.write` 会在收尾阶段失败；
② `verilator` 必须在 `PATH` 中，否则 Makefile 回落到 `VERILATOR_LEGACY` 并报找不到命令。

```bash
# 编译（以 xs-env 官方命令为准，等价写法）
make -C XiangShan sim-verilog   # 或 mill 等效命令

# 单条 vdot 的最小验证（示例，需按实际 emu 用法调整）
cat > vdot_smoke.S <<'EOF'
# 期望：t0 = 120，vd0 = 0x00000078
li   t0, 0
vsetvli t0, x0, e8, m1, ta, ma
la   t1, vec_a
vle8.v v1, (t1)
la   t1, vec_b
vle8.v v2, (t1)
vdot.vv v3, v1, v2
vmv.x.s t2, v3
EOF
```

判定：波形中 `out_valid` 与 `out_vd[31:0]=0x78` 在预期周期出现，且 `out_vd[127:32]` 恒为 0。

**波形取证要求**（对应阶段二录屏取证）：至少保留 1 条正数、1 条负数、1 条边界用例的波形，标出 EX1/EX2/WB 三个周期与 `vd` 写回时刻。

---

## 7. 回归与验收

| 步骤 | 内容 | 通过判据 |
|---|---|---|
| B0 | 集成前，跑既有向量指令回归（vadd/vmul 等）并留档 | 全 PASS，作为基线 |
| B1 | 集成译码与 uop 类型后重跑 B0 | 与 B0 完全一致（零回归） |
| B2 | 集成 VFu 与写回后重跑 B0 | 零回归 |
| B3 | 跑 `vdot_smoke.S` | 单条结果正确 |
| B4 | 把 `tests/vectors/vdot_vectors.txt` 的 3047 条三模式用例映射为汇编程序批量跑 | 3047/3047 与 Python 期望一致 |
| B5 | 与 NEMU difftest（阶段三） | 无 difftest 报错 |

**B1/B2 的"零回归"是硬门禁**：任何一条既有用例失败，先回滚本次改动再定位，不允许带着回归继续往下做。

---

## 8. 集成点核对表（2026-11-03 已回填）

路径均相对 `build/xs-work/XiangShan/src/main/scala/xiangshan/`。

| # | 集成环节 | 实际文件 | 实际符号 | 状态 |
|---|---|---|---|---|
| I1 | 译码 | `backend/decode/VecDecoder.scala` | `VDOT_VV = BitPat("b1111111??????????000?????1010111")` → `OPIVV(FuType.vdot, ...)` | 已核实 |
| I2 | uop 类型 | `backend/fu/FuType.scala` | `FuType.vdot`，`needVecCtrl`/`isVecArith` 均包含 | 已核实 |
| I3 | 功能单元 | `backend/fu/wrapper/VDotUnit.scala` | `class VDotUnit(cfg) extends VecPipedFuncUnit(cfg)`（K=8，ACC_W=20，OUT_W=32） | 已核实 |
| I4 | 发射/忙表 | `backend/fu/FuConfig.scala` | `VdotCfg`：`srcData = Seq(Seq(VecData(), VecData(), VecData(), V0Data(), VlData()))`、`piped=true`、`latency=CertainLatency(3)`、`vconfigWakeUp=true`、`maskWakeUp=true`、`writeVecRf=true`、`destDataBits=128`、`exceptionOut=Seq(illegalInstr)`；`allConfigs` 与 `VecArithFuConfigs` 已加入 | 已核实 |
| I5 | 写回 | `backend/fu/FuncUnit.scala` + `VDotUnit` | `io.out.bits.ctrl.vecWen`（恒随 `outCtrl.vecWen`）、`res.data = Mux(vstart>=vl, oldVd, vdOut)` | 已核实 |
| I6 | 配置校验 | `backend/fu/wrapper/VDotUnit.scala` | `cfgIllegal = vill \|\| vsew =/= VSew.e8 \|\| vlmul =/= VLmul.m1 \|\| !vm`；`exceptionVec(illegalInstr) := cfgIllegal \|\| (vstart =/= 0)` | 已核实（修正 D-08） |
| I7 | 参数开关 | `Parameters.scala` | VFEX0 的 `exuConfigs` 加入 `VdotCfg` | 已核实 |

**生成 RTL 反查**（`build/rtl/VDotUnit.sv`，用于确认没有信号被优化掉）：

```systemverilog
assign io_out_bits_ctrl_vecWen = io_in_bits_ctrlPipe_3_vecWen;
assign io_out_bits_ctrl_exceptionVec_2 =
    io_in_bits_ctrlPipe_3_vpu_vill | (|io_in_bits_ctrlPipe_3_vpu_vsew)
  | (|io_in_bits_ctrlPipe_3_vpu_vlmul) | ~io_in_bits_ctrlPipe_3_vpu_vm
  | (|io_in_bits_ctrlPipe_3_vpu_vstart);
assign io_out_bits_res_data =
  io_in_bits_ctrlPipe_3_vpu_vstart >= io_in_bits_dataPipe_3_src_4
    ? io_in_bits_dataPipe_3_src_2          // oldVd，vl==0 时保持原值
    : {96'h0, {12{_sumAll_T[19]}}, _sumAll_T};
```

若生成的端口里没有 `vpu_vsew/vpu_vlmul/vpu_vill`，即说明又走回了 `VlData`（见 §5.1）。

---

## 9. 风险与回滚

| # | 风险 | 触发信号 | 应对 |
|---|---|---|---|
| R1 | funct6 与既有指令冲突 | 译码后既有指令行为异常 | 换编码常量，数据通路不变 |
| R2 | VFu 响应位宽与 128 bit 不匹配 | 高位被截断/拼接错位 | 按实际位宽裁剪，保持 `vd[OUTW-1:0]` 语义 |
| R3 | 写回端口不允许新增来源 | 编译期端口数不匹配 | 改为映射到既有整型 VFu 的降级方案 |
| R4 | `vlZero` 信号在 uop 中不可得 | 无法编译 | 用 `uop.vl === 0.U` 现场生成 |
| R5 | 上游漂移导致回归难判定 | B0 与 B1 结果不一致 | 严格执行版本锁定表 |

**回滚方式**：所有改动均为新增文件 + 少量注册行，回滚只需移除新增文件并撤销注册行（建议每个集成环节单独一次提交，便于二分定位）。

---

## 10. 执行结果与证据（2026-11-03）

环境：香山 @ `16ae9dd`（DefaultConfig=KunminghuV2），Chisel 6.6.0 / mill 0.12.3 / firtool 1.62.1，
Verilator 5.034，NEMU 扩展作 difftest 参考模型，`--ram-size` 默认。

| 用例 | 运行方式 | 结果 | 日志 |
|---|---|---|---|
| `vdot_directed`（7 用例，含 `vl=0`） | emu + difftest | `DIRECTED fails=00000000`，`HIT GOOD TRAP`，992 inst / 13,565 cyc，0 mismatch | `docs/phase2/logs/xs_emu_vdot_directed.log` |
| `vdot_illegal`（5 类非法配置） | emu `--no-diff`（架构自检） | `ILLEGAL traps=00000005 other=00000000`，`HIT GOOD TRAP`，10,429 cyc | `docs/phase2/logs/xs_emu_vdot_illegal.log` |
| 普通非法指令（对照） | emu + difftest | 在陷阱指令处报 CSR 不一致（`mepc/mcause`），DUT 侧结果正确 | `docs/phase2/logs/xs_emu_baseline_illegal_difftest.log` |
| `perf_empty/vdot/rvv/scalar` | emu + difftest | 四个内核均 `PERF result=OK`、`HIT GOOD TRAP` | `docs/phase2/logs/xs_emu_perf_*.log` |

实测加速比（NITER=2000，per-iter 扣空循环）：vdot 0.51 cyc / 标量 4.96 cyc / RVV 基线 6.00 cyc，
即 **对标量 9.8×（lane 公平）、对 RVV 基线 11.8×（16-lane，上界）**，详见 `docs/phase3/perf_analysis.md` §6。

**difftest 已知边界**：本 emu 构建中，陷阱指令提交时 DUT 已更新 `mepc/mcause/mstatus`，而参考模型在同一
比较点仍是旧值（用 `.word 0` 的普通非法指令即可复现，见上表第 3 行），因此非法配置用例改用程序内自检。
这不是本模块的问题，也不影响合法路径的 0 mismatch 结论。
