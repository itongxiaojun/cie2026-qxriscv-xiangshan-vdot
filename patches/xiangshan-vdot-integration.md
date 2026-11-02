# 香山昆明湖 V2 集成说明（VDot / vdot.vv）

> **状态：未执行（UNVERIFIED）**
> 本文是集成**操作规程**，不是"已完成集成"的记录。当前工作区已检出香山源码（`build/xs-work/XiangShan` @ `16ae9dd`）、具备 RISC-V 工具链与 emu（阶段一已闭环），但**集成本身尚未执行**，因此：
> - 文中所有文件路径、类名、方法名均为**按香山通用结构的推断**，必须用文中给出的 grep 命令逐一核实后回填；
> - 任何一条都不得在未核实的情况下直接粘贴进源码；
> - 集成完成后必须重跑既有向量回归，确认零回归，并把结果补进 [阶段二测试报告](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase2/test_report.md)（替换 U-01）。
>
> 已冻结、可直接复用的部分是数据通路本身：[rtl/verilog/VDot.v](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v)（已验证）与 [rtl/chisel/VDot.scala](file:///home/dbqxxs/xsriscv/cieriscv/rtl/chisel/VDot.scala)（同语义骨架，未编译）。

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

`SEW != 8`、`LMUL != 1`、`vm == 0` 三条必须在**译码期或发射前**判定为 illegal-instruction，而不是在功能单元里静默丢弃：

- 译码期判定：uop 带 `illegal` 标记，进入异常路径，不进入 VFu；
- 若框架只能在 VFu 内上报，则用 `core.io.out.illegal` 驱动对应异常通路，并确保**不产生写回**。

`vl == 0` 与上述不同：它是合法指令，只是无元素写入 —— 用 `io.in.vlZero` 驱动 `out_valid=0`。

---

## 6. Step E：构建与仿真

```bash
# 编译（以 xs-env 官方命令为准）
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
| B4 | 把 `tests/vectors/vdot_vectors.txt` 的 1518 条用例映射为汇编程序批量跑 | 1518/1518 与 Python 期望一致 |
| B5 | 与 NEMU difftest（阶段三） | 无 difftest 报错 |

**B1/B2 的"零回归"是硬门禁**：任何一条既有用例失败，先回滚本次改动再定位，不允许带着回归继续往下做。

---

## 8. 集成点核对表（执行后回填）

| # | 集成环节 | 实际文件 | 实际符号 | 核实时间 | 状态 |
|---|---|---|---|---|---|
| I1 | 译码 | | | | 待核实 |
| I2 | uop 类型 | | | | 待核实 |
| I3 | 功能单元 | | | | 待核实 |
| I4 | 发射/忙表 | | | | 待核实 |
| I5 | 写回 | | | | 待核实 |
| I6 | 配置校验 | | | | 待核实 |
| I7 | 参数开关 | | | | 待核实 |

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
