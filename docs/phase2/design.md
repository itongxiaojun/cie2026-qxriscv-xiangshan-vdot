# vdot.vv 设计文档（阶段二提交版）

| 项目 | 内容 |
|---|---|
| 团队 | qxriscv |
| 目标平台 | 香山（XiangShan）昆明湖 V2，VLEN=128 |
| 交付物对应 | 阶段二 2.1「vdot.vv 设计文档」 |
| 规范性上游 | [ipd/01 指令与微架构设计规格书](file:///home/dbqxxs/xsriscv/cieriscv/ipd/01_vdot指令与微架构设计规格书.md)（需求条目、ADR、开放问题） |
| 实现 | [rtl/verilog/VDot.v](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v)（已验证）、[rtl/chisel/VDot.scala](file:///home/dbqxxs/xsriscv/cieriscv/rtl/chisel/VDot.scala)（已编译，生成 RTL 同向量回归 PASS） |
| 验证结论 | [阶段二测试报告](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase2/test_report.md)：1518/1518 PASS，延迟 3 cycle，吞吐 1 inst/cycle，行覆盖率 36/36 = 100%；Chisel 生成 RTL 同向量等价回归 1518/1518 |
| 文档版本 | v1.2（2026-11-02，补充 Chisel 编译/等价回归、SEW 接口位宽修正与覆盖率证据） |

---

## 1. 设计目标与约束

本设计在**不新增流水线、不修改既有向量功能单元逻辑**的前提下，为昆明湖 V2 的向量执行单元增加一个自洽的点积功能单元，使 `vdot.vv` 以单 uop 完成 8 个 int8 的乘累加，并把结果写入 `vd[31:0]`，同时按题面要求把 `vd[127:32]` 清零。

| 约束 | 来源 | 设计响应 |
|---|---|---|
| SEW=8、VLEN=128、K=8 | 赛题语义 | 参数化 `VLEN/K/ACC_W/OUT_W`，默认值即题面值 |
| 复用现有向量实现 | 赛题核心要求 | 只挂接既有向量发射/写回框架，新增 1 个 VFu，零改动既有 VFu |
| 阶段二需完成正/负/边界三类测试 | 提交要求 2.3.1–2.3.3 | 已由 1518 条用例覆盖（含 4 类边界） |
| 4 周内可交付 | IPD 计划 | 无状态单 uop 设计，无跨指令状态、无归约网络 |

---

## 2. 指令语义

### 2.1 汇编格式与建议编码

```
vdot.vv  vd, vs1, vs2
```

| 字段 | 位域 | 取值 | 说明 |
|---|---|---|---|
| funct6 | [31:26] | `111111` | 已定值：RVV 保留空间，与 RVV 1.0 已分配项无冲突（O2 关闭） |
| vm | [25] | `1` | 仅无掩码形态合法 |
| vs2 | [24:20] | 源寄存器 2 | 提供 lane0..7 |
| vs1 | [19:15] | 源寄存器 1 | 提供 lane0..7 |
| funct3 | [14:12] | `000`（OPIVV） | 复用标准向量整数运算编码空间 |
| vd | [11:7] | 目标寄存器 | 仅 `vd[31:0]` 承载结果 |
| opcode | [6:0] | `0x57`（OP-V） | |

编码在 RTL 中集中为常量组，若官方后续明确其他编码，只需替换常量与译码表项，数据通路不变。

### 2.2 规范性伪代码

```python
def vdot_vv(vd, vs1, vs2):
    if SEW != 8 or LMUL != 1 or vm != 1:
        raise IllegalInstruction
    if vl == 0:
        return                        # 不写 vd，不置 dirty
    s = 0
    for i in range(8):                # 仅使用低 64 bit
        s += sext8(vs1[8*i +: 8]) * sext8(vs2[8*i +: 8])
    vd[31:0]   = s[31:0]              # 32 bit 二补码，无饱和
    vd[127:32] = 0
    mark_vd_dirty()                   # 整寄存器脏
```

### 2.3 位宽推导（本设计的关键决策）

| 量 | 取值范围 | 结论 |
|---|---|---|
| 单个乘积 `a*b` | `[-16256, +16384]` | 16 bit 有符号足够 |
| 8 项和 `S` | `[-130048, **+131072**]` | **必须 ≥19 bit 有符号**（18 bit 上界仅 131071） |
| 内部累加 | — | 取 `ACC_W=20`，留 1 bit 余量 |
| 输出元素 | — | `OUT_W=32`，由 `S` 符号扩展 |
| 尾通道 | — | `vd[127:32]` 固定为 0 |

若把累加器写成 16/18 bit，"全 `-128` 输入"用例（`S=+131072`）会溢出。该点已固化为边界用例 `TC-B03`，实测正确（`0x00020000`）。

### 2.4 语义判定表

| 条件 | 行为 |
|---|---|
| `vl == 0` | 不写 `vd`、不置 dirty、正常退休 |
| `vl >= 1` | 写满 128 bit：`{96'b0, sext32(S)}`，与 `vl` 数值无关 |
| `vm == 0` | illegal-instruction（显式拒绝未定义形态） |
| `SEW != 8` | illegal-instruction（含 `vsew=4..7` 的保留编码） |
| `LMUL != 1` | illegal-instruction（避免组内布局歧义） |
| `vstart != 0` | 幂等重算：单元无状态，重放结果一致 |
| `vta`/`vma` | 无关：输出固定写满 128 bit |
| `vxrm`/`vxsat` | 不读不写 |

**为什么可以"无条件重算"**：单元内部没有任何跨指令累加状态，结果仅由两个源寄存器内容决定，因此中断后重放不会产生半成品，`vstart` 无需参与数据计算。

---

## 3. 微架构设计

### 3.1 单元定位

| 项 | 规格 |
|---|---|
| 形态 | 新增向量功能单元 `VDot`，不新增流水段 |
| 每指令 uop | 1（128 bit 一次处理，不做多 beat 切分） |
| 流水 | 全流水、无状态、支持背靠背发射 |
| 延迟 | 3 周期（EX1 / EX2 / WB） |
| 吞吐 | 1 条/周期 |
| 阻塞/重放 | 无；不做跨 uop 归约 |
| 旁路 | 不内部旁路，RAW 由既有记分牌保证 |

### 3.2 数据通路

```
      vs1[63:0]                                   vs2[63:0]
  ┌──┬──┬──┬──┬──┬──┬──┬──┐                 ┌──┬──┬──┬──┬──┬──┬──┬──┐
  │ 7│ 6│ 5│ 4│ 3│ 2│ 1│ 0│  int8 lanes     │ 7│ 6│ 5│ 4│ 3│ 2│ 1│ 0│
  └─┬┴─┬┴─┬┴─┬┴─┬┴─┬┴─┬┴─┬┘                 └─┬┴─┬┴─┬┴─┬┴─┬┴─┬┴─┬┴─┬┘
    ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼                     ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼
  ┌───────────────────────────────────────────────────────────────┐
  │         8 × 有符号 8×8 乘法器  → p0..p7 (16 bit)               │ EX1
  └───────────────────────────────┬───────────────────────────────┘
                    ┌─────────────┴─────────────┐
                    │ 流水寄存器 s1_prod[0..7]  │
                    └─────────────┬─────────────┘
  ┌───────────────────────────────┴───────────────────────────────┐
  │  加法树 8→4→2→1（三级拓扑同周期内完成），操作数扩展至 ACC_W=20 │ EX2
  └───────────────────────────────┬───────────────────────────────┘
                    ┌─────────────┴─────────────┐
                    │ 流水寄存器 s2_sum (20 bit)│ + 控制位
                    └─────────────┬─────────────┘
  ┌───────────────────────────────┴───────────────────────────────┐
  │  {96'b0, sext32(s2_sum)}  → 128 bit vd payload                 │ WB
  └───────────────────────────────┬───────────────────────────────┘
                                  ▼  向量写回端口（含 dirty 标记）
```

乘法与加法树均为组合逻辑，两级之间各插一级流水寄存器，因此延迟为 3 周期（发射读 → EX1 → EX2 → WB 可见），且每周期可接收一条新请求。

### 3.3 周期级时序

| 周期 | 动作 | 关键信号（RTL 命名） |
|---|---|---|
| T0 | 请求接收，锁存源 payload 与控制位 | `in_valid/in_vs1/in_vs2/in_vm/in_sew/in_lmul/in_vl_zero` |
| T0 末 | EX1 结果打入第一级 | `s1_prod[0..7]`、`s1_illegal/s1_write` |
| T1 末 | EX2 加法树结果打入第二级 | `s2_sum`、`s2_illegal/s2_write` |
| T2 末 | 格式化并写回 | `out_vd/out_valid/out_illegal/out_dirty` |

实测（见测试报告 §5）：`in_valid` 到 `out_valid` 为 3 个时钟沿，与上表一致，无额外气泡；连续发射吞吐 1 inst/cycle。

### 3.4 参数

| 参数 | 默认 | 可配置 | 说明 |
|---|---|---|---|
| `VLEN` | 128 | 否 | 平台固定 |
| `K` | 8 | 是 | 分组长度；仿真启动检查 `K==8` |
| `ACC_W` | 20 | 是 | 必须 ≥19，仿真启动检查 |
| `OUT_W` | 32 | 是 | 必须 ≥ACC_W |

---

## 4. RTL 实现说明

### 4.1 模块接口

`rtl/verilog/VDot.v` 提供一个与香山集成解耦的"请求/写回"接口：

| 方向 | 信号 | 位宽 | 含义 |
|---|---|---|---|
| in | `clk`, `reset` | 1 | 同步复位、高有效 |
| in | `in_valid` | 1 | 请求有效 |
| in | `in_vs1`, `in_vs2` | 128 | 源寄存器 payload |
| in | `in_vl_zero` | 1 | `vl==0`：不写回 |
| in | `in_vm`, `in_sew[2:0]`, `in_lmul[2:0]` | 1/3/3 | 合法性判定输入 |
| out | `out_vd` | 128 | 写回数据 |
| out | `out_valid` | 1 | 写回有效 |
| out | `out_illegal` | 1 | 非法指令（不写回） |
| out | `out_dirty` | 1 | 整寄存器脏 |

合法性判定为单行组合逻辑：`legal = in_vm && (in_sew == 0) && (in_lmul == 0)`。

`in_sew` 必须保留完整 3 bit（与 `vtype.vsew` 同宽）：若只取低 2 bit，保留编码 `vsew=4`（`3'b100`）会被截断为 0 而误判为 e8。该问题已由 TC-E05 覆盖并在 v1.2 修正。

### 4.2 实现结构（与文件对应）

| 功能块 | 位置 | 说明 |
|---|---|---|
| 参数自检 | [VDot.v#L48-L52](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L48-L52) | `K`/`ACC_W`/`OUT_W` 越界即 `$fatal` |
| 合法性判定 | [VDot.v#L57-L58](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L57-L58) | 仅支持 `vm=1 / e8 / m1` |
| 8 路乘法 | [VDot.v#L63-L74](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L63-L74) | `generate` 展开 8 个 `8×8` 有符号乘 |
| EX1→EX2 流水寄存器 | [VDot.v#L82-L95](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L82-L95) | 保存 8 个乘积与控制位（`s1_illegal/s1_write`） |
| EX2 加法树 | [VDot.v#L100-L118](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L100-L118) | 8→4→2→1，常数索引展开，20 bit |
| EX2→WB 流水寄存器 | [VDot.v#L120-L133](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L120-L133) | 保存和与控制位（`s2_illegal/s2_write`） |
| 写回格式化 | [VDot.v#L138-L154](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L138-L154) | 符号扩展 + 96 bit 尾零 |
| 仿真断言 | [VDot.v#L159-L171](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L159-L171) | 高位清零、valid/illegal 互斥、dirty 伴随 valid |

两点实现说明：

1. **加法树采用常数索引显式展开**，而非二维数组动态索引。原因：后者在 Verilator 中触发 `UNOPTFLAT`（工具无法判定元素级依赖），改写后告警消失，同时更接近可综合写法（缺陷记录 D-01）。
2. **乘法器不在两级间复用**：8 个乘法器为 EX1 专用，EX2 只做加法与格式化。这是"3 周期、1 条/周期"吞吐的直接来源。面积代价为 8 个小乘法器 + 7 个 20 bit 加法器 + 172 bit 流水寄存器；generic 综合实测 4186 单元、172 个触发器、最长寄存器到寄存器路径 25 级，按 2 输入 NAND 等效口径约 **5.3k–8.4k GE（中值 ≈6.9k）**，证据见 [阶段四发布报告](../phase4/release_report.md) §3 与 `docs/phase4/01_yosys_synth.log`（该口径为工艺无关综合，非 PDK µm² 签核值）。

> 环境注记（2026-11-01）：当前工作区已迁移，主机**未安装 yosys**，上述综合数字为迁移前的历史证据，暂不可在本机复跑；功能与时序结论（1518/1518、3 cycle）已在新环境复跑确认。

### 4.3 Chisel 版本

`rtl/chisel/VDot.scala` 提供与 Verilog 版同语义的 `VDotCore`：

- `laneSInt` / `ext` / `treeSum` 分别对应 lane 切片、符号扩展与树形归约；
- 三级 `RegNext` 对应 EX1/EX2/WB；
- **状态（v1.2 更新）**：已用 `.tools/jdk` + `.tools/bin/mill` + 缓存的 Chisel 6.6.0 / firtool 1.62.1 **编译通过并成功 elaboration、生成 SystemVerilog**（`rtl/chisel/VDotCore.sv`，214 行）；
- 生成 RTL 经 `rtl/chisel/VDotWrap.v` 对齐端口后，复用同一测试台与同一 1518 条向量 + 1024 条背靠背 + 补充自检，结果 **1518/1518 PASS、3 cycle、1.0 inst/cycle**，与 Verilog 版一致（`docs/phase2/logs/09_chisel_equiv.log`）。

编译过程中修正了 3 个仅在 Chisel 版暴露的问题（详见测试报告 §7）：

1. `s2Sum = RegNext(sum2)` 对宽度推断节点会生成位宽未知的寄存器 → 改为显式 `RegInit(0.S(ACCW.W))`；
2. 加法树各级 `+` 的位宽语义不显式 → 每级 `(a +& b)(ACCW-1,0)` 截断，确保静态可推断且与 Verilog 的 20 bit 加法一致；
3. 断言消息含中文导致 firtool 1.62.1 拒绝（Unicode 转义不支持）→ 断言消息改为 ASCII。

接入香山时仍以该文件为骨架，按下节集成点替换为官方 `VFu` 基类。

---

## 5. 与香山昆明湖 V2 的集成方案

完整步骤、代码骨架与逐项核对清单见 [香山集成说明](file:///home/dbqxxs/xsriscv/cieriscv/patches/xiangshan-vdot-integration.md)。要点：

| # | 集成环节 | 动作 |
|---|---|---|
| I1 | 译码 | 新增 `vdot.vv` 匹配项（opcode/funct3/funct6/vm） |
| I2 | uop 类型 | 新增 `VFuType.VDot` |
| I3 | 功能单元 | 新增 `VDot` 模块并实例化进向量执行单元，参考 `VMul` 结构 |
| I4 | 发射/忙表 | 绑定 VDot 端口与释放条件 |
| I5 | 写回 | 复用向量写回端口，置整寄存器 dirty |
| I6 | 配置校验 | `SEW/LMUL/vm` 检查与 illegal 抛出 |
| I7 | 参数 | `GROUP_K`/`OUT_W` 参数化便于回退 |

**集成原则**：只做加法（新增文件 + 少量注册点），每完成一个环节跑一次既有向量冒烟测试，确保零回归。

> **状态声明（2026-11-03 更新）**：上述集成已在香山 `16ae9dd` 源码上执行（I1–I7），RTL 重生成 + emu 重建完成，并跑通定向 7/7（difftest 0 mismatch）与非法配置 5/5。本文档中"已验证"的原始含义是模块级 RTL 仿真；系统级证据见 [测试报告 §8](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase2/test_report.md) 与 `docs/phase2/logs/xs_emu_*.log`。

---

## 6. 验证结果摘要

| 项 | 结果 | 证据 |
|---|---|---|
| 定向用例（功能/边界/配置异常） | 18/18 PASS | 测试报告 §4.1–4.3 |
| 随机 + 边界密集 | 1500/1500 PASS | 测试报告 §4.4 |
| 背靠背流式 | 1024/1024 PASS | 测试报告 §4.4 |
| 三方模型一致性 | 1518/1518 | `logs/06_c_model_crosscheck.log` |
| 逐 lane 定位（lane0..7 单独非零） | 8/8 PASS | `logs/03_unit_test.log`（`lane_checks`） |
| `vstart` 幂等重放（同请求连续重放 3 次） | 3/3 PASS | `logs/03_unit_test.log`（`replay_checks`） |
| 保留 SEW 编码（`vsew=4`）拒绝 | PASS（illegal，不写回） | `logs/03_unit_test.log`（`reserved_sew`） |
| 复位空闲（复位后无 valid/illegal/dirty、`vd=0`） | PASS | `logs/03_unit_test.log`（`reset_idle`） |
| 延迟 / 吞吐 | 3 cycle / 1.0 inst/cycle | `logs/03_unit_test.log` |
| Chisel 版 ↔ Verilog 版等价回归（同一测试台/同一向量） | 1518/1518 PASS，3 cycle，1.0 inst/cycle | `logs/09_chisel_equiv.log` |
| 行覆盖率（Verilator `--coverage-line`） | **36/36 = 100%** | `logs/07_coverage.log` |
| generic 综合（工艺无关） | 4186 单元 / 172 FF / 25 级 R2R | `docs/phase4/01_yosys_synth.log` |
| 严格 lint（Verilator -Wall） | 0 告警 0 错误 | `docs/phase4/02_verilator_lint.log` |
| 断言违反 | 0 | 测试报告 §6 |

---

## 7. 偏差、风险与未决项

| # | 项 | 状态 | 处理 |
|---|---|---|---|
| U-01 | 香山集成与仿真 | **已完成（2026-11-03）**：I1–I7 落地，RTL 重生成 + emu 重建，定向 7/7、非法 5/5 | 见测试报告 §8 与 `docs/phase2/logs/xs_emu_*.log` |
| U-02 | 汇编级测试（emu） | **已完成（2026-11-03）**：`vdot_directed.S` 7 例、`vdot_illegal.S` 5 例 | 复用同一向量集；`tests/phase2/xs_emu/run_emu.sh` |
| U-03 | NEMU 扩展与 difftest | **已完成**（阶段三 T3.1–T3.4） | 见 `docs/phase3/cosim_report.md`，1513/1513，RTL↔NEMU 0 mismatch |
| U-04 | 真实加速比 | **已完成（2026-11-03）**：emu 实测 9.8×（对标量，8-lane 公平）/ 11.8×（对 RVV，16-lane，属上界），NITER=2000 | 见 `docs/phase3/perf_analysis.md` §6 |
| U-05 | 综合面积/时序 | **部分关闭**（阶段四 T4.2/T4.3） | generic 综合已取得：4186 单元 / 172 FF / 25 级 R2R / ≈5.3k–8.4k GE，见 `docs/phase4/01_yosys_synth.log`；PDK 映射后的 µm²、ns 签核仍待做 |
| O2 | funct6 编码冲突 | **已关闭**（`111111` 属 RVV 保留空间） | 香山集成时仍按 `patches/xiangshan-vdot-integration.md` I1 做一次 grep 复核 |
| — | Chisel 版可编译性 | **已关闭**（v1.2） | Chisel 6.6.0 + firtool 1.62.1 编译通过、生成 `rtl/chisel/VDotCore.sv`，经 `VDotWrap.v` 复用同一测试台完成 1518/1518 等价回归（`logs/09_chisel_equiv.log`） |
| — | 单元级行覆盖率 | **已关闭**（v1.2） | `--coverage-line` + `--annotate-min 1`，36/36 = 100%（`logs/07_coverage.log`） |

---

## 8. 追溯

| 需求 | 设计位置 | 验证 |
|---|---|---|
| 8 个 int8 有符号点积 | §2.2、§4.2 乘法块 | TC-F01/F02/F03、TC-R |
| `vd[0]=result`（32 bit） | §2.3、§4.2 写回格式化 | 全部写回用例逐位比对 |
| `vd[127:32]=0` | §4.2 尾零填充 + 断言 | 断言 + 128 bit 全宽比对 |
| 19 bit 溢出边界正确 | §2.3 | TC-B03（`0x00020000`） |
| 非法配置拒绝 | §2.4、§4.2 合法性判定 | TC-E01..E04 |
| 非法配置拒绝（保留 SEW 编码 `vsew=4..7`） | §2.4、§4.1 `in_sew[2:0]` | TC-E05（`reserved_sew`，见 `logs/03_unit_test.log`） |
| `vstart != 0` 幂等重算 | §2.4、§3.1 无状态设计 | TC-V03（同请求连续重放 3 次，`replay_checks`） |
| lane0..7 逐通道定位 | §4.2 乘法块按 lane 切片 | 逐 lane 自检 8/8（`lane_checks`） |
| 单 uop / 3 周期 / 1 条每周期 | §3.1、§3.3 | 测试报告 §5 |
| Chisel 与 Verilog 语义一致 | §4.3 | `logs/09_chisel_equiv.log`（1518/1518） |
